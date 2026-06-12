"""
远程执行器 —— Agent 可调用的轻量工具集。

运行在麒麟VM上的操作通过 SSH 执行，本地 Windows 负责 Agent 推理。
所有工具返回结构化数据，供 Agent 解析和决策。

安全增强:
  - 非 root 沙箱执行 (ops_agent 用户)
  - 资源限制 (CPU/内存/文件描述符/进程数)
  - 高危命令白名单
"""

import json
import logging
import re
from datetime import datetime
from typing import Union
from .ssh_client import get_ssh_client, get_ssh_for_server_sync
from app.services.server_user_policy import default_ops_ssh_user

logger = logging.getLogger(__name__)

# ── 沙箱配置 ──
def _sandbox_user() -> str:
    return default_ops_ssh_user()

SANDBOX_ENABLED = True  # 是否启用沙箱
SANDBOX_RLIMIT_CPU = 30      # CPU 时间限制（秒）
SANDBOX_RLIMIT_MEMORY_MB = 512  # 内存限制（MB）
SANDBOX_RLIMIT_NOFILE = 256  # 文件描述符限制
SANDBOX_RLIMIT_NPROC = 50    # 进程数限制

# 白名单：始终以 root 执行的只读命令
READONLY_ROOT_WHITELIST = [
    "systemctl status", "journalctl", "cat ", "ls ", "df ", "free ",
    "ps ", "ss ", "ip ", "getent", "readlink", "uptime", "hostname",
    "uname", "cat /etc/os-release", "python3 -c", "cat /proc",
]

# ── 工具结果统一格式 ──


def _ok(data):  # type: (Union[dict, str]) -> dict
    return {"success": True, "data": data, "timestamp": datetime.now().isoformat()}


def _err(msg: str) -> dict:
    return {"success": False, "error": msg, "timestamp": datetime.now().isoformat()}


# ── 沙箱包装 ──

def _is_readonly_command(command: str) -> bool:
    """判断命令是否为只读操作，可在 root 下直接执行"""
    cmd_stripped = command.strip()
    for prefix in READONLY_ROOT_WHITELIST:
        if cmd_stripped.startswith(prefix):
            return True
    return False


def _is_root_maintenance_command(command: str) -> bool:
    """包缓存清理、journal 收缩等需在 root 下执行的安全维护命令。"""
    cmd = command.strip()
    if re.search(r"\b(journalctl)\s+.*--vacuum", cmd, re.I):
        return True
    if re.search(r"\b(dnf|yum)\s+clean\b", cmd, re.I):
        return True
    if re.search(r"\b(apt-get|apt)\s+(clean|autoclean|autoremove)\b", cmd, re.I):
        return True
    return False


def _rlimit_prefix() -> str:
    return "ulimit -t {cpu} -v {mem} -n {nofile} -u {nproc} 2>/dev/null; ".format(
        cpu=SANDBOX_RLIMIT_CPU,
        mem=SANDBOX_RLIMIT_MEMORY_MB * 1024,
        nofile=SANDBOX_RLIMIT_NOFILE,
        nproc=SANDBOX_RLIMIT_NPROC,
    )


def _command_needs_root(command: str) -> bool:
    """非 root SSH 连接时需 sudo 提权的命令。"""
    cmd = command.strip()
    if _is_root_maintenance_command(command):
        return True
    if cmd.startswith("systemctl ") and not cmd.startswith("systemctl status"):
        return True
    if re.search(r"\b(dnf|yum|apt-get|apt)\s+install\b", cmd, re.I):
        return True
    if cmd.startswith("kill "):
        return True
    return False


def _wrap_privileged(command: str, ssh_username: str) -> str:
    """特权命令：root 直连时带 ulimit；普通用户时用 sudo -n。"""
    inner = _rlimit_prefix() + command
    ssh_user = (ssh_username or "").strip().lower()
    if ssh_user and ssh_user != "root":
        escaped = inner.replace("'", "'\"'\"'")
        return f"sudo -n bash -c '{escaped}'"
    return inner


def _sandbox_wrap(command: str, timeout: int = 30, ssh_username: str = "") -> str:
    """将命令包装在非 root 沙箱中执行。

    策略:
      1. 只读命令 → 当前 SSH 用户直接执行
      2. 特权维护/系统管理 → sudo（非 root 连接）或 root + ulimit
      3. 其他写操作 → 降权到沙箱用户（若已是沙箱用户则直接执行）
    """
    if not SANDBOX_ENABLED:
        if _command_needs_root(command) and (ssh_username or "").strip().lower() not in ("", "root"):
            escaped = command.replace("'", "'\"'\"'")
            return f"sudo -n bash -c '{escaped}'"
        return command

    ssh_user = (ssh_username or "").strip().lower()
    sandbox_user = _sandbox_user().lower()

    # 只读命令直接执行
    if _is_readonly_command(command):
        return command

    # 磁盘/包缓存维护、systemctl 管理
    if _is_root_maintenance_command(command) or (
        command.strip().startswith("systemctl ")
        and not command.strip().startswith("systemctl status")
    ):
        return _wrap_privileged(command, ssh_username)

    # kill 命令
    if command.strip().startswith("kill "):
        if ssh_user and ssh_user != "root":
            escaped = command.replace("'", "'\"'\"'")
            return f"sudo -n bash -c '{escaped}'"
        return command

    # 包安装
    if re.search(r"\b(dnf|yum|apt-get|apt)\s+install\b", command.strip(), re.I):
        return _wrap_privileged(command, ssh_username)

    limits = _rlimit_prefix()
    escaped_cmd = command.replace("'", "'\"'\"'")

    # 已以沙箱用户连接：直接执行 + ulimit
    if ssh_user == sandbox_user:
        return limits + command

    # 其他写操作：降权到沙箱用户（如用户不存在则直接执行 + ulimit）
    wrapped = (
        "if id {user} >/dev/null 2>&1; then "
        "  su - {user} -c '{limits}{escaped_cmd}'; "
        "else "
        "  {limits}{escaped_cmd}; "
        "fi"
    ).format(
        user=_sandbox_user(),
        limits=limits,
        escaped_cmd=escaped_cmd,
    )
    return wrapped


def _wrap_with_timeout(command: str, timeout: int) -> str:
    """给命令包装 timeout（复杂 shell 片段须经 bash -c 执行）。"""
    escaped = command.replace("'", "'\"'\"'")
    return "timeout {t} bash -c '{cmd}'".format(t=timeout, cmd=escaped)


# ── 系统信息工具 ──


def get_system_info(server_id: str = None) -> dict:
    """获取系统基本信息：内核、发行版、架构。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = """
        echo "===OS==="
        cat /etc/os-release 2>/dev/null | grep -E '^(NAME|VERSION)=' | cut -d= -f2 | tr -d '"'
        echo "===KERNEL==="
        uname -r
        echo "===ARCH==="
        uname -m
        echo "===HOSTNAME==="
        hostname
        echo "===UPTIME==="
        uptime -p 2>/dev/null || uptime
        echo "===UPTIME_SEC==="
        awk '{print int($1)}' /proc/uptime
    """
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取系统信息失败")
    return _ok(_parse_kv(out))


def get_cpu_info(server_id: str = None) -> dict:
    """获取 CPU 使用率和负载。"""
    ssh = get_ssh_for_server_sync(server_id)
    # 用 Python 解析 top 输出，彻底避免 bash/awk 转义问题
    cmd = (
        "python3 -c \""
        "import subprocess,re; "
        "out=subprocess.check_output(['top','-bn1']).decode(); "
        "cpu_line=[l for l in out.split(chr(10)) if '%Cpu' in l][0]; "
        "idle=float(re.findall(r'([0-9.]+)\\s+id', cpu_line)[0]); "
        "print(f'===CPU_CORES==='); "
        "import os; print(os.cpu_count()); "
        "print(f'===LOAD_1_5_15==='); "
        "print(open('/proc/loadavg').read().split()[0]+','+open('/proc/loadavg').read().split()[1]+','+open('/proc/loadavg').read().split()[2]); "
        "print(f'===CPU_USAGE==='); "
        "print(f'{100-idle:.1f}')"
        "\""
    )
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取CPU信息失败")
    return _ok(_parse_kv(out))


def get_memory_info(server_id: str = None) -> dict:
    """获取内存和交换分区使用情况（MB）。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = """
        echo "===MEM_TOTAL_MB===" && free -m | awk '/^Mem:/{print $2}'
        echo "===MEM_USED_MB===" && free -m | awk '/^Mem:/{print $3}'
        echo "===MEM_AVAILABLE_MB===" && free -m | awk '/^Mem:/{print $7}'
        echo "===SWAP_TOTAL_MB===" && free -m | awk '/^Swap:/{print $2}'
        echo "===SWAP_USED_MB===" && free -m | awk '/^Swap:/{print $3}'
    """
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取内存信息失败")
    return _ok(_parse_kv(out))


def get_disk_info(server_id: str = None, mount_point: str = "") -> dict:
    """获取磁盘使用情况，可指定挂载点。"""
    ssh = get_ssh_for_server_sync(server_id)
    if mount_point:
        cmd = "df -h {}".format(mount_point)
    else:
        cmd = "df -h --type=ext4 --type=xfs --type=btrfs 2>/dev/null || df -h /"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取磁盘信息失败")
    lines = out.strip().split("\n")
    disks = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6:
            disks.append({
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "available": parts[3],
                "use_percent": parts[4],
                "mount": parts[5],
            })
    return _ok({"disks": disks, "raw": out})


def get_network_info(server_id: str = None) -> dict:
    """获取网络接口和IP信息。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = "ip -4 addr show 2>/dev/null | grep -E '(^[0-9]:|inet )' | grep -v '127.0.0.1'"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取网络信息失败")
    return _ok({"raw": out})


def get_process_list(top_n: int = 10, sort_by: str = "cpu", server_id: str = None) -> dict:
    """获取占用最高的 N 个进程（可按 CPU 或内存排序）。"""
    ssh = get_ssh_for_server_sync(server_id)
    sort_flag = "-%mem" if str(sort_by).lower() == "mem" else "-%cpu"
    cmd = f"ps aux --sort={sort_flag} | head -{int(top_n) + 1}"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取进程列表失败")
    return _ok({"raw": out, "top_n": top_n, "sort_by": sort_by})


def get_process_detail(pid: int, server_id: str = None) -> dict:
    """获取指定进程的详细信息。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = f"""
        echo "===INFO==="
        ps -p {pid} -o pid,ppid,user,%cpu,%mem,cmd --no-headers 2>/dev/null
        echo "===FDS==="
        ls /proc/{pid}/fd 2>/dev/null | wc -l
        echo "===CWD==="
        readlink /proc/{pid}/cwd 2>/dev/null
        echo "===EXE==="
        readlink /proc/{pid}/exe 2>/dev/null
        echo "===ENV==="
        cat /proc/{pid}/environ 2>/dev/null | tr '\\0' '\\n' | head -20
    """
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or f"获取进程 {pid} 详情失败")
    return _ok({"pid": pid, "raw": out})


def kill_process(pid: int, signal: str = "TERM", server_id: str = None) -> dict:
    """终止指定进程。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = f"kill -{signal} {pid} 2>&1; echo $?"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or f"终止进程 {pid} 失败")
    return _ok({"pid": pid, "signal": signal, "result": out.strip()})


def get_service_status(service_name: str, server_id: str = None) -> dict:
    """获取指定服务状态（结构化 + 保留原始日志供详情查看）。"""
    from app.services.tool_output_formatter import parse_systemctl_status

    ssh = get_ssh_for_server_sync(server_id)
    cmd = f"systemctl status {service_name} 2>/dev/null || echo 'Service not found'"
    out, err, code = ssh.execute(cmd)
    if code != 0 and "not found" not in out:
        return _err(err or f"获取服务 {service_name} 状态失败")
    raw = out.strip()
    parsed = parse_systemctl_status(raw, service_name)
    payload = {
        "service": service_name,
        **parsed,
        "raw_status": raw,
    }
    if parsed.get("state") == "not-found":
        ret = _err(parsed.get("summary") or f"{service_name} 未找到或未安装")
        ret["data"] = payload
        return ret
    return _ok(payload)


def manage_service(service_name: str, action: str, server_id: str = None) -> dict:
    """管理服务：start/stop/restart/reload。"""
    ssh = get_ssh_for_server_sync(server_id)
    valid_actions = ["start", "stop", "restart", "reload"]
    if action not in valid_actions:
        return _err(f"无效操作: {action}，有效操作: {', '.join(valid_actions)}")
    cmd = f"systemctl {action} {service_name} 2>&1; echo \"Exit code: $?\""
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or f"{action} 服务 {service_name} 失败")
    return _ok({"service": service_name, "action": action, "result": out.strip()})


def get_network_connections(state: str = "", server_id: str = None) -> dict:
    """获取网络连接状态。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = f"ss -tuln {'state ' + state if state else ''} 2>/dev/null | head -50"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取网络连接失败")
    return _ok({"raw": out, "state": state})


def get_network_interfaces(server_id: str = None) -> dict:
    """获取网络接口信息。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = "ip addr show 2>/dev/null | grep -E '(^[0-9]:|inet |link/ether)'"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取网络接口失败")
    return _ok({"raw": out})


def _read_proc_net_dev_stats(ssh) -> dict:
    """解析 /proc/net/dev 为 {iface: {rx_bytes, tx_bytes}}。"""
    out, err, code = ssh.execute("cat /proc/net/dev")
    if code != 0:
        return {}
    stats: dict = {}
    for line in (out or "").splitlines():
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        if iface in ("lo",):
            continue
        parts = rest.split()
        if len(parts) < 9:
            continue
        try:
            stats[iface] = {"rx_bytes": int(parts[0]), "tx_bytes": int(parts[8])}
        except ValueError:
            continue
    return stats


def _rate_network_speed_bps(rx_bps: float, tx_bps: float) -> tuple:
    """返回 (rating_code, rating_label)。"""
    total_kbps = (rx_bps + tx_bps) / 1024
    if total_kbps < 10:
        return "idle", "空闲（几乎无实时流量）"
    if total_kbps < 100:
        return "low", "较低（轻量网络活动）"
    if total_kbps < 5120:
        return "normal", "正常（一般业务流量水平）"
    if total_kbps < 51200:
        return "high", "较高（大文件传输或高并发）"
    return "very_high", "很高（接近或达到千兆带宽上限）"


def _format_network_speed_entry(name: str, rx_bps: float, tx_bps: float, interval: float) -> dict:
    rating, rating_label = _rate_network_speed_bps(rx_bps, tx_bps)
    return {
        "iface": name,
        "rx_bps": round(rx_bps, 1),
        "tx_bps": round(tx_bps, 1),
        "rx_kbps": round(rx_bps / 1024, 2),
        "tx_kbps": round(tx_bps / 1024, 2),
        "rx_mbps": round(rx_bps * 8 / 1_000_000, 3),
        "tx_mbps": round(tx_bps * 8 / 1_000_000, 3),
        "interval_sec": interval,
        "rating": rating,
        "rating_label": rating_label,
    }


def get_network_speed(server_id: str = None, interval: float = 1.0, iface: str = "") -> dict:
    """采样网卡流量，计算实时收发速率（KB/s、Mbps）并给出评价。"""
    import time

    sample_sec = max(0.5, min(float(interval or 1.0), 5.0))
    ssh = get_ssh_for_server_sync(server_id)
    s1 = _read_proc_net_dev_stats(ssh)
    if not s1:
        return _err("无法读取 /proc/net/dev，请检查目标主机")
    time.sleep(sample_sec)
    s2 = _read_proc_net_dev_stats(ssh)
    if not s2:
        return _err("第二次采样失败，无法计算实时速率")

    iface_filter = (iface or "").strip()
    interfaces: list = []
    for name in sorted(set(s1) | set(s2)):
        if iface_filter and name != iface_filter:
            continue
        if name not in s1 or name not in s2:
            continue
        drx = max(0, s2[name]["rx_bytes"] - s1[name]["rx_bytes"])
        dtx = max(0, s2[name]["tx_bytes"] - s1[name]["tx_bytes"])
        interfaces.append(_format_network_speed_entry(name, drx / sample_sec, dtx / sample_sec, sample_sec))

    if not interfaces:
        return _err("未找到可用网卡或采样间隔内无有效数据")

    primary = max(interfaces, key=lambda x: x["rx_bps"] + x["tx_bps"])
    emoji = {"idle": "⚪", "low": "🟢", "normal": "🟢", "high": "🟡", "very_high": "🟠"}.get(primary["rating"], "🟢")
    summary = (
        f"{emoji} 网卡 **{primary['iface']}** 实时速率："
        f"下行 **{primary['rx_kbps']} KB/s**（{primary['rx_mbps']} Mbps）、"
        f"上行 **{primary['tx_kbps']} KB/s**（{primary['tx_mbps']} Mbps）；"
        f"评价：**{primary['rating_label']}**"
    )
    return _ok({
        "interval_sec": sample_sec,
        "interfaces": interfaces,
        "primary_iface": primary["iface"],
        "primary": primary,
        "summary": summary,
    })


def get_file_list(path: str = ".", server_id: str = None) -> dict:
    """获取目录文件列表。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = f"ls -la {path} 2>/dev/null"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or f"列出目录 {path} 失败")
    return _ok({"path": path, "raw": out})


def read_file(file_path: str, server_id: str = None) -> dict:
    """读取文件内容。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = f"cat {file_path} 2>/dev/null | head -100"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or f"读取文件 {file_path} 失败")
    return _ok({"path": file_path, "content": out})


def get_logs(
    service: str = "",
    priority: str = "info",
    lines: int = 20,
    path: str = "",
    file_path: str = "",
    server_id: str = None,
) -> dict:
    """获取系统日志：journalctl 按服务过滤，或 tail 指定日志文件。"""
    ssh = get_ssh_for_server_sync(server_id)
    n = max(1, min(int(lines or 20), 500))
    log_path = (path or file_path or "").strip()

    if log_path:
        cmd = f"tail -n {n} {log_path} 2>/dev/null"
        out, err, code = ssh.execute(cmd)
        if code != 0 or not (out or "").strip():
            svc = service or "cups"
            cmd = f"journalctl -u {svc} -n {n} --no-pager 2>/dev/null"
            out, err, code = ssh.execute(cmd)
        if code != 0:
            return _err(err or f"读取日志 {log_path} 失败")
        summary = f"已获取日志 {log_path}（{len((out or '').splitlines())} 行）"
        return _ok({
            "path": log_path,
            "service": service,
            "lines": n,
            "raw": out,
            "summary": summary,
        })

    cmd = "journalctl"
    if service:
        cmd += f" -u {service}"
    if priority:
        prio_map = {"err": "3", "warning": "4", "info": "6", "debug": "7"}
        cmd += f" -p {prio_map.get(priority, '6')}"
    cmd += f" -n {n} --no-pager 2>/dev/null"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取日志失败")
    summary = f"已获取 {service or '系统'} 日志（{len((out or '').splitlines())} 行）"
    return _ok({
        "service": service,
        "priority": priority,
        "lines": n,
        "raw": out,
        "summary": summary,
    })


def get_users(server_id: str = None) -> dict:
    """获取系统用户列表。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = "getent passwd | grep -E '/bin/bash|/bin/sh' | cut -d: -f1,3,4,6,7"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取用户列表失败")
    return _ok({"raw": out})


def get_groups(server_id: str = None) -> dict:
    """获取系统用户组列表。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = "getent group | cut -d: -f1,3,4"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取用户组列表失败")
    return _ok({"raw": out})


# ── 命令执行 ──


def _diagnostic_command_nonzero_ok(code: int, command: str) -> bool:
    """只读诊断命令：无匹配/未安装时退出码 1 仍视为有效检查结果。"""
    if code != 1:
        return False
    c = (command or "").lower()
    if "| grep" in c or c.strip().startswith("grep "):
        return True
    if re.search(r"\brpm\s+-q[a]?\b", c):
        return True
    if re.search(r"\bwhich\b|\bcommand -v\b", c):
        return True
    return False


def _diagnostic_negative_summary(command: str, stdout: str, stderr: str) -> str:
    c = (command or "").lower()
    if "libnss-mdns" in c or "nss-mdns" in c:
        return "未检测到 nss-mdns / libnss-mdns 包（可能未安装）"
    if "| grep" in c or c.strip().startswith("grep "):
        return "未找到匹配项（可能未安装或不存在）"
    if re.search(r"\brpm\s+-q", c):
        return "软件包未安装"
    hint = (stdout or stderr or "").strip().split("\n")[0]
    return hint[:200] if hint else "检查完成，条件不满足"


def run_command(command: str, timeout: int = 30, server_id: str = None) -> dict:
    """在远程VM上执行任意命令（Agent 核心操作入口）。

    沙箱策略:
      - 只读命令 → root 直接执行
      - 写操作 → sudo -u ops_agent 降权执行 + ulimit 资源限制
      - 系统管理 → root 执行但限制资源
    """
    ssh = get_ssh_for_server_sync(server_id)
    ssh_user = ssh.username or _sandbox_user()
    sandboxed = _sandbox_wrap(command, timeout, ssh_user)
    final_cmd = _wrap_with_timeout(sandboxed, timeout)
    logger.info("[Sandbox] user=%s | cmd=%s", ssh_user, command[:100])
    out, err, code = ssh.execute(final_cmd)
    payload = {
        "command": command,
        "sandbox": {
            "enabled": SANDBOX_ENABLED,
            "user": ssh_user,
            "rlimit_cpu": SANDBOX_RLIMIT_CPU,
            "rlimit_memory_mb": SANDBOX_RLIMIT_MEMORY_MB,
            "rlimit_nofile": SANDBOX_RLIMIT_NOFILE,
            "rlimit_nproc": SANDBOX_RLIMIT_NPROC,
        },
        "stdout": out,
        "stderr": err,
        "exit_code": code,
    }
    if code != 0:
        if _diagnostic_command_nonzero_ok(code, command):
            payload["diagnostic_negative"] = True
            payload["summary"] = _diagnostic_negative_summary(command, out, err)
            return _ok(payload)
        msg = (err or out or "").strip()[:500] or f"命令失败，退出码 {code}"
        return {"success": False, "error": msg, "data": payload, "timestamp": datetime.now().isoformat()}
    return _ok(payload)


# ── 工具注册表 ──


TOOL_REGISTRY = {
    "get_system_info": get_system_info,
    "get_cpu_info": get_cpu_info,
    "get_memory_info": get_memory_info,
    "get_disk_info": get_disk_info,
    "get_network_info": get_network_info,
    "get_network_connections": get_network_connections,
    "get_network_interfaces": get_network_interfaces,
    "get_network_speed": get_network_speed,
    "get_process_list": get_process_list,
    "get_process_detail": get_process_detail,
    "kill_process": kill_process,
    "get_service_status": get_service_status,
    "manage_service": manage_service,
    "get_file_list": get_file_list,
    "read_file": read_file,
    "get_logs": get_logs,
    "get_users": get_users,
    "get_groups": get_groups,
    "run_command": run_command,
}


def execute_tool(tool_name: str, **kwargs) -> dict:
    """Agent 统一调用入口。"""
    from app.services.tool_args import normalize_tool_args

    kwargs = normalize_tool_args(tool_name, kwargs)
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return _err(f"未知工具: {tool_name}，可用工具: {list(TOOL_REGISTRY)}")
    try:
        return tool(**kwargs) if kwargs else tool()
    except TypeError as e:
        logger.warning("Tool %s arg mismatch: %s kwargs=%s", tool_name, e, kwargs)
        return _err(str(e))
    except Exception as e:
        logger.exception(f"Tool {tool_name} failed")
        return _err(str(e))


# ── 工具描述（供 LLM Agent 使用） ──

TOOL_DESCRIPTIONS = [
    {
        "name": "get_system_info",
        "description": "获取远程麒麟VM的系统信息：操作系统版本、内核版本、CPU架构、主机名、运行时间",
        "parameters": {},
    },
    {
        "name": "get_cpu_info",
        "description": "获取远程麒麟VM的CPU信息：核心数、负载平均值、CPU使用率",
        "parameters": {},
    },
    {
        "name": "get_memory_info",
        "description": "获取远程麒麟VM的内存和交换分区使用情况（单位MB）",
        "parameters": {},
    },
    {
        "name": "get_disk_info",
        "description": "获取远程麒麟VM的磁盘分区和使用情况",
        "parameters": {},
    },
    {
        "name": "get_network_info",
        "description": "获取远程麒麟VM的网络接口和IPv4地址信息",
        "parameters": {},
    },
    {
        "name": "get_network_connections",
        "description": "获取远程麒麟VM的网络连接状态和监听端口",
        "parameters": {"state": {"type": "string", "description": "连接状态过滤: LISTEN, ESTABLISHED 等"}},
    },
    {
        "name": "get_network_interfaces",
        "description": "获取远程麒麟VM的网络接口详细信息",
        "parameters": {},
    },
    {
        "name": "get_network_speed",
        "description": "采样计算网卡实时收发速率（KB/s、Mbps），并给出网速好坏评价；用户问「网速/带宽/流量快慢」时优先使用",
        "parameters": {
            "interval": {"type": "number", "description": "采样间隔秒数，默认1秒"},
            "iface": {"type": "string", "description": "指定网卡名，如 ens33；留空则返回所有非 lo 网卡"},
        },
    },
    {
        "name": "get_process_list",
        "description": "获取远程麒麟VM上占用最高的进程列表，可按 CPU 或内存排序",
        "parameters": {
            "top_n": {"type": "integer", "description": "返回的进程数量，默认10"},
            "sort_by": {"type": "string", "description": "排序字段: cpu 或 mem，默认 cpu"},
        },
    },
    {
        "name": "get_process_detail",
        "description": "获取指定进程的详细信息，包括PID、PPID、用户、CPU占用、内存占用等",
        "parameters": {"pid": {"type": "integer", "description": "进程ID"}},
    },
    {
        "name": "kill_process",
        "description": "终止指定进程，默认发送TERM信号",
        "parameters": {
            "pid": {"type": "integer", "description": "进程ID"},
            "signal": {"type": "string", "description": "信号类型，如TERM、KILL，默认TERM"},
        },
    },
    {
        "name": "get_service_status",
        "description": "获取指定系统服务的状态",
        "parameters": {"service_name": {"type": "string", "description": "服务名称"}},
    },
    {
        "name": "manage_service",
        "description": "管理系统服务：启动、停止、重启、重载",
        "parameters": {
            "service_name": {"type": "string", "description": "服务名称"},
            "action": {"type": "string", "description": "操作：start/stop/restart/reload"},
        },
    },
    {
        "name": "get_file_list",
        "description": "获取指定目录的文件列表",
        "parameters": {"path": {"type": "string", "description": "目录路径，默认为当前目录"}},
    },
    {
        "name": "read_file",
        "description": "读取指定文件的内容（最多显示前100行）",
        "parameters": {"file_path": {"type": "string", "description": "文件路径"}},
    },
    {
        "name": "get_logs",
        "description": "获取系统日志，可按服务和优先级过滤",
        "parameters": {
            "service": {"type": "string", "description": "服务名过滤，如 nginx、cups"},
            "path": {"type": "string", "description": "日志文件路径，如 /var/log/cups/error_log"},
            "priority": {"type": "string", "description": "journal 日志级别：err/warning/info/debug"},
            "lines": {"type": "integer", "description": "返回行数，默认20"},
        },
    },
    {
        "name": "get_users",
        "description": "获取系统用户列表",
        "parameters": {},
    },
    {
        "name": "get_groups",
        "description": "获取系统用户组列表",
        "parameters": {},
    },
    {
        "name": "run_command",
        "description": "在远程麒麟VM上执行任意shell命令。⚠ 需谨慎使用，命令以root权限执行",
        "parameters": {
            "command": {"type": "string", "description": "要执行的shell命令"},
            "timeout": {"type": "integer", "description": "命令超时秒数，默认30"},
        },
    },
]


# ── 解析工具 ──


def _parse_kv(text: str) -> dict:
    """解析 ===KEY===\nVALUE 格式的文本。"""
    result = {}
    current_key = None
    for line in text.split("\n"):
        if line.startswith("===") and line.endswith("==="):
            current_key = line.strip("=").lower()
            result[current_key] = ""
        elif current_key:
            result[current_key] += (line + "\n") if result[current_key] else line
    # trim trailing newlines
    for k in result:
        if isinstance(result[k], str):
            result[k] = result[k].strip()
    return result
