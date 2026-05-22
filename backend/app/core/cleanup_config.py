from typing import Dict, List, Optional


class CleanupPathConfig:
    def __init__(self, path: str, description: str, risk_level: str = "low", auto_clean: bool = False, retention_days: Optional[int] = None):
        self.path = path
        self.description = description
        self.risk_level = risk_level
        self.auto_clean = auto_clean
        self.retention_days = retention_days


DEFAULT_CLEANUP_PATHS: List[CleanupPathConfig] = [
    CleanupPathConfig(
        path="/var/log",
        description="系统日志目录，存放系统和应用日志",
        risk_level="medium",
        auto_clean=True,
        retention_days=7,
    ),
    CleanupPathConfig(
        path="/var/cache",
        description="系统缓存目录，存放临时缓存文件",
        risk_level="low",
        auto_clean=True,
        retention_days=3,
    ),
    CleanupPathConfig(
        path="/var/tmp",
        description="临时文件目录，系统重启后自动清理",
        risk_level="low",
        auto_clean=True,
        retention_days=1,
    ),
    CleanupPathConfig(
        path="/tmp",
        description="临时文件目录，系统重启后自动清理",
        risk_level="low",
        auto_clean=True,
        retention_days=1,
    ),
    CleanupPathConfig(
        path="/home",
        description="用户家目录，可能包含用户数据",
        risk_level="high",
        auto_clean=False,
    ),
    CleanupPathConfig(
        path="/root",
        description="root用户家目录，可能包含重要配置",
        risk_level="high",
        auto_clean=False,
    ),
    CleanupPathConfig(
        path="/var/lib/docker",
        description="Docker镜像和容器数据目录",
        risk_level="high",
        auto_clean=False,
    ),
    CleanupPathConfig(
        path="/var/spool/mail",
        description="邮件队列目录",
        risk_level="medium",
        auto_clean=False,
    ),
]


def get_cleanup_paths() -> List[Dict]:
    """获取所有可清理路径配置"""
    return [
        {
            "path": p.path,
            "description": p.description,
            "risk_level": p.risk_level,
            "auto_clean": p.auto_clean,
            "retention_days": p.retention_days,
        }
        for p in DEFAULT_CLEANUP_PATHS
    ]


def get_paths_by_risk(risk_level: str) -> List[str]:
    """按风险级别获取路径列表"""
    return [p.path for p in DEFAULT_CLEANUP_PATHS if p.risk_level == risk_level]


def get_auto_clean_paths() -> List[str]:
    """获取可自动清理的路径"""
    return [p.path for p in DEFAULT_CLEANUP_PATHS if p.auto_clean]


def get_safe_cleanup_paths() -> List[str]:
    """获取低风险清理路径（适合自动清理）"""
    return [p.path for p in DEFAULT_CLEANUP_PATHS if p.risk_level in ["low", "medium"] and p.auto_clean]


def get_cleanup_command(paths: Optional[List[str]] = None) -> str:
    """生成磁盘清理检查命令"""
    if paths is None:
        paths = [p.path for p in DEFAULT_CLEANUP_PATHS]
    path_str = " ".join(paths)
    return f"du -sh {path_str} 2>/dev/null | sort -rh"


def get_clean_command(path: str, retention_days: int = 7) -> str:
    """生成清理指定路径的命令"""
    return f"find {path} -type f -mtime +{retention_days} -print 2>/dev/null | head -20"