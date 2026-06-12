"""
安全校验引擎 — 命令分析、风险分级、黑名单、绕过检测、路径保护

五层分析:
  L1: 命令分组匹配 (GROUP_CONFIG)
  L2: 黑名单硬阻断 (BLOCKED_PATTERNS)
  L3: 参数风险分析 (DANGEROUS_ARGS)
  L4: Shell注入/绕过检测 (BYPASS_PATTERNS)
  L5: 路径保护验证 (PATH_PROTECTIONS)
"""

import re
from enum import Enum
from typing import Dict, List, Tuple, Optional


class RiskLevel(Enum):
    SAFE = "L1"
    LOW = "L2"
    MEDIUM = "L3"
    HIGH = "L4"
    FATAL = "L5"


class CommandGroup(Enum):
    SYSTEM_MONITOR = "system_monitor"
    PROCESS_MANAGEMENT = "process_management"
    NETWORK_MANAGEMENT = "network_management"
    FILE_MANAGEMENT = "file_management"
    DISK_MANAGEMENT = "disk_management"
    USER_MANAGEMENT = "user_management"
    SERVICE_CONFIG = "service_config"
    LOG_AUDIT = "log_audit"
    SYSTEM_CTL = "system_ctl"
    PACKAGE_MGMT = "package_mgmt"
    FIREWALL = "firewall"
    SECURITY = "security"


# ═══════════════════════════════════════════
# L1: 命令分组 — 更全面的命令覆盖
# ═══════════════════════════════════════════
GROUP_CONFIG: Dict[CommandGroup, Dict] = {
    CommandGroup.SYSTEM_MONITOR: {
        "name": "系统监控",
        "commands": [
            "top", "free", "df", "uptime", "vmstat", "iostat", "mpstat",
            "sar", "dstat", "nmon", "glances", "htop",
        ],
        "risk_level": RiskLevel.SAFE,
        "require_approval": False,
        "require_confirm": False,
    },
    CommandGroup.LOG_AUDIT: {
        "name": "日志审计",
        "commands": [
            "journalctl", "dmesg", "tail", "grep", "cat", "head", "less",
            "more", "zcat", "zgrep", "awk", "sed", "cut", "sort", "uniq",
            "wc", "find", "locate", "which", "whereis", "file", "stat",
            "ls", "pwd", "echo", "date", "hostname", "uname",
            "lpstat", "lpoptions", "lpinfo",
        ],
        "risk_level": RiskLevel.SAFE,
        "require_approval": False,
        "require_confirm": False,
        "special_rules": {
            "journalctl": {
                "args_match": r"--vacuum",
                "require_confirm": True,
                "require_approval": True,
                "risk_level": RiskLevel.MEDIUM,
            },
        },
    },
    CommandGroup.PROCESS_MANAGEMENT: {
        "name": "进程管理",
        "commands": ["ps", "kill", "pkill", "pgrep", "pidof", "killall",
                      "renice", "nice", "nohup", "disown"],
        "risk_level": RiskLevel.LOW,
        "require_approval": False,
        "require_confirm": True,
        "special_rules": {
            "kill": {"args_match": r"-(9|KILL|SIGKILL)", "risk_level": RiskLevel.HIGH, "require_approval": True},
            "pkill": {"args_match": r"-(9|KILL|SIGKILL)", "risk_level": RiskLevel.HIGH, "require_approval": True},
            "killall": {"args_match": r"-(9|KILL|SIGKILL)", "risk_level": RiskLevel.HIGH, "require_approval": True},
        },
    },
    CommandGroup.NETWORK_MANAGEMENT: {
        "name": "网络管理",
        "commands": ["netstat", "ss", "ip", "ping", "traceroute", "nslookup",
                      "dig", "host", "arp", "route", "ifconfig", "iwconfig",
                      "ethtool", "nmcli", "nmap", "tcpdump"],
        "risk_level": RiskLevel.MEDIUM,
        "require_approval": False,
        "require_confirm": True,
        "special_rules": {
            "ip": {"args_match": r"(route|link|addr)\s+(add|del|set|change)", "require_approval": True},
            "route": {"args_match": r"(add|del)", "require_approval": True},
            "ifconfig": {"args_match": r"(up|down)", "require_approval": True},
        },
    },
    CommandGroup.FILE_MANAGEMENT: {
        "name": "文件管理",
        "commands": ["cp", "mv", "rm", "chmod", "chown", "mkdir",
                      "rmdir", "touch", "ln", "chattr", "lsattr"],
        "risk_level": RiskLevel.MEDIUM,
        "require_approval": False,
        "require_confirm": True,
        "special_rules": {
            "rm": {"args_match": r"-(r|recursive|f|force)", "risk_level": RiskLevel.HIGH, "require_approval": True},
            "chmod": {"default_approval": True, "risk_level": RiskLevel.HIGH},
            "chown": {"default_approval": True, "risk_level": RiskLevel.HIGH},
            "chattr": {"default_approval": True, "risk_level": RiskLevel.HIGH},
        },
    },
    CommandGroup.DISK_MANAGEMENT: {
        "name": "磁盘管理",
        "commands": ["fdisk", "mkfs", "mkfs.ext2", "mkfs.ext3", "mkfs.ext4",
                      "mkfs.xfs", "mkfs.btrfs", "mount", "umount", "parted",
                      "dd", "fsck", "e2fsck", "xfs_repair", "mkswap",
                      "resize2fs", "lvm", "pvcreate", "vgcreate", "lvcreate",
                      "mdadm"],
        "risk_level": RiskLevel.HIGH,
        "require_approval": True,
        "require_confirm": True,
        "special_rules": {
            "mkfs": {"blocked": True},
            "mkfs.ext2": {"blocked": True},
            "mkfs.ext3": {"blocked": True},
            "mkfs.ext4": {"blocked": True},
            "mkfs.xfs": {"blocked": True},
            "mkfs.btrfs": {"blocked": True},
            "fdisk": {"blocked": True},
            "parted": {"blocked": True},
            "dd": {"blocked": True, "block_message": "dd命令涉及裸磁盘写入，已被安全策略禁止"},
            "mkswap": {"blocked": True},
            "pvcreate": {"blocked": True, "block_message": "LVM创建操作被禁止"},
            "vgcreate": {"blocked": True},
            "lvcreate": {"blocked": True},
            "mdadm": {"blocked": True, "block_message": "RAID管理操作被禁止"},
        },
    },
    CommandGroup.USER_MANAGEMENT: {
        "name": "用户管理",
        "commands": ["useradd", "userdel", "usermod", "passwd", "visudo",
                      "groupadd", "groupdel", "groupmod", "chsh", "chfn"],
        "risk_level": RiskLevel.FATAL,
        "require_approval": True,
        "require_confirm": True,
    },
    CommandGroup.SERVICE_CONFIG: {
        "name": "服务配置",
        "commands": ["systemctl", "service", "chkconfig", "update-rc.d"],
        "risk_level": RiskLevel.MEDIUM,
        "require_approval": False,
        "require_confirm": True,
        "special_rules": {
            "systemctl": {
                "args_match": r"(start|stop|restart|reload|enable|disable|mask|unmask)",
                "require_approval": True,
                "risk_level": RiskLevel.HIGH,
                "sub_check": {
                    r"(stop|disable|mask)\s+(sshd|firewalld|auditd|kylinops)": {
                        "blocked": True, "block_message": "禁止停止关键安全服务",
                    },
                },
            },
        },
    },
    CommandGroup.PACKAGE_MGMT: {
        "name": "软件包管理",
        "commands": ["yum", "dnf", "apt", "apt-get", "rpm", "dpkg", "pip", "pip3", "npm"],
        "risk_level": RiskLevel.HIGH,
        "require_approval": True,
        "require_confirm": True,
        "special_rules": {
            "yum": {"args_match": r"(install|remove|erase|update|upgrade|reinstall)", "require_approval": True},
            "dnf": {"args_match": r"(install|remove|erase|update|upgrade)", "require_approval": True},
            "apt": {"args_match": r"(install|remove|purge|update|upgrade|dist-upgrade)", "require_approval": True},
            "apt-get": {"args_match": r"(install|remove|purge|update|upgrade|dist-upgrade)", "require_approval": True},
            "pip": {"args_match": r"(install|uninstall)", "require_approval": True},
            "pip3": {"args_match": r"(install|uninstall)", "require_approval": True},
            "rpm": {
                "args_match": r"(-e|--erase|-U|--upgrade|-F|--freshen|--reinstall|-i|--install|-ivh)",
                "require_approval": True,
            },
        },
    },
    CommandGroup.FIREWALL: {
        "name": "防火墙管理",
        "commands": ["iptables", "ip6tables", "firewall-cmd", "ufw", "nft"],
        "risk_level": RiskLevel.FATAL,
        "require_approval": True,
        "require_confirm": True,
        "special_rules": {
            "iptables": {
                "args_match": r"-(A|I|D|F|X|P|N)",
                "risk_level": RiskLevel.FATAL,
                "require_approval": True,
                "sub_check": {
                    r"-F|--flush": {"blocked": True, "block_message": "禁止清空防火墙规则"},
                    r"-P\s+ACCEPT": {"blocked": True, "block_message": "禁止将默认策略设为ACCEPT"},
                },
            },
            "firewall-cmd": {
                "args_match": r"--(permanent|add-rich-rule|remove-rich-rule|change)",
                "require_approval": True,
            },
        },
    },
    CommandGroup.SECURITY: {
        "name": "安全相关",
        "commands": ["setenforce", "semanage", "auditctl", "ausearch",
                      "setfacl", "getfacl", "sestatus"],
        "risk_level": RiskLevel.FATAL,
        "require_approval": True,
        "require_confirm": True,
        "special_rules": {
            "setenforce": {"blocked": True, "block_message": "禁止修改SELinux状态"},
            "semanage": {"blocked": True, "block_message": "禁止修改SELinux策略"},
        },
    },
}


# ═══════════════════════════════════════════
# L2: 黑名单 — 绝对禁止的命令/模式
# ═══════════════════════════════════════════
BLOCKED_COMMANDS = [
    # 系统破坏
    "shutdown", "reboot", "halt", "poweroff", "init",
    # 磁盘破坏
    "dd", "mkfs", "fdisk", "parted", "wipefs", "sfdisk",
    "mkswap", "pvcreate", "vgcreate", "lvcreate",
    # 内核/模块破坏
    "modprobe", "rmmod", "insmod", "depmod",
    # 引导破坏
    "grub-install", "grub-mkconfig",
    # 安全绕过
    "setenforce",
]


BLOCKED_PATTERNS: List[Tuple[object, str, bool]] = [
    # (正则, 说明, 直接阻止)
    (re.compile(r'\brm\s+-rf\s*/'), "递归删除根目录", True),
    (re.compile(r'\brm\s+-rf\s+/(bin|boot|dev|etc|lib|proc|root|sbin|sys|usr|var)\b'), "删除系统关键目录", True),
    (re.compile(r'>\s*/dev/(sd|hd|nvme|vd|xvd|mmcblk)'), "写入裸设备", True),
    (re.compile(r'\bdd\s+if=/dev/zero\s+of=/dev/(sd|hd|nvme|vd)'), "磁盘清零", True),
    (re.compile(r'\bdd\s+if=/dev/urandom\s+of=/dev/(sd|hd|nvme|vd)'), "磁盘随机覆写", True),
    (re.compile(r':\(\)\s*\{\s*:\|:&\s*\}\s*;:'), "Fork炸弹", True),
    (re.compile(r'chmod\s+(-R\s+)?777\s+/'), "递归777设置", False),
    (re.compile(r'chmod\s+(-R\s+)?777\s+/(bin|boot|dev|etc|lib)'), "系统目录777", True),
    (re.compile(r'chown\s+(-R\s+)?\w+:\w+\s+/'), "递归修改系统文件所有者", False),
    (re.compile(r'\b(wget|curl)\s+.*\|\s*(ba)?sh'), "远程脚本下载执行", True),
    (re.compile(r'\b(wget|curl)\s+.*-O\s+.*\|\s*(ba)?sh'), "远程脚本下载执行", True),
    (re.compile(r'\b>\/etc\/(passwd|shadow|sudoers|group|hosts)'), "覆写系统关键文件", True),
    (re.compile(r'\becho\s+.*>>\s*/etc/(passwd|shadow|sudoers)'), "追加系统关键文件", True),
]


# ═══════════════════════════════════════════
# L3: 高危参数检测
# ═══════════════════════════════════════════
DANGEROUS_ARGS: List[Tuple[object, str]] = [
    (re.compile(r'/\*'), "通配符删除"),
    (re.compile(r'--no-preserve-root'), "跳过根保护"),
    (re.compile(r'chmod\s+777'), "不安全权限"),
    (re.compile(r'chmod\s+[0-7]*7[0-7]*7\s+/'), "系统级宽泛权限"),
    (re.compile(r'>/\w'), "输出重定向(可能覆盖文件)"),
    (re.compile(r'>>\s*/etc/'), "追加系统配置"),
    (re.compile(r'\|\s*(ba)?sh\b'), "管道到shell执行"),
    (re.compile(r'\|\s*(python|perl|ruby|php)\b'), "管道到解释器"),
    (re.compile(r'\$\{.*\}'), "变量展开(可能注入)"),
    (re.compile(r'`[^`]+`'), "命令替换(反引号)"),
    (re.compile(r'\$\([^)]+\)'), "命令替换($())"),
    (re.compile(r'\.\./\.\./\.\.'), "深层目录遍历"),
    (re.compile(r'/etc/(passwd|shadow|sudoers|hosts\.(allow|deny))'), "访问安全文件"),
    (re.compile(r'/root/\.ssh'), "访问SSH密钥"),
]


# ═══════════════════════════════════════════
# L4: 绕过检测
# ═══════════════════════════════════════════
BYPASS_PATTERNS: List[Tuple[object, str]] = [
    # 编码绕过
    (re.compile(r'\\x[0-9a-f]{2}'), "十六进制编码"),
    (re.compile(r'\\u[0-9a-f]{4}'), "Unicode编码"),
    (re.compile(r'\\[0-7]{3}'), "八进制编码"),
    (re.compile(r'base64\s+(-d|--decode)'), "Base64解码执行"),
    # 命令别名绕过
    (re.compile(r'(?i)\b(?:command|builtin|exec)\s+-'), "内置命令包装"),
    (re.compile(r'(?i)\beval\s+'), "eval执行"),
    (re.compile(r'(?i)\bsource\s+/'), "source执行文件"),
    # 空格绕过
    (re.compile(r'\$\{IFS\}'), "IFS空格绕过"),
    (re.compile(r'<\([^)]+\)'), "进程替换"),
    # 历史命令操作
    (re.compile(r'(?i)history\s+-c'), "清除命令历史"),
    (re.compile(r'(?i)unset\s+HISTFILE'), "禁用历史记录"),
    # 时间/条件绕过
    (re.compile(r'(?i)\b(at|batch)\s+'), "延迟执行"),
    (re.compile(r'(?i)nohup\s+'), "后台持续执行"),
]


# ═══════════════════════════════════════════
# L5: 路径保护
# ═══════════════════════════════════════════
PATH_PROTECTIONS = {
    "/etc/shadow": "系统密码文件，禁止任何操作",
    "/etc/shadow-": "系统密码备份文件",
    "/root/.ssh": "SSH密钥目录，禁止访问",
    "/root/.ssh/authorized_keys": "SSH授权密钥，禁止修改",
    "/boot": "系统引导分区，禁止写入",
    "/etc/sudoers": "sudo配置文件，禁止修改",
    "/etc/sudoers.d": "sudo配置目录，禁止修改",
    "/etc/passwd": "系统用户文件，禁止直接修改",
    "/etc/group": "系统组文件，禁止直接修改",
    "/etc/gshadow": "系统组密码文件",
    "/etc/hosts.allow": "TCP Wrapper允许列表",
    "/etc/hosts.deny": "TCP Wrapper拒绝列表",
    "/etc/ssh/sshd_config": "SSH服务配置",
    "/etc/pam.d": "PAM认证配置目录",
    "/etc/audit": "审计配置目录",
    "/etc/selinux": "SELinux配置目录",
    "/var/log/audit": "审计日志目录",
}

SUDO_WHITELIST = {
    "systemctl", "journalctl", "ss", "netstat", "df", "du",
    "ps", "top", "free", "uptime", "hostnamectl", "timedatectl",
    "lsblk", "blkid", "lsof", "ip", "ping", "traceroute",
    "cat", "head", "tail", "less", "grep", "awk", "sed",
    "find", "ls", "stat", "file", "wc", "sort", "uniq",
    "cut", "tr", "tee", "diff", "expr", "test",
}


# ═══════════════════════════════════════════
# 分析函数
# ═══════════════════════════════════════════
def max_risk(a: str, b: str) -> str:
    levels = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}
    return b if levels.get(b, 0) > levels.get(a, 0) else a


def parse_command(command: str) -> Tuple[str, List[str], Dict]:
    parts = command.strip().split()
    if not parts:
        return "", [], {}
    cmd_name = parts[0]
    args = parts[1:]
    flags = {}
    for i, arg in enumerate(args):
        if arg.startswith("--"):
            key = arg[2:]
            flags[key] = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("-") else True
        elif arg.startswith("-") and len(arg) > 1:
            for flag in arg[1:]:
                flags[flag] = True
    return cmd_name, args, flags


def get_command_group(cmd_name: str) -> Optional[CommandGroup]:
    for group, config in GROUP_CONFIG.items():
        if cmd_name in config["commands"]:
            return group
    return None


def _check_blacklist(command: str) -> Optional[dict]:
    """L2: 黑名单检查。只返回硬阻断结果，非阻断警告走 findings"""
    cmd_name = command.strip().split()[0] if command.strip() else ""
    cmd_base = cmd_name.split("/")[-1]
    if cmd_base in BLOCKED_COMMANDS:
        return {
            "blocked": True,
            "block_message": f"命令 '{cmd_base}' 被系统安全策略禁止",
            "risk_level": RiskLevel.FATAL.value,
        }
    return None


def _check_blacklist_warnings(command: str) -> List[dict]:
    """L2b: 黑名单模式警告（非阻断）"""
    warnings = []
    for pattern, description, hard_block in BLOCKED_PATTERNS:
        if pattern.search(command):
            if hard_block:
                return [{"type": "blocked", "description": description, "block": True}]
            warnings.append({"type": "dangerous_pattern", "description": description})
    return warnings


def _check_dangerous_args(command: str) -> List[dict]:
    """L3: 高危参数检测"""
    findings = []
    for pattern, description in DANGEROUS_ARGS:
        if pattern.search(command):
            findings.append({"type": "dangerous_arg", "description": description})
    return findings


def _check_bypass(command: str) -> List[dict]:
    """L4: 绕过检测"""
    findings = []
    for pattern, description in BYPASS_PATTERNS:
        if pattern.search(command):
            findings.append({"type": "bypass_attempt", "description": description})
    return findings


def analyze_command(command: str) -> Dict:
    """
    综合分析命令安全风险。

    返回: {success, command, cmd_name, risk_level, require_approval,
           require_confirm, blocked, block_message, group, group_name,
           reason, findings}
    """
    cmd_name, args, flags = parse_command(command)

    base = {
        "success": True,
        "command": command,
        "cmd_name": cmd_name,
        "args": args,
        "flags": flags,
        "group": None,
        "group_name": "未知",
        "risk_level": RiskLevel.SAFE.value,
        "require_approval": False,
        "require_confirm": False,
        "blocked": False,
        "block_message": None,
        "reason": "",
        "findings": [],
    }

    if not cmd_name:
        base["success"] = False
        base["reason"] = "空命令"
        return base

    # RPM/DNF 只读查询（L1 直接执行）
    if cmd_name == "rpm" and re.search(r"(^|\s)(-q|--query|-qa|-qi|-ql|-qf|-qR)\b", command.strip(), re.I):
        base["group"] = CommandGroup.PACKAGE_MGMT.value
        base["group_name"] = GROUP_CONFIG[CommandGroup.PACKAGE_MGMT]["name"]
        base["risk_level"] = RiskLevel.SAFE.value
        base["require_approval"] = False
        base["require_confirm"] = False
        base["reason"] = "RPM 包查询（只读）"
        return base
    if cmd_name in ("dnf", "yum") and re.search(r"\b(list|info|provides|search|history)\b", command, re.I):
        base["group"] = CommandGroup.PACKAGE_MGMT.value
        base["group_name"] = GROUP_CONFIG[CommandGroup.PACKAGE_MGMT]["name"]
        base["risk_level"] = RiskLevel.SAFE.value
        base["require_approval"] = False
        base["require_confirm"] = False
        base["reason"] = "包管理器只读查询"
        return base

    # L2: 黑名单（硬阻断）
    blacklist_result = _check_blacklist(command)
    if blacklist_result:
        base.update(blacklist_result)
        return base

    # L2b: 黑名单模式警告
    bl_warnings = _check_blacklist_warnings(command)
    for w in bl_warnings:
        if w.get("block"):
            base["blocked"] = True
            base["block_message"] = f"检测到危险模式: {w['description']}"
            base["risk_level"] = RiskLevel.FATAL.value
            return base
        base["findings"].append(w)

    # L4: 绕过检测
    bypass = _check_bypass(command)
    for b in bypass:
        base["findings"].append(b)
    if bypass:
        base["require_approval"] = True
        base["require_confirm"] = True
        base["risk_level"] = max_risk(base["risk_level"], RiskLevel.HIGH.value)

    # L3: 高危参数
    dangerous = _check_dangerous_args(command)
    for d in dangerous:
        base["findings"].append(d)
    # 访问安全文件 → 至少需确认
    if any("安全文件" in d.get("description", "") for d in dangerous):
        base["require_confirm"] = True

    # 时间同步：只读查询（L1 直接执行）
    _TIME_READONLY = (
        (re.compile(r"^timedatectl\s+(status|show|timesync-status|show-timesync-status)\b", re.I), "查看时间同步状态"),
        (re.compile(r"^chronyc\s+(tracking|sources|sourcestats|activity)\b", re.I), "查看 chrony 状态"),
        (re.compile(r"^systemctl\s+status\s+chronyd?\b", re.I), "查看 chronyd 服务状态"),
        (re.compile(r"^date(\s|$)", re.I), "查看当前系统时间"),
    )
    for pattern, reason in _TIME_READONLY:
        if pattern.search(command.strip()):
            base["risk_level"] = RiskLevel.SAFE.value
            base["require_approval"] = False
            base["require_confirm"] = False
            base["reason"] = reason
            return base

    # 网络只读查询（L1 直接执行，避免 cat /proc/net/dev 等被误判为 L4）
    _NETWORK_READONLY = (
        (re.compile(r"^cat\s+/proc/net/(dev|snmp|softnet_stat)\b", re.I), "查看网络接口统计"),
        (re.compile(r"^ip\s+-s\s+(link|addr)\b", re.I), "查看网卡流量统计"),
        (re.compile(r"^ip\s+link\s+show\b", re.I), "查看网络接口状态"),
        (re.compile(r"^cat\s+/sys/class/net/[^/\s]+/statistics/\w+\b", re.I), "读取网卡计数器"),
        (re.compile(r"^sar\s+-n\s+(DEV|EDEV)\b", re.I), "查看网络吞吐统计"),
        (re.compile(r"^ss\s+-s\b", re.I), "查看网络连接摘要"),
    )
    for pattern, reason in _NETWORK_READONLY:
        if pattern.search(command.strip()):
            base["risk_level"] = RiskLevel.SAFE.value
            base["require_approval"] = False
            base["require_confirm"] = False
            base["reason"] = reason
            return base

    # 时间同步：写操作
    if re.search(r"^timedatectl\s+set-ntp\s+(true|1)\b", command.strip(), re.I):
        base["risk_level"] = RiskLevel.MEDIUM.value
        base["require_approval"] = False
        base["require_confirm"] = True
        base["reason"] = "启用 NTP 时间同步（需用户确认）"
        return base
    if re.search(r"^chronyc\s+(-a\s+)?makestep\b", command.strip(), re.I):
        base["risk_level"] = RiskLevel.MEDIUM.value
        base["require_approval"] = False
        base["require_confirm"] = True
        base["reason"] = "强制 chrony 对时（需用户确认）"
        return base
    if re.search(r"^timedatectl\s+set-time\b", command.strip(), re.I):
        base["risk_level"] = RiskLevel.HIGH.value
        base["require_approval"] = True
        base["require_confirm"] = True
        base["reason"] = "手动设置系统时间（高风险）"
        return base

    # L1: 命令分组（不覆盖已有的高风险标记）
    group = get_command_group(cmd_name)
    if group is None:
        base["require_approval"] = max(base["require_approval"], True)
        base["require_confirm"] = max(base["require_confirm"], True)
        base["reason"] = "未知命令，默认中等风险"
        return base

    config = GROUP_CONFIG[group]
    base["group"] = group.value
    base["group_name"] = config["name"]
    base["risk_level"] = max_risk(base["risk_level"], config["risk_level"].value)
    # 不覆盖已有的审批/确认要求（前面的L2/L3/L4可能已设置了更高的要求）
    base["require_approval"] = base["require_approval"] or config["require_approval"]
    base["require_confirm"] = base["require_confirm"] or config["require_confirm"]
    base["reason"] = config.get("description", "")

    # 特殊规则
    special = config.get("special_rules", {}).get(cmd_name, {})

    if special.get("blocked"):
        base["blocked"] = True
        base["block_message"] = special.get("block_message", f"命令 '{cmd_name}' 被禁止")
        base["risk_level"] = RiskLevel.FATAL.value
        return base

    # 参数匹配
    args_match = special.get("args_match")
    if args_match:
        args_str = " ".join(args)
        if re.search(args_match, args_str):
            if "risk_level" in special:
                base["risk_level"] = special["risk_level"].value if isinstance(special["risk_level"], RiskLevel) else special["risk_level"]
            if "require_approval" in special:
                base["require_approval"] = bool(special["require_approval"])
            if "require_confirm" in special:
                base["require_confirm"] = bool(special["require_confirm"])
            # 子规则检查
            for sub_pattern, sub_rule in special.get("sub_check", {}).items():
                if re.search(sub_pattern, args_str):
                    if sub_rule.get("blocked"):
                        base["blocked"] = True
                        base["block_message"] = sub_rule.get("block_message", "子规则阻止")
                        base["risk_level"] = RiskLevel.FATAL.value
                        return base

    if special.get("default_approval"):
        base["require_approval"] = True

    # 包管理：clean/autoclean/autoremove 降为 L2 确认（非 L4 审批）
    if cmd_name in ("apt-get", "apt") and re.search(r"\b(clean|autoclean|autoremove)\b", command, re.I):
        base["require_approval"] = False
        base["require_confirm"] = True
        base["risk_level"] = RiskLevel.LOW.value
        base["reason"] = "APT 缓存清理（低风险，需用户确认）"
    if cmd_name in ("dnf", "yum") and re.search(r"\bclean\b", command, re.I):
        base["require_approval"] = False
        base["require_confirm"] = True
        base["risk_level"] = RiskLevel.LOW.value
        base["reason"] = "DNF/YUM 缓存清理（低风险，需用户确认）"

    # L5: 路径保护 — 从命令参数提取路径并校验
    path_findings = _check_path_protections(command)
    for pf in path_findings:
        base["findings"].append(pf)
    if path_findings:
        if any(pf.get("blocked") for pf in path_findings):
            base["blocked"] = True
            base["block_message"] = path_findings[0].get("message", "受保护路径，禁止操作")
            base["risk_level"] = RiskLevel.FATAL.value
            return base
        base["require_approval"] = True
        base["require_confirm"] = True
        base["risk_level"] = max_risk(base["risk_level"], RiskLevel.HIGH.value)
        base["reason"] = base["reason"] or "涉及受保护路径"

    return base


def _extract_paths_from_command(command: str) -> List[str]:
    """从命令中提取可能的目标路径。"""
    paths = []
    # rm/chmod/chown/cat/echo > 等后的路径
    for m in re.finditer(r"(?:^|\s)(/(?:[\w.-]+/)*[\w.-]+)", command):
        paths.append(m.group(1))
    for m in re.finditer(r"(>>?)\s*(/(?:[\w.-]+/)*[\w.-]+)", command):
        paths.append(m.group(2))
    return paths


def _check_path_protections(command: str, extra_whitelist: List[str] = None) -> List[dict]:
    """L5 路径保护校验。"""
    findings = []
    write_verbs = re.compile(r"\b(rm|mv|chmod|chown|chattr|dd|mkfs|truncate|shred)\b", re.I)
    if not write_verbs.search(command):
        return findings

    for path in _extract_paths_from_command(command):
        result = validate_path(path)
        if not result["safe"]:
            findings.append({
                "type": "path_protection",
                "path": path,
                "message": result["message"],
                "blocked": True,
            })
    return findings


def get_risk_level_info(risk_level: str) -> Dict:
    level_info = {
        RiskLevel.SAFE.value: {"name": "安全", "color": "🟢", "description": "只读操作，无风险", "action": "直接执行"},
        RiskLevel.LOW.value: {"name": "低风险", "color": "🟡", "description": "低风险操作，可逆", "action": "确认后执行"},
        RiskLevel.MEDIUM.value: {"name": "中等风险", "color": "🟠", "description": "可能影响系统状态", "action": "需管理员审批"},
        RiskLevel.HIGH.value: {"name": "高风险", "color": "🟠→🔴", "description": "可能造成数据丢失或服务中断", "action": "需管理员审批"},
        RiskLevel.FATAL.value: {"name": "致命风险", "color": "🔴", "description": "高危操作，可能导致系统崩溃", "action": "需管理员审批/禁止"},
    }
    return level_info.get(risk_level, {"name": "未知", "color": "⚪", "description": "未知风险", "action": "需审批"})


def validate_path(path: str) -> dict:
    if not path or not path.strip():
        return {"safe": True, "message": ""}
    normalized = path.strip()
    for protected_path, reason in PATH_PROTECTIONS.items():
        if normalized == protected_path or normalized.startswith(protected_path + "/"):
            return {"safe": False, "message": reason}
    return {"safe": True, "message": ""}


def check_sudo_command(command: str) -> dict:
    if not command or not command.strip():
        return {"allowed": True, "message": ""}
    parts = command.strip().split()
    cmd_name = parts[0] if parts else ""
    cmd_base = cmd_name.split("/")[-1] if "/" in cmd_name else cmd_name
    if cmd_base in SUDO_WHITELIST:
        return {"allowed": True, "command": cmd_base, "message": "在白名单中"}
    return {"allowed": False, "command": cmd_base, "message": f"'{cmd_base}' 不在sudo白名单中"}
