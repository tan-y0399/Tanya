"""服务器自动化配置 —— 连通性检测、用户创建、SSH 免密部署。"""
from __future__ import annotations

import base64
import ipaddress
import logging
import os
import socket
import struct
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import paramiko

from app.core.config import settings
from app.services.server_user_policy import assert_allowed_ssh_user
from app.services.ssh_client import (
    _load_private_key,
    ensure_platform_keypair,
    ensure_public_key_file,
    resolve_ssh_key_path,
    resolve_ssh_public_key_path,
)

logger = logging.getLogger(__name__)

Step = Dict[str, str]


def _append_step(steps: List[Step], message: str, status: str = "info") -> None:
    steps.append({"message": message, "status": status})


def _get_primary_local_ip() -> Optional[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def _get_default_gateway() -> Optional[str]:
    try:
        with open("/proc/net/route", "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    return socket.inet_ntoa(struct.pack("<L", int(parts[2], 16)))
    except OSError:
        pass
    return None


def _ping_once(host: str, timeout: int = 2) -> bool:
    """跨平台 ping（Windows 用 -n/-w，Linux/macOS 用 -c/-W）。"""
    try:
        if os.name == "nt":
            # Windows: -n 次数；-w 超时毫秒
            cmd = ["ping", "-n", "1", "-w", str(max(timeout, 1) * 1000), host]
        else:
            cmd = ["ping", "-c", "1", "-W", str(timeout), host]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout + 2,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _same_subnet_24(ip_a: str, ip_b: str) -> bool:
    try:
        net_a = ipaddress.ip_network(f"{ip_a}/24", strict=False)
        return ipaddress.ip_address(ip_b) in net_a
    except ValueError:
        return False


def diagnose_host_connectivity(host: str, port: int = 22, timeout: int = 8) -> Dict[str, Any]:
    """诊断主机连通性，返回可操作的修复建议。"""
    host = (host or "").strip()
    port = int(port or 22)
    local_ip = _get_primary_local_ip()
    gateway = _get_default_gateway()
    same_subnet = bool(local_ip and _same_subnet_24(local_ip, host))

    gateway_ok = _ping_once(gateway) if gateway else False
    target_ping = _ping_once(host)
    tcp_ok, tcp_msg = check_host_reachable(host, port, timeout=timeout)

    suggestions: List[str] = []
    if not tcp_ok:
        if local_ip and not same_subnet:
            local_net = ".".join(local_ip.split(".")[:3]) + ".0/24"
            suggestions.append(
                f"平台运行在 {local_ip}（{local_net}），目标 {host} 不在同一网段，"
                "VMware/UTM 中请将目标虚拟机网卡改为 NAT 或桥接，与平台处于同一网段"
            )
        if not target_ping:
            suggestions.append("目标主机 ping 不通：请确认虚拟机已开机、IP 地址填写正确")
        if not gateway_ok and gateway:
            suggestions.append(f"默认网关 {gateway} 不可达，请检查本机网络配置")
        suggestions.extend([
            "在目标虚拟机控制台执行以下命令开放 SSH（不要长期关闭防火墙）：",
            "  sudo firewall-cmd --permanent --add-service=ssh && sudo firewall-cmd --reload",
            "  sudo systemctl enable --now sshd",
            "若仍不通，在虚拟化软件中将目标 VM 网络从 Host-Only(66.x) 改为 NAT(64.x)",
        ])

    reachable = tcp_ok
    message = tcp_msg if tcp_ok else (
        f"无法连接 {host}:{port}。"
        + (" 目标与平台不在同一网段，需调整虚拟机网络。" if local_ip and not same_subnet else "")
        + f" ({tcp_msg.split('(')[-1].rstrip(')') if '(' in tcp_msg else '连接超时'})"
    )

    return {
        "reachable": reachable,
        "message": message,
        "localIp": local_ip,
        "gateway": gateway,
        "gatewayReachable": gateway_ok,
        "targetPing": target_ping,
        "sameSubnet": same_subnet,
        "tcpPortOpen": tcp_ok,
        "suggestions": suggestions,
    }


def check_host_reachable(host: str, port: int = 22, timeout: int = 8) -> tuple[bool, str]:
    """检测主机 TCP 端口是否可达（支持局域网或穿透后的公网地址）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host.strip(), int(port)))
        return True, f"主机 {host}:{port} 网络可达"
    except socket.gaierror as e:
        return False, f"主机地址无法解析: {host} ({e})"
    except (TimeoutError, OSError) as e:
        return False, f"无法连接 {host}:{port}，请检查网络、防火墙或内网穿透配置 ({e})"
    finally:
        sock.close()


def _ssh_exec(client: paramiko.SSHClient, command: str, timeout: int = 20) -> tuple[str, str, int]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return out, err, code


def _connect_password(host: str, port: int, username: str, password: str, timeout: int = 15) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=port,
        username=username,
        password=password,
        timeout=timeout,
        allow_agent=False,
        look_for_keys=False,
        banner_timeout=timeout,
        auth_timeout=timeout,
    )
    return client


def _read_platform_public_key() -> str:
    # 平台公钥缺失时由私钥推导生成，避免新机器上直接失败
    pub_path = ensure_public_key_file(settings.ssh_key_path)
    with open(pub_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _verify_key_login(host: str, port: int, username: str, timeout: int = 15) -> tuple[bool, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        # 密钥解析放在 try 内：平台上尚无密钥时应优雅返回 False，而不是抛异常导致 500
        key_path = resolve_ssh_key_path(settings.ssh_key_path)
        key = _load_private_key(key_path)
        client.connect(
            hostname=host,
            port=port,
            username=username,
            pkey=key,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        out, _, code = _ssh_exec(client, "whoami && sudo -n whoami")
        if code != 0:
            return False, "密钥登录成功，但 sudo 验证失败"
        return True, f"SSH 密钥免密登录验证通过（{out.replace(chr(10), ' → ')}）"
    except Exception as e:
        return False, f"SSH 密钥免密登录验证失败: {e}"
    finally:
        client.close()


def _run_privileged(client: paramiko.SSHClient, script: str) -> tuple[str, str, int]:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = (
        "if [ \"$(id -u)\" -eq 0 ]; then echo "
        + encoded
        + " | base64 -d | bash; "
        "elif sudo -n true 2>/dev/null; then echo "
        + encoded
        + " | base64 -d | sudo bash; "
        "else echo NEED_ROOT 1>&2; exit 1; fi"
    )
    return _ssh_exec(client, cmd)


def auto_provision_server(
    host: str,
    port: int,
    target_username: str,
    host_password: str,
) -> Dict[str, Any]:
    """自动化配置远程服务器 SSH 运维环境。"""
    steps: List[Step] = []
    host = (host or "").strip()
    port = int(port or 22)
    password = host_password or ""

    if not host:
        return {"success": False, "error": "主机地址不能为空", "steps": steps}
    if not password:
        return {"success": False, "error": "请填写主机密码", "steps": steps}

    try:
        target_user = assert_allowed_ssh_user(target_username)
    except ValueError as e:
        _append_step(steps, str(e), "error")
        return {"success": False, "error": str(e), "steps": steps}

    _append_step(steps, f"目标运维用户: {target_user}", "info")

    ok, msg = check_host_reachable(host, port, timeout=settings.ssh_timeout)
    diag = diagnose_host_connectivity(host, port, timeout=settings.ssh_timeout)
    _append_step(steps, msg, "ok" if ok else "error")
    if not ok:
        if diag.get("localIp"):
            _append_step(steps, f"平台 IP: {diag['localIp']}，与目标{'同' if diag.get('sameSubnet') else '不同'}网段", "warn")
        for tip in diag.get("suggestions") or []:
            _append_step(steps, tip, "warn")
        return {"success": False, "error": diag.get("message") or msg, "steps": steps, "diagnosis": diag}

    # 确保平台密钥存在：新机器上此前没有密钥，需先生成，否则无法部署公钥
    try:
        try:
            resolve_ssh_key_path(settings.ssh_key_path)
            key_existed = True
        except FileNotFoundError:
            key_existed = False
        platform_key = ensure_platform_keypair(settings.ssh_key_path)
        if key_existed:
            _append_step(steps, f"平台 SSH 密钥已就绪: {platform_key}", "ok")
        else:
            _append_step(steps, f"平台未配置 SSH 密钥，已自动生成 Ed25519 密钥对: {platform_key}", "ok")
    except Exception as e:
        err_msg = f"平台 SSH 密钥准备失败: {e}"
        _append_step(steps, err_msg, "error")
        return {"success": False, "error": err_msg, "steps": steps}

    # 平台密钥已可登录时，无需密码（常见于已配置过免密 SSH 的服务器）
    key_ok, key_msg = _verify_key_login(host, port, target_user, timeout=settings.ssh_timeout)
    if key_ok:
        _append_step(steps, "检测到平台 SSH 密钥已可免密登录，跳过密码部署", "ok")
        _append_step(steps, key_msg, "ok")
        _append_step(steps, "自动化配置完成，可安全保存服务器", "ok")
        return {
            "success": True,
            "steps": steps,
            "username": target_user,
            "keyPath": resolve_ssh_key_path(settings.ssh_key_path),
            "skippedPassword": True,
        }

    client: Optional[paramiko.SSHClient] = None
    login_user: Optional[str] = None
    login_candidates = []
    for u in (target_user, "root"):
        if u not in login_candidates:
            login_candidates.append(u)

    for candidate in login_candidates:
        try:
            client = _connect_password(host, port, candidate, password)
            login_user = candidate
            _append_step(steps, f"SSH 密码登录成功（登录账户: {candidate}）", "ok")
            break
        except Exception as e:
            detail = getattr(e, "args", [""])[0] if getattr(e, "args", None) else str(e)
            _append_step(steps, f"尝试使用 {candidate} 登录失败（{detail or type(e).__name__}）", "warn")

    if not client or not login_user:
        key_ok2, key_msg2 = _verify_key_login(host, port, target_user, timeout=settings.ssh_timeout)
        if key_ok2:
            _append_step(steps, "密码不正确，但平台 SSH 密钥仍可登录，已改用密钥方式", "ok")
            _append_step(steps, key_msg2, "ok")
            _append_step(steps, "自动化配置完成，可安全保存服务器", "ok")
            return {
                "success": True,
                "steps": steps,
                "username": target_user,
                "keyPath": resolve_ssh_key_path(settings.ssh_key_path),
                "skippedPassword": True,
            }
        err = (
            "无法使用提供的密码登录目标主机，请确认密码及 SSH 服务已开启。"
            "若本机已配置 SSH 密钥，可清空「主机密码」后直接保存。"
        )
        _append_step(steps, err, "error")
        return {"success": False, "error": err, "steps": steps}

    try:
        session_user, _, _ = _ssh_exec(client, "whoami")
        _append_step(steps, f"当前会话用户: {session_user}", "info")

        uid_out, _, uid_code = _ssh_exec(client, f"getent passwd {target_user} | cut -d: -f3")
        if uid_code == 0 and uid_out.strip() == "0":
            err = f"用户 {target_user} 为 root（UID=0），禁止使用"
            _append_step(steps, err, "error")
            return {"success": False, "error": err, "steps": steps}

        exists_out, _, exists_code = _ssh_exec(client, f"id -u {target_user} 2>/dev/null || echo MISSING")
        user_exists = exists_code == 0 and "MISSING" not in exists_out

        if user_exists:
            _append_step(steps, f"用户 {target_user} 已存在于目标主机", "ok")
        else:
            _append_step(steps, f"用户 {target_user} 不存在，正在自动创建…", "info")
            create_script = f"""
set -e
useradd -m -s /bin/bash {target_user}
usermod -aG wheel {target_user} 2>/dev/null || usermod -aG sudo {target_user} 2>/dev/null || true
"""
            _, err, code = _run_privileged(client, create_script)
            if code != 0:
                err_msg = f"自动创建用户 {target_user} 失败: {err or '权限不足'}"
                _append_step(steps, err_msg, "error")
                return {"success": False, "error": err_msg, "steps": steps}
            _append_step(steps, f"已创建用户 {target_user} 并加入特权组", "ok")

        try:
            pubkey = _read_platform_public_key()
        except OSError as e:
            # FileNotFoundError 与 PermissionError 均为 OSError 子类，
            # 统一兜底，避免权限类问题逃逸成 500
            err_msg = f"读取平台 SSH 公钥失败: {e}"
            _append_step(steps, err_msg, "error")
            return {"success": False, "error": err_msg, "steps": steps}
        pub_b64 = base64.b64encode(pubkey.encode("utf-8")).decode("ascii")
        deploy_script = f"""
set -e
TARGET={target_user}
PUB=$(echo '{pub_b64}' | base64 -d)
HOME_DIR=$(getent passwd "$TARGET" | cut -d: -f6)
mkdir -p "$HOME_DIR/.ssh"
chmod 700 "$HOME_DIR/.ssh"
touch "$HOME_DIR/.ssh/authorized_keys"
grep -qF "$PUB" "$HOME_DIR/.ssh/authorized_keys" 2>/dev/null || echo "$PUB" >> "$HOME_DIR/.ssh/authorized_keys"
chmod 600 "$HOME_DIR/.ssh/authorized_keys"
chown -R "$TARGET:$TARGET" "$HOME_DIR/.ssh"
echo "$TARGET ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/kylinops-$TARGET
chmod 440 /etc/sudoers.d/kylinops-$TARGET
visudo -cf /etc/sudoers.d/kylinops-$TARGET >/dev/null 2>&1 || true
"""
        _, err, code = _run_privileged(client, deploy_script)
        if code != 0:
            err_msg = f"部署 SSH 公钥失败: {err or '权限不足'}"
            _append_step(steps, err_msg, "error")
            return {"success": False, "error": err_msg, "steps": steps}
        _append_step(steps, f"已为 {target_user} 配置 SSH 公钥免密登录", "ok")
        _append_step(steps, f"已为 {target_user} 配置免密 sudo", "ok")
    finally:
        client.close()

    verified, verify_msg = _verify_key_login(host, port, target_user)
    _append_step(steps, verify_msg, "ok" if verified else "error")
    if not verified:
        return {"success": False, "error": verify_msg, "steps": steps}

    _append_step(steps, "自动化配置完成，可安全保存服务器", "ok")
    return {
        "success": True,
        "steps": steps,
        "username": target_user,
        "keyPath": resolve_ssh_key_path(settings.ssh_key_path),
    }
