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


GROUP_CONFIG: Dict[CommandGroup, Dict] = {
    CommandGroup.SYSTEM_MONITOR: {
        "name": "系统监控",
        "commands": ["top", "free", "df", "uptime", "vmstat", "iostat", "mpstat"],
        "risk_level": RiskLevel.SAFE,
        "require_approval": False,
        "require_confirm": False,
        "description": "只读操作，直接执行",
    },
    CommandGroup.PROCESS_MANAGEMENT: {
        "name": "进程管理",
        "commands": ["ps", "kill", "systemctl", "pkill", "pgrep"],
        "risk_level": RiskLevel.LOW,
        "require_approval": False,
        "require_confirm": True,
        "description": "kill -9 需确认，systemctl 需审批",
        "special_rules": {
            "kill": {"args_contain": ["-9"], "require_approval": True},
            "systemctl": {"args_contain": ["start", "stop", "restart", "reload"], "require_approval": True},
        },
    },
    CommandGroup.NETWORK_MANAGEMENT: {
        "name": "网络管理",
        "commands": ["netstat", "ss", "ip", "ping", "iptables", "curl", "wget", "nc"],
        "risk_level": RiskLevel.MEDIUM,
        "require_approval": False,
        "require_confirm": True,
        "description": "查询放行，iptables 修改需审批",
        "special_rules": {
            "iptables": {"default_approval": True},
            "ip": {"args_contain": ["route", "link", "addr"], "require_approval": True},
        },
    },
    CommandGroup.FILE_MANAGEMENT: {
        "name": "文件管理",
        "commands": ["ls", "cat", "cp", "mv", "rm", "chmod", "chown", "mkdir", "rmdir", "touch"],
        "risk_level": RiskLevel.MEDIUM,
        "require_approval": False,
        "require_confirm": True,
        "description": "查询放行，rm/chmod 高风险",
        "special_rules": {
            "rm": {"args_contain": ["-rf", "--recursive", "--force"], "risk_level": RiskLevel.HIGH, "require_approval": True},
            "chmod": {"default_approval": True},
            "chown": {"default_approval": True},
        },
    },
    CommandGroup.DISK_MANAGEMENT: {
        "name": "磁盘管理",
        "commands": ["fdisk", "mkfs", "mkfs.ext2", "mkfs.ext3", "mkfs.ext4", "mkfs.xfs", "mkfs.btrfs", "mount", "umount", "du", "df", "parted"],
        "risk_level": RiskLevel.HIGH,
        "require_approval": True,
        "require_confirm": True,
        "description": "mkfs 禁止，mount 需审批",
        "special_rules": {
            "mkfs": {"blocked": True, "block_message": "mkfs 命令禁止执行"},
            "mkfs.ext2": {"blocked": True, "block_message": "mkfs 命令禁止执行"},
            "mkfs.ext3": {"blocked": True, "block_message": "mkfs 命令禁止执行"},
            "mkfs.ext4": {"blocked": True, "block_message": "mkfs 命令禁止执行"},
            "mkfs.xfs": {"blocked": True, "block_message": "mkfs 命令禁止执行"},
            "mkfs.btrfs": {"blocked": True, "block_message": "mkfs 命令禁止执行"},
            "fdisk": {"blocked": True, "block_message": "fdisk 命令禁止执行"},
            "parted": {"blocked": True, "block_message": "parted 命令禁止执行"},
        },
    },
    CommandGroup.USER_MANAGEMENT: {
        "name": "用户管理",
        "commands": ["useradd", "userdel", "usermod", "passwd", "visudo", "groupadd", "groupdel", "groupmod"],
        "risk_level": RiskLevel.FATAL,
        "require_approval": True,
        "require_confirm": True,
        "description": "全部需审批",
    },
    CommandGroup.SERVICE_CONFIG: {
        "name": "服务配置",
        "commands": ["yum", "rpm", "crontab", "sysctl", "systemctl", "chkconfig"],
        "risk_level": RiskLevel.FATAL,
        "require_approval": True,
        "require_confirm": True,
        "description": "全部需审批",
        "special_rules": {
            "yum": {"args_contain": ["install", "remove", "update"], "require_approval": True},
            "rpm": {"default_approval": True},
            "crontab": {"default_approval": True},
            "sysctl": {"default_approval": True},
        },
    },
    CommandGroup.LOG_AUDIT: {
        "name": "日志审计",
        "commands": ["journalctl", "dmesg", "tail", "grep", "cat"],
        "risk_level": RiskLevel.SAFE,
        "require_approval": False,
        "require_confirm": False,
        "description": "只读操作，直接执行",
    },
}


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
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                flags[key] = args[i + 1]
            else:
                flags[key] = True
        elif arg.startswith("-") and len(arg) > 1:
            for flag in arg[1:]:
                flags[flag] = True
    
    return cmd_name, args, flags


def get_command_group(cmd_name: str) -> Optional[CommandGroup]:
    for group, config in GROUP_CONFIG.items():
        if cmd_name in config["commands"]:
            return group
    return None


def analyze_command(command: str) -> Dict:
    cmd_name, args, flags = parse_command(command)
    
    if not cmd_name:
        return {
            "success": False,
            "error": "空命令",
            "command": command,
            "cmd_name": "",
            "group": None,
            "risk_level": RiskLevel.SAFE.value,
            "require_approval": False,
            "require_confirm": False,
            "blocked": False,
            "block_message": None,
        }
    
    group = get_command_group(cmd_name)
    
    if group is None:
        return {
            "success": True,
            "command": command,
            "cmd_name": cmd_name,
            "args": args,
            "flags": flags,
            "group": None,
            "group_name": "未知",
            "risk_level": RiskLevel.MEDIUM.value,
            "require_approval": True,
            "require_confirm": True,
            "blocked": False,
            "block_message": None,
            "reason": "未知命令，默认中等风险",
        }
    
    config = GROUP_CONFIG[group]
    result = {
        "success": True,
        "command": command,
        "cmd_name": cmd_name,
        "args": args,
        "flags": flags,
        "group": group.value,
        "group_name": config["name"],
        "risk_level": config["risk_level"].value,
        "require_approval": config["require_approval"],
        "require_confirm": config["require_confirm"],
        "blocked": False,
        "block_message": None,
        "reason": config["description"],
    }
    
    special_rules = config.get("special_rules", {})
    if cmd_name in special_rules:
        rules = special_rules[cmd_name]
        
        if rules.get("blocked", False):
            result["blocked"] = True
            result["block_message"] = rules.get("block_message", "此命令被禁止")
            return result
        
        args_contain = rules.get("args_contain", [])
        if args_contain:
            for arg in args_contain:
                if arg in args:
                    if "risk_level" in rules:
                        result["risk_level"] = rules["risk_level"].value
                    if rules.get("require_approval", False):
                        result["require_approval"] = True
                    break
        
        if rules.get("default_approval", False):
            result["require_approval"] = True
    
    return result


def get_risk_level_info(risk_level: str) -> Dict:
    level_info = {
        RiskLevel.SAFE.value: {
            "name": "安全",
            "color": "🟢",
            "description": "只读操作，无风险",
            "action": "直接执行",
        },
        RiskLevel.LOW.value: {
            "name": "低风险",
            "color": "🟡",
            "description": "低风险操作",
            "action": "确认后执行",
        },
        RiskLevel.MEDIUM.value: {
            "name": "中等风险",
            "color": "🟡~🟠",
            "description": "可能影响系统状态",
            "action": "需确认",
        },
        RiskLevel.HIGH.value: {
            "name": "高风险",
            "color": "🟠",
            "description": "可能造成数据丢失或服务中断",
            "action": "需审批",
        },
        RiskLevel.FATAL.value: {
            "name": "致命风险",
            "color": "🔴",
            "description": "高危操作，可能导致系统崩溃",
            "action": "需审批",
        },
    }
    return level_info.get(risk_level, {"name": "未知", "color": "⚪", "description": "未知风险", "action": "需审批"})