"""
文件保护白名单 — 关键资产识别与路径拦截
"""
from __future__ import annotations

import re
from typing import List, Set

from app.core.command_security import validate_path, PATH_PROTECTIONS

CRITICAL_PATHS = tuple(PATH_PROTECTIONS.keys()) + (
    "/etc/passwd", "/etc/shadow", "/etc/group", "/etc/sudoers",
    "/etc/ssh/sshd_config", "/etc/fstab", "/boot",
    "/var/lib/mysql", "/var/lib/pgsql", "/var/lib/docker",
)

BUSINESS_HINTS = ("数据目录", "数据库", "业务数据", "生产数据", "备份目录")


def build_whitelist(content: str = "", rag_context: str = "", env_metrics: dict = None) -> List[str]:
    protected: Set[str] = set(CRITICAL_PATHS)
    combined = f"{content}\n{rag_context or ''}".lower()

    for m in re.finditer(r"(/(?:[\w./_-]+))", combined):
        p = m.group(1).rstrip("/")
        if any(k in p for k in ("data", "mysql", "pgsql", "backup", "db")):
            protected.add(p)

    for hint in BUSINESS_HINTS:
        if hint in combined:
            protected.add(f"/*{hint}*")

    if env_metrics:
        for _tool, raw in env_metrics.items():
            text = str(raw)
            for p in re.findall(r"(/var/[\w./-]+|/etc/[\w./-]+)", text):
                if "lib" in p or "data" in p:
                    protected.add(p)

    return sorted(protected)


def check_command_against_whitelist(command: str, whitelist: List[str] = None) -> dict:
    """原子化校验：写操作是否触碰保护路径。"""
    write_re = re.compile(r"\b(rm|mv|chmod|chown|chattr|dd|mkfs|truncate|shred)\b", re.I)
    if not write_re.search(command or ""):
        return {"blocked": False, "path": None, "message": ""}

    for m in re.finditer(r"(?:^|\s)(/(?:[\w.-]+/)*[\w.-]+)", command):
        path = m.group(1)
        vr = validate_path(path)
        if not vr["safe"]:
            return {"blocked": True, "path": path, "message": vr["message"]}

        if whitelist:
            for wp in whitelist:
                if wp.endswith("*"):
                    continue
                if path == wp or path.startswith(wp + "/"):
                    return {"blocked": True, "path": path, "message": f"受保护路径: {wp}"}

    return {"blocked": False, "path": None, "message": ""}
