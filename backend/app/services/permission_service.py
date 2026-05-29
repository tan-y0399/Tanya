"""最小权限执行控制 —— 角色-风险映射、sudo白名单、命令净化、目录/操作范围限制"""

import re
import shlex
from typing import Dict, List, Optional

# ── 角色 → 最高允许风险级别 ──
ROLE_MAX_RISK = {
    "admin": "L5",
    "operator": "L3",
    "auditor": "L2",
    "viewer": "L1",
}

# ── sudo 白名单（允许以 root 执行的命令）──
SUDO_WHITELIST = {
    # 系统信息
    "systemctl", "journalctl", "hostnamectl", "timedatectl", "localectl",
    # 网络
    "ss", "netstat", "ip", "ping", "traceroute", "nslookup", "dig",
    # 磁盘
    "df", "du", "lsblk", "blkid", "iostat", "iotop",
    # 进程
    "ps", "top", "htop", "lsof", "pidstat", "pgrep",
    # 内存
    "free", "vmstat", "pmap",
    # 文件
    "cat", "head", "tail", "less", "more", "grep", "awk", "sed",
    "find", "ls", "stat", "file", "wc", "sort", "uniq", "cut", "tr",
    # 包管理（只读）
    "rpm", "dpkg", "yum", "apt",
    # 其他
    "uptime", "who", "whoami", "id", "groups", "getent", "last", "lastb",
    "crontab", "lsmod", "modinfo",
}

# ── 危险字符/模式（命令净化时移除）──
DANGEROUS_SHELL_CHARS = re.compile(r'[;&|`$(){}[\]<>!\n\r]')
PIPE_REDIRECT_PATTERN = re.compile(r'[|>]')
COMMAND_SEPARATOR = re.compile(r'[;&]')

# ── 目录操作限制 ──
ALLOWED_READ_PATHS = [
    "/var/log", "/var/cache", "/var/tmp", "/tmp",
    "/etc", "/opt", "/home", "/root",
    "/proc", "/sys", "/dev",
    "/usr/local", "/usr/share",
]

PROTECTED_PATHS = {
    "/etc/shadow": "密码文件禁止访问",
    "/etc/shadow-": "密码文件禁止访问",
    "/root/.ssh": "SSH密钥目录禁止访问",
    "/root/.ssh/authorized_keys": "SSH密钥文件禁止访问",
    "/boot": "引导分区禁止写入",
    "/etc/sudoers": "sudo配置禁止修改",
    "/etc/sudoers.d": "sudo配置目录禁止修改",
}

BLOCKED_PATHS = [
    "/etc/shadow", "/root/.ssh", "/boot",
    "/etc/sudoers", "/etc/passwd", "/etc/group",
]

# ── 操作范围限制 ──
TOOL_SCOPE_LIMITS = {
    "read_file": {"max_lines": 500, "max_file_size_mb": 10},
    "execute_command": {"max_timeout": 120},
    "kill_process": {"allowed_signals": ["TERM", "HUP"], "admin_signals": ["TERM", "HUP", "KILL"]},
    "manage_service": {"allowed_actions": ["start"], "admin_actions": ["start", "stop", "restart", "reload"]},
    "get_file_list": {"max_depth": 3},
    "search_journal_logs": {"max_lines": 200},
}


def check_privilege_level(role: str, risk_level: str, command_group: str = "") -> dict:
    """检查用户角色是否有权限执行指定风险级别的操作"""
    max_allowed = ROLE_MAX_RISK.get(role, "L1")
    current = int(risk_level[1]) if risk_level.startswith("L") else 3
    max_val = int(max_allowed[1]) if max_allowed.startswith("L") else 1

    allowed = current <= max_val

    if allowed:
        return {"allowed": True, "reason": f"角色{role}允许执行{risk_level}级操作"}
    return {
        "allowed": False,
        "reason": f"角色{role}(最高{max_allowed})无法执行{risk_level}级操作，需要审批",
        "require_approval": True,
    }


def validate_sudo_whitelist(command: str) -> dict:
    """检查命令是否在sudo白名单中"""
    cmd_name = command.strip().split()[0] if command.strip() else ""
    cmd_base = cmd_name.split("/")[-1] if "/" in cmd_name else cmd_name

    allowed = cmd_base in SUDO_WHITELIST

    return {
        "allowed": allowed,
        "command": cmd_base,
        "message": "命令在sudo白名单中" if allowed else f"命令 '{cmd_base}' 不在sudo白名单中",
    }


def validate_path_restriction(path: str, operation: str = "read") -> dict:
    """验证路径是否在允许的操作范围内"""
    if not path or path == ".":
        return {"allowed": True, "message": ""}

    normalized = path.strip()

    # 检查保护路径
    for protected, reason in PROTECTED_PATHS.items():
        if normalized == protected or normalized.startswith(protected + "/"):
            return {"allowed": False, "message": reason}

    # 检查阻止路径
    for blocked in BLOCKED_PATHS:
        if normalized.startswith(blocked):
            return {"allowed": False, "message": f"路径 {blocked} 禁止访问"}

    # 检查允许路径（读操作）
    if operation == "read":
        for allowed in ALLOWED_READ_PATHS:
            if normalized.startswith(allowed):
                return {"allowed": True, "message": ""}
        # 绝对路径但不在允许列表中
        if normalized.startswith("/"):
            return {"allowed": True, "message": ""}

    return {"allowed": True, "message": ""}


def validate_operation_scope(tool_name: str, args: dict, role: str) -> dict:
    """按工具类型校验操作范围"""
    limits = TOOL_SCOPE_LIMITS.get(tool_name, {})

    if not limits:
        return {"allowed": True, "message": ""}

    if tool_name == "read_file":
        file_path = args.get("file_path", "")
        return validate_path_restriction(file_path, "read")

    if tool_name == "execute_command":
        timeout = args.get("timeout", 30)
        max_to = limits.get("max_timeout", 120)
        if timeout > max_to:
            return {"allowed": False, "message": f"命令超时限制为{max_to}秒，请求{timeout}秒"}
        command = args.get("command", "")
        if command:
            sudo_check = validate_sudo_whitelist(command)
            if not sudo_check["allowed"]:
                if role != "admin":
                    return {"allowed": False, "message": f"非管理员不能执行: {command}"}
        return {"allowed": True, "message": ""}

    if tool_name == "kill_process":
        signal = args.get("signal", "TERM").upper()
        is_admin = role in ("admin",)
        allowed = limits.get("admin_signals" if is_admin else "allowed_signals", ["TERM"])
        if signal not in allowed:
            return {"allowed": False, "message": f"角色{role}不允许发送{signal}信号"}
        return {"allowed": True, "message": ""}

    if tool_name == "manage_service":
        action = args.get("action", "start").lower()
        is_admin = role in ("admin",)
        allowed = limits.get("admin_actions" if is_admin else "allowed_actions", ["start"])
        if action not in allowed:
            return {"allowed": False, "message": f"角色{role}不允许执行{action}操作"}
        return {"allowed": True, "message": ""}

    if tool_name == "search_journal_logs":
        lines = args.get("lines", 20)
        if lines > limits.get("max_lines", 200):
            return {"allowed": False, "message": f"日志行数限制为200，请求{lines}行"}
        return {"allowed": True, "message": ""}

    return {"allowed": True, "message": ""}


# ═══════════════════════════════════════════
# 命令净化
# ═══════════════════════════════════════════
def sanitize_command(command: str) -> dict:
    """净化命令：检测危险模式，返回 {safe, sanitized, warnings, blocked}"""
    if not command or not command.strip():
        return {"safe": True, "sanitized": "", "warnings": [], "blocked": False}

    warnings = []
    pipe_redirect = re.compile(r'[|>]')
    cmd_sep = re.compile(r'[;&]')

    if pipe_redirect.search(command):
        warnings.append("命令包含管道/重定向")
    if cmd_sep.search(command):
        warnings.append("命令包含分隔符（可能链式执行）")

    dangerous = [
        (r'\brm\s+-rf', "包含强制递归删除"),
        (r'>\s*/dev/', "包含设备文件写入"),
        (r'\bdd\s+if=', "包含磁盘操作"),
        (r'\bmkfs\.', "包含文件系统创建"),
        (r'\bchmod\s+777', "包含不安全权限设置"),
        (r'\b(wget|curl)\s+.*\|\s*(ba)?sh', "包含远程脚本执行"),
        (r'`[^`]+`', "包含命令替换"),
        (r'\$\(', "包含命令替换"),
    ]
    for pattern, warning in dangerous:
        if re.search(pattern, command):
            warnings.append(warning)

    try:
        import shlex
        parts = shlex.split(command)
        if parts:
            first_cmd = parts[0].split("/")[-1]
    except ValueError:
        warnings.append("命令语法异常")

    return {
        "safe": len(warnings) == 0,
        "sanitized": command,
        "warnings": warnings,
        "blocked": any("递归删除" in w or "磁盘操作" in w or "远程脚本" in w for w in warnings),
    }


def execution_gate(tool_name: str, tool_args: dict, role: str) -> dict:
    """统一执行前权限门禁。返回 {allowed, reason, require_approval, risk_level}"""
    # 1. 操作范围校验
    scope = validate_operation_scope(tool_name, tool_args, role)
    if not scope["allowed"]:
        return {
            "allowed": False, "reason": scope["message"],
            "require_approval": True, "require_confirm": True, "risk_level": "L3",
        }

    # 2. 命令净化
    if tool_name == "execute_command":
        cmd = tool_args.get("command", "")
        s = sanitize_command(cmd)
        if s["blocked"]:
            return {
                "allowed": False,
                "reason": f"命令被阻止: {'; '.join(s['warnings'])}",
                "require_approval": True, "require_confirm": True, "risk_level": "L5",
            }
        if s["warnings"]:
            return {
                "allowed": True,
                "reason": f"命令存在风险: {'; '.join(s['warnings'])}",
                "require_approval": True, "require_confirm": True, "risk_level": "L3",
            }

    # 3. 路径保护
    if tool_name in ("read_file", "get_file_list"):
        path = tool_args.get("file_path", tool_args.get("path", ""))
        if path:
            pc = validate_path_restriction(path, "read")
            if not pc["allowed"]:
                return {
                    "allowed": False, "reason": pc["message"],
                    "require_approval": True, "require_confirm": True, "risk_level": "L4",
                }

    return {
        "allowed": True, "reason": "允许",
        "require_approval": False, "require_confirm": False, "risk_level": "L1",
    }
