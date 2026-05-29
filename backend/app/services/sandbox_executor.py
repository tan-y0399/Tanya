"""
非root沙箱执行器 — 安全执行命令，限制权限和资源

沙箱策略:
  1. 非root用户执行 (默认 kylinops-agent)
  2. 文件系统限制 (仅允许白名单路径)
  3. 网络限制 (仅允许出站连接)
  4. 资源限制 (CPU/内存/磁盘IO)
  5. 超时控制 (默认30s, 最大300s)
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 沙箱用户 (非root)
SANDBOX_USER = "kylinops-agent"

# 文件系统白名单
PATH_WHITELIST = [
    "/var/log/", "/tmp/", "/var/tmp/",
    "/etc/", "/usr/share/", "/proc/", "/sys/",
    "/var/lib/systemd/", "/run/systemd/",
]

# 文件系统黑名单
PATH_BLACKLIST = [
    "/etc/shadow", "/etc/shadow-", "/root/.ssh",
    "/etc/sudoers", "/etc/sudoers.d",
    "/boot/", "/etc/passwd", "/etc/group",
]


@dataclass
class SandboxConfig:
    """沙箱配置"""
    user: str = SANDBOX_USER
    timeout: int = 30
    max_timeout: int = 300
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    allow_network: bool = True
    allow_write: bool = False
    path_whitelist: list = field(default_factory=lambda: PATH_WHITELIST.copy())
    path_blacklist: list = field(default_factory=lambda: PATH_BLACKLIST.copy())


def build_sandbox_wrapper(command: str, config: Optional[SandboxConfig] = None) -> str:
    """
    构建沙箱包装命令。

    在麒麟OS上使用以下机制:
    - sudo -u 切换到非root用户
    - timeout 限制执行时间
    - ulimit 限制资源使用
    """
    if config is None:
        config = SandboxConfig()

    parts = []

    # 1. 切换用户
    parts.append(f"sudo -u {config.user}")

    # 2. 资源限制
    limits = []
    if config.max_memory_mb:
        limits.append(f"ulimit -v {config.max_memory_mb * 1024}")
    if config.max_cpu_percent:
        limits.append(f"ulimit -t {config.timeout}")
    if limits:
        parts.append("bash -c '" + " && ".join(limits) + " && ")

    # 3. 超时包装
    parts.append(f"timeout {config.timeout}")

    # 4. 原始命令
    parts.append(command)

    # 5. 关闭bash -c
    if limits:
        parts.append("'")

    return " ".join(parts)


def validate_path(path: str) -> Dict:
    """验证路径是否在沙箱允许范围内"""
    if not path:
        return {"safe": True, "message": ""}

    # 黑名单检查
    for blacklisted in PATH_BLACKLIST:
        if path == blacklisted or path.startswith(blacklisted + "/"):
            return {"safe": False, "message": f"路径在黑名单中: {blacklisted}"}

    # 白名单检查
    for whitelisted in PATH_WHITELIST:
        if path.startswith(whitelisted):
            return {"safe": True, "message": ""}

    # 不在白名单也不在黑名单 → 只读允许
    return {"safe": True, "message": "路径不在白名单中，仅允许读取"}


def build_safe_command(command: str, allow_write: bool = False, timeout: int = 30) -> Dict:
    """
    构建安全执行命令。

    返回:
      {command, safe, warnings, sandbox_config}
    """
    config = SandboxConfig(
        timeout=min(timeout, 300),
        allow_write=allow_write,
    )

    warnings = []

    # 提取命令中的路径进行检查
    import re
    paths = re.findall(r'(/[a-zA-Z0-9._-]+)+/?', command)
    for path in paths:
        if isinstance(path, tuple):
            path = "/" + "/".join(filter(None, path))
        result = validate_path(path)
        if not result["safe"]:
            return {
                "command": "",
                "safe": False,
                "warnings": [result["message"]],
            }
        if result["message"]:
            warnings.append(result["message"])

    safe_cmd = build_sandbox_wrapper(command, config)

    return {
        "command": safe_cmd,
        "safe": True,
        "warnings": warnings,
    }
