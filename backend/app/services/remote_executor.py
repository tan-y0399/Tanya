"""
远程执行器 —— Agent 可调用的轻量工具集。

运行在麒麟VM上的操作通过 SSH 执行，本地 Windows 负责 Agent 推理。
所有工具返回结构化数据，供 Agent 解析和决策。
"""

import json
import logging
from datetime import datetime
from typing import Union
from .ssh_client import get_ssh_client, get_ssh_for_server_sync

logger = logging.getLogger(__name__)

# ── 工具结果统一格式 ──


def _ok(data):  # type: (Union[dict, str]) -> dict
    return {"success": True, "data": data, "timestamp": datetime.now().isoformat()}


def _err(msg: str) -> dict:
    return {"success": False, "error": msg, "timestamp": datetime.now().isoformat()}


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


def get_disk_info(server_id: str = None) -> dict:
    """获取磁盘使用情况。"""
    ssh = get_ssh_for_server_sync(server_id)
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


def get_process_list(top_n: int = 10, server_id: str = None) -> dict:
    """获取 CPU 占用最高的 N 个进程。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = f"ps aux --sort=-%cpu | head -{top_n + 1}"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取进程列表失败")
    return _ok({"raw": out, "top_n": top_n})


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
    """获取指定服务状态。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = f"systemctl status {service_name} 2>/dev/null || echo 'Service not found'"
    out, err, code = ssh.execute(cmd)
    if code != 0 and "not found" not in out:
        return _err(err or f"获取服务 {service_name} 状态失败")
    return _ok({"service": service_name, "status": out.strip()})


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


def get_logs(service: str = "", priority: str = "info", lines: int = 20, server_id: str = None) -> dict:
    """获取系统日志。"""
    ssh = get_ssh_for_server_sync(server_id)
    cmd = "journalctl"
    if service:
        cmd += f" -u {service}"
    if priority:
        prio_map = {"err": "3", "warning": "4", "info": "6", "debug": "7"}
        cmd += f" -p {prio_map.get(priority, '6')}"
    cmd += f" -n {lines} --no-pager 2>/dev/null"
    out, err, code = ssh.execute(cmd)
    if code != 0:
        return _err(err or "获取日志失败")
    return _ok({"service": service, "priority": priority, "lines": lines, "raw": out})


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


def run_command(command: str, timeout: int = 30, server_id: str = None) -> dict:
    """在远程VM上执行任意命令（Agent 核心操作入口）。

    ⚠ 命令在 root 权限下执行，需由 Agent 确认无风险后再调用。
    """
    ssh = get_ssh_for_server_sync(server_id)
    out, err, code = ssh.execute(f"timeout {timeout} {command}")
    return _ok({
        "command": command,
        "stdout": out,
        "stderr": err,
        "exit_code": code,
    })


# ── 工具注册表 ──


TOOL_REGISTRY = {
    "get_system_info": get_system_info,
    "get_cpu_info": get_cpu_info,
    "get_memory_info": get_memory_info,
    "get_disk_info": get_disk_info,
    "get_network_info": get_network_info,
    "get_network_connections": get_network_connections,
    "get_network_interfaces": get_network_interfaces,
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
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return _err(f"未知工具: {tool_name}，可用工具: {list(TOOL_REGISTRY)}")
    try:
        return tool(**kwargs) if kwargs else tool()
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
        "name": "get_process_list",
        "description": "获取远程麒麟VM上CPU占用最高的进程列表",
        "parameters": {"top_n": {"type": "integer", "description": "返回的进程数量，默认10"}},
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
            "service": {"type": "string", "description": "服务名过滤，如nginx、mysql"},
            "priority": {"type": "string", "description": "日志级别：err/warning/info/debug，默认info"},
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
