"""内置运维工具目录 — 供工具管理页展示与启动时自动注册。"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_config import ToolConfig

# 与 tool_definitions.TOOLS 及 remote_executor 对齐
BUILTIN_TOOL_CATALOG: List[Dict] = [
    {"name": "get_system_info", "description": "获取系统概览信息，包括CPU、内存、磁盘、系统版本等", "category": "system_monitor", "risk_level": 1},
    {"name": "get_disk_usage", "description": "查询磁盘挂载和使用情况", "category": "system_monitor", "risk_level": 1},
    {"name": "get_cpu_info", "description": "获取CPU使用率、核心数、负载等信息", "category": "system_monitor", "risk_level": 1},
    {"name": "get_memory_info", "description": "获取内存和交换区使用情况", "category": "system_monitor", "risk_level": 1},
    {"name": "list_processes", "description": "获取进程列表，可按CPU或内存排序", "category": "process_management", "risk_level": 1},
    {"name": "get_process_detail", "description": "获取指定进程的详细信息", "category": "process_management", "risk_level": 1},
    {"name": "kill_process", "description": "终止指定进程，默认发送TERM信号", "category": "process_management", "risk_level": 3},
    {"name": "get_network_connections", "description": "查询网络连接状态和监听端口", "category": "network_management", "risk_level": 1},
    {"name": "get_network_speed", "description": "采样计算网卡实时收发速率（KB/s、Mbps），并给出网速好坏评价", "category": "network_management", "risk_level": 1},
    {"name": "get_service_status", "description": "获取指定系统服务的状态", "category": "service_management", "risk_level": 1},
    {"name": "manage_service", "description": "管理系统服务：启动、停止、重启、重载", "category": "service_management", "risk_level": 3},
    {"name": "get_file_list", "description": "获取指定目录的文件列表", "category": "file_management", "risk_level": 1},
    {"name": "read_file", "description": "读取指定文件的内容", "category": "file_management", "risk_level": 1},
    {"name": "search_journal_logs", "description": "搜索系统日志", "category": "log_management", "risk_level": 1},
    {"name": "get_users", "description": "获取系统用户列表", "category": "system_operation", "risk_level": 1},
    {"name": "get_groups", "description": "获取系统用户组列表", "category": "system_operation", "risk_level": 1},
    {"name": "execute_command", "description": "在远程系统上执行shell命令。高危操作，需经过安全检查", "category": "system_operation", "risk_level": 4},
    {"name": "summarize_task", "description": "总结当前任务，结束对话，提供最终报告", "category": "system_operation", "risk_level": 1},
]

BUILTIN_TOOL_NAMES = frozenset(item["name"] for item in BUILTIN_TOOL_CATALOG)


def is_builtin_tool_name(name: str) -> bool:
    return name in BUILTIN_TOOL_NAMES


async def ensure_builtin_tools(db: AsyncSession) -> int:
    """将缺失的内置工具写入 tool_configs，已有记录不覆盖。"""
    existing = set(
        (await db.execute(select(ToolConfig.name))).scalars().all()
    )
    added = 0
    for item in BUILTIN_TOOL_CATALOG:
        if item["name"] in existing:
            continue
        db.add(ToolConfig(
            name=item["name"],
            description=item["description"],
            category=item["category"],
            risk_level=item["risk_level"],
            enabled=1,
            config_json="{}",
        ))
        added += 1
    if added:
        await db.commit()
    return added
