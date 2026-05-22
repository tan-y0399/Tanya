import json
from datetime import datetime, timedelta
import httpx
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import desc
from app.models.session import Session, Message
from app.models.approval import Approval
from app.models.pending_execution import PendingExecution
from app.core.config import settings
from app.core.trace import generate_trace_id
from app.core.command_security import analyze_command, RiskLevel, get_risk_level_info


# ============================================================
# 工具定义 (OpenAI Function Calling 格式)
# ============================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "获取系统概览信息，包括CPU、内存、磁盘、系统版本等",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_disk_usage",
            "description": "查询磁盘挂载和使用情况",
            "parameters": {
                "type": "object",
                "properties": {
                    "mount_point": {"type": "string", "description": "指定挂载点路径，留空查询全部"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cpu_info",
            "description": "获取CPU使用率、核心数、负载等信息",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory_info",
            "description": "获取内存和交换区使用情况",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "获取进程列表，可按CPU或内存排序",
            "parameters": {
                "type": "object",
                "properties": {
                    "sort_by": {"type": "string", "enum": ["cpu", "mem"], "description": "排序字段"},
                    "limit": {"type": "integer", "description": "返回数量，默认10"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_process_detail",
            "description": "获取指定进程的详细信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "进程ID"},
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_process",
            "description": "终止指定进程，默认发送TERM信号",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "进程ID"},
                    "signal": {"type": "string", "description": "信号类型，如TERM、KILL，默认TERM"},
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_network_connections",
            "description": "查询网络连接状态和监听端口",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "连接状态过滤: LISTEN, ESTABLISHED 等"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_status",
            "description": "获取指定系统服务的状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "服务名称"},
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_service",
            "description": "管理系统服务：启动、停止、重启、重载",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "服务名称"},
                    "action": {"type": "string", "enum": ["start", "stop", "restart", "reload"], "description": "操作类型"},
                },
                "required": ["service_name", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_list",
            "description": "获取指定目录的文件列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认为当前目录"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_journal_logs",
            "description": "搜索系统日志",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "服务名过滤，如 nginx, mysql"},
                    "priority": {"type": "string", "enum": ["err", "warning", "info"], "description": "日志级别"},
                    "lines": {"type": "integer", "description": "返回行数，默认20"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_users",
            "description": "获取系统用户列表",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_groups",
            "description": "获取系统用户组列表",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "在远程系统上执行shell命令。⚠ 高危操作，需经过安全检查",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的shell命令"},
                    "timeout": {"type": "integer", "description": "命令超时秒数，默认30"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_task",
            "description": "总结当前任务，结束对话，提供最终报告",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "任务总结内容"},
                },
                "required": [],
            },
        },
    },
]

SYSTEM_PROMPT = """你是 KylinOps 智能运维 Agent，运行在麒麟操作系统 V11 上。你是一个智能的、主动的运维助手。

## 核心能力
- 自动理解用户意图，不需要用户明确说"执行命令"或"调用工具"
- 能够规划多步骤任务并自动执行所有必要步骤
- 像人类助手一样自然对话，主动提供建议和方案

## 任务处理流程（自动执行）
1. **理解意图**：自动分析用户的自然语言请求
2. **规划步骤**：自动规划完成任务所需的步骤
3. **自动执行**：按步骤自动调用工具获取信息和执行操作
4. **智能判断**：根据结果决定下一步（继续/确认/完成）
5. **总结报告**：完成任务后提供详细总结

## 智能决策规则
- 如果用户说"查看磁盘" -> 直接调用 get_disk_usage 获取磁盘信息并展示
- 如果用户说"磁盘满了，清理一下" -> 先查看磁盘 -> 使用标准路径分析大文件 -> 列出可删除项 -> 等待确认 -> 执行删除
- 如果用户说"检查nginx服务" -> 先查看服务状态 -> 如果异常则建议重启 -> 等待确认后执行
- 如果用户说"系统慢" -> 自动检查CPU、内存、进程 -> 分析瓶颈 -> 提供优化建议

## 磁盘清理标准路径
清理磁盘时，请使用以下标准路径列表，不要使用其他路径：
- 低风险（可自动清理）：/var/log, /var/cache, /var/tmp, /tmp
- 高风险（需确认）：/home, /root, /var/lib/docker

检查磁盘空间使用命令示例：du -sh /var/log /var/cache /var/tmp /tmp /home /root 2>/dev/null | sort -rh

## 对话状态管理
- 记住对话历史，理解上下文
- 如果用户问"然后呢？"或"继续"，继续执行下一步
- 如果用户说"取消"或"算了"，中止当前任务

## 安全规则（系统自动执行，LLM无需关心）
系统内置多层安全护栏，对你每次工具调用自动进行风险分级：
- 🟢 L1 只读操作（get_cpu_info, get_memory_info, get_disk_usage, list_processes, get_service_status,
  get_network_connections, get_file_list, read_file, get_logs, get_users, get_groups 等）：
  自动执行，无需确认
- 🟡 L2 低风险操作（kill TERM信号, manage_service start, 查询类命令）：自动向用户确认后执行
- 🟠 L3 高风险操作（kill -9/KILL, manage_service stop/restart, rm/chmod/iptables等）：
  需要用户审批
- 🔴 L4~L5 致命操作（mkfs, fdisk, useradd, passwd, yum install/remove 等）：
  需要审批，部分命令（mkfs/fdisk）直接被阻止

你只需要正常调用工具即可，安全护栏会自动拦截、审批或放行。对于被阻止的操作，你会收到 error 消息。

## 可用工具
| 工具名 | 用途 | 风险级别 |
|--------|------|----------|
| get_system_info | 获取系统概览 | L1 |
| get_cpu_info | 获取CPU信息 | L1 |
| get_memory_info | 获取内存信息 | L1 |
| get_disk_usage | 获取磁盘使用 | L1 |
| list_processes | 进程列表 | L1 |
| get_process_detail | 进程详情 | L1 |
| kill_process | 终止进程 | L2~L3 |
| get_service_status | 服务状态 | L1 |
| manage_service | 服务管理(启动/停止/重启) | L2~L4 |
| get_network_connections | 网络连接 | L1 |
| get_network_interfaces | 网络接口 | L1 |
| get_file_list | 文件列表 | L1 |
| read_file | 读取文件 | L1 |
| get_logs | 系统日志 | L1 |
| get_users | 用户列表 | L1 |
| get_groups | 用户组列表 | L1 |
| execute_command | 执行任意命令 | 按命令风险分级 |
| summarize_task | 总结任务并结束 | L1 |

## 输出格式规范（严格遵守）
你必须使用 Markdown 格式化输出，让结果清晰美观。按数据类型使用以下格式：

### 数值指标（CPU、内存、磁盘使用率等）
使用 **表格** 展示，重要指标用 `**粗体**` 高亮：

```
| 指标 | 数值 | 状态 |
|------|------|------|
| CPU使用率 | **23.5%** | 🟢 正常 |
| 内存使用率 | **78.2%** | 🟡 偏高 |
| 磁盘 /dev/sda1 | **45%** | 🟢 正常 |
```

### 系统概览
使用 **卡片式标题 + 表格**：

```
### 🖥 系统概览
| 项目 | 详情 |
|------|------|
| 操作系统 | Kylin Linux V11 |
| 内核版本 | 5.10.0-8-generic |
| 运行时间 | 3 days 12 hours |
| 主机名 | kylin-server-01 |
```

### 进程列表
使用 **表格**，高亮资源占用高的进程：

```
### 📋 进程列表 (TOP 5)
| PID | 进程名 | CPU% | MEM% | 用户 |
|-----|--------|------|------|------|
| 1234 | **mysqld** | **45.2%** | 12.1% | mysql |
| 5678 | nginx | 2.3% | 1.5% | www |
```

### 多步骤任务
使用 **步骤列表**，每步标注状态：

```
### 🔍 磁盘空间分析

**Step 1**: 检查磁盘使用 ✅
| 分区 | 总量 | 已用 | 可用 | 使用率 |
|------|------|------|------|--------|
| /dev/sda1 | 100G | 45G | 55G | 45% |

**Step 2**: 分析大文件目录 ✅
- `/var/log` — 12G（可清理）
- `/tmp` — 3.2G（可清理）

**Step 3**: 建议操作 🟡
建议清理以上目录，预计释放 **15.2G** 空间。是否继续？
```

### 日志/错误信息
使用 **代码块**：

~~~
### ⚠️ 错误日志 (最近5条)
\`\`\`
May 21 10:30:15 kylin nginx[1234]: connect() failed
May 21 10:30:16 kylin nginx[1234]: upstream timeout
\`\`\`
~~~

### 健康评分
巡检完成后给出总体评分：

```
### 🏥 系统健康评分: 85/100 🟡
| 维度 | 分数 | 状态 |
|------|------|------|
| CPU | 90/100 | 🟢 |
| 内存 | 75/100 | 🟡 |
| 磁盘 | 85/100 | 🟢 |
| 网络 | 90/100 | 🟢 |
```

## 输出要求
- 始终使用 Markdown 表格、标题、列表、代码块格式化输出
- 数值数据用表格，不要用纯文本罗列
- 关键指标用 `**粗体**`，状态用 🟢🟡🔴 标识
- 多步骤任务用步骤编号 + 状态标记
- 短语优先，避免冗长段落
- 中文回复，专业友好
"""


# ============================================================
# 工具执行器 —— 通过 SSH 在远程麒麟VM上真实执行
# ============================================================
def execute_tool(name: str, args: dict) -> dict:
    """执行工具调用，转发到远程麒麟VM执行"""
    from app.services.remote_executor import execute_tool as remote_exec

    # 工具名映射：chat_service 中的工具名 → remote_executor 中的工具名
    tool_map = {
        "get_system_info": "get_system_info",
        "get_cpu_info": "get_cpu_info",
        "get_memory_info": "get_memory_info",
        "get_disk_usage": "get_disk_info",
        "list_processes": "get_process_list",
        "get_network_connections": "get_network_connections",
        "get_process_detail": "get_process_detail",
        "kill_process": "kill_process",
        "get_service_status": "get_service_status",
        "manage_service": "manage_service",
        "get_file_list": "get_file_list",
        "read_file": "read_file",
        "get_logs": "get_logs",
        "get_users": "get_users",
        "get_groups": "get_groups",
    }

    if name in tool_map:
        return remote_exec(tool_map[name], **args)

    if name == "search_journal_logs":
        service = args.get("service", "")
        priority = args.get("priority", "")
        lines = args.get("lines", 20)
        cmd = "journalctl"
        if service:
            cmd += f" -u {service}"
        if priority:
            prio_map = {"err": "3", "warning": "4", "info": "6"}
            cmd += f" -p {prio_map.get(priority, '6')}"
        cmd += f" -n {lines} --no-pager 2>/dev/null"
        return remote_exec("run_command", command=cmd, timeout=5)

    if name == "execute_command":
        command = args.get("command", "")
        timeout = args.get("timeout", 30)
        return remote_exec("run_command", command=command, timeout=timeout)

    if name == "summarize_task":
        summary = args.get("summary", "")
        return {
            "success": True,
            "data": {
                "summary": summary,
                "task_completed": True,
            }
        }

    return {"success": False, "error": f"未知工具: {name}"}


def get_tool_risk_level(name: str, args: dict = None) -> str:
    """获取工具调用的风险级别"""
    args = args or {}
    
    risk_map = {
        "get_system_info": "L1",
        "get_cpu_info": "L1",
        "get_memory_info": "L1",
        "get_disk_usage": "L1",
        "list_processes": "L1",
        "get_process_detail": "L1",
        "get_network_connections": "L1",
        "search_journal_logs": "L1",
        "get_logs": "L1",
        "get_file_list": "L1",
        "read_file": "L1",
        "get_users": "L1",
        "get_groups": "L1",
        "get_service_status": "L1",
        "summarize_task": "L1",
        
        "kill_process": "L3",
        "manage_service": "L3",
        
        "execute_command": "L3",
    }
    
    risk = risk_map.get(name, "L3")
    
    if name == "kill_process":
        signal = args.get("signal", "").upper()
        if signal == "KILL" or signal == "9":
            risk = "L4"
    
    if name == "manage_service":
        action = args.get("action", "").lower()
        if action in ["stop", "restart"]:
            risk = "L4"
    
    if name == "execute_command":
        from app.core.command_security import analyze_command
        command = args.get("command", "")
        analysis = analyze_command(command)
        if analysis.get("success"):
            risk = analysis.get("risk_level", "L3")
    
    return risk


# ============================================================
# 安全护栏 —— 工具调用前风险检查
# ============================================================
def _check_tool_safety(tool_name: str, tool_args: dict) -> dict:
    """
    检查工具调用的安全风险，返回:
      {safe, blocked, block_message, require_approval, require_confirm, risk_level}

    分级规则（严格按照产品规范）:
      L1 🟢: 只读操作，直接执行
      L2 🟡: 需确认（kill -9 升级为审批）
      L3 🟠: 需审批
      L4~L5 🔴: 需审批，部分命令直接阻止
    """
    risk = get_tool_risk_level(tool_name, tool_args)

    result = {
        "safe": True,
        "blocked": False,
        "block_message": None,
        "require_approval": False,
        "require_confirm": False,
        "risk_level": risk,
    }

    # L1: 只读，直接执行
    if risk == "L1":
        return result

    # execute_command 需要深入分析命令内容
    if tool_name == "execute_command":
        command = tool_args.get("command", "")
        if not command.strip():
            result["safe"] = False
            result["blocked"] = True
            result["block_message"] = "空命令"
            return result

        analysis = analyze_command(command)

        if analysis.get("blocked"):
            result["safe"] = False
            result["blocked"] = True
            result["block_message"] = analysis.get("block_message", "此命令被安全策略阻止")
            result["risk_level"] = analysis.get("risk_level", risk)
            return result

        if analysis.get("require_approval"):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = analysis.get("require_confirm", True)
            result["risk_level"] = analysis.get("risk_level", risk)
            return result

        if analysis.get("require_confirm"):
            result["safe"] = False
            result["require_confirm"] = True
            result["risk_level"] = analysis.get("risk_level", risk)
            return result

        # 命令分析通过，按工具级别处理
        if risk in ("L3", "L4", "L5"):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = True
            return result
        if risk == "L2":
            result["safe"] = False
            result["require_confirm"] = True
            return result
        return result

    # kill_process: TERM=L2需确认, KILL=L3需审批
    if tool_name == "kill_process":
        signal = tool_args.get("signal", "").upper()
        if signal in ("KILL", "9"):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = True
            result["risk_level"] = "L3"
            return result
        result["safe"] = False
        result["require_confirm"] = True
        result["risk_level"] = "L2"
        return result

    # manage_service: start=L2需确认, stop/restart/reload=L3需审批
    if tool_name == "manage_service":
        action = tool_args.get("action", "").lower()
        if action in ("stop", "restart", "reload"):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = True
            result["risk_level"] = "L4"
            return result
        result["safe"] = False
        result["require_confirm"] = True
        result["risk_level"] = "L2"
        return result

    # L2: 需确认
    if risk == "L2":
        result["safe"] = False
        result["require_confirm"] = True
        return result

    # L3~L5: 需审批
    if risk in ("L3", "L4", "L5"):
        result["safe"] = False
        result["require_approval"] = True
        result["require_confirm"] = True
        return result

    return result


def _build_risk_description(tool_name: str, tool_args: dict, risk_level: str) -> str:
    """生成风险描述文本，用于审批单和用户展示"""
    desc_map = {
        "kill_process": f"终止进程 PID={tool_args.get('pid', '?')} (信号: {tool_args.get('signal', 'TERM')})",
        "manage_service": f"{tool_args.get('action', '?')} 服务 {tool_args.get('service_name', '?')}",
        "execute_command": f"执行命令: {tool_args.get('command', '?')}",
    }
    detail = desc_map.get(tool_name, f"调用工具 {tool_name}: {json.dumps(tool_args, ensure_ascii=False)}")

    risk_info = get_risk_level_info(risk_level)
    return f"{risk_info['color']} [{risk_level}] {detail}"


async def _save_pending_execution(
    db: AsyncSession,
    session_id: str,
    trace_id: str,
    user_id: str,
    tool_name: str,
    tool_args: dict,
    risk_level: str,
    messages_snapshot: list,
    need_approval: bool = False,
    need_confirm: bool = False,
    approval_id: str = None,
) -> PendingExecution:
    pe = PendingExecution(
        session_id=session_id,
        trace_id=trace_id,
        user_id=user_id,
        approval_id=approval_id,
        tool_name=tool_name,
        tool_params_json=json.dumps(tool_args, ensure_ascii=False),
        risk_level=risk_level,
        messages_snapshot_json=json.dumps(messages_snapshot, ensure_ascii=False),
        need_approval=need_approval,
        need_confirm=need_confirm,
        status="pending",
    )
    db.add(pe)
    await db.commit()
    await db.refresh(pe)
    return pe


# ============================================================
# 会话管理
# ============================================================
async def get_sessions(db: AsyncSession, user_id: str, page: int = 1, size: int = 20) -> dict:
    q = select(Session).where(Session.user_id == user_id).order_by(desc(Session.updated_at))
    total_result = await db.execute(select(func.count()).select_from(Session).where(Session.user_id == user_id))
    total = total_result.scalar() or 0
    rows_result = await db.execute(q.offset((page - 1) * size).limit(size))
    rows = rows_result.scalars().all()

    items = []
    for s in rows:
        msg_result = await db.execute(select(func.count()).select_from(Message).where(Message.session_id == s.id))
        msg_count = msg_result.scalar() or 0
        items.append({
            "id": s.id, "title": s.title,
            "createdAt": s.created_at.isoformat() if s.created_at else "",
            "updatedAt": s.updated_at.isoformat() if s.updated_at else "",
            "messageCount": msg_count,
        })
    return {"items": items, "total": total, "page": page, "size": size}


async def create_session(db: AsyncSession, user_id: str, title: str = "新会话") -> dict:
    s = Session(user_id=user_id, title=title)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": s.id, "title": s.title, "createdAt": s.created_at.isoformat() if s.created_at else ""}


async def delete_session(db: AsyncSession, session_id: str) -> None:
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Message).where(Message.session_id == session_id))
    await db.execute(sql_delete(Session).where(Session.id == session_id))
    await db.commit()


async def clear_session_messages(db: AsyncSession, session_id: str) -> None:
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Message).where(Message.session_id == session_id))
    await db.commit()


async def delete_message(db: AsyncSession, message_id: str) -> None:
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Message).where(Message.id == message_id))
    await db.commit()


async def get_messages(db: AsyncSession, session_id: str, page: int = 1, size: int = 50) -> dict:
    q = select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    total_result = await db.execute(select(func.count()).select_from(Message).where(Message.session_id == session_id))
    total = total_result.scalar() or 0
    rows_result = await db.execute(q.offset((page - 1) * size).limit(size))
    rows = rows_result.scalars().all()

    items = []
    for m in rows:
        tool_calls = None
        if m.tool_calls_json:
            try:
                tool_calls = json.loads(m.tool_calls_json)
            except Exception:
                pass
        items.append({
            "id": m.id, "role": m.role, "content": m.content or "",
            "toolCalls": tool_calls, "traceId": m.trace_id,
            "createdAt": m.created_at.isoformat() if m.created_at else "",
        })
    return {"items": items, "total": total}


async def save_message(db: AsyncSession, session_id: str, role: str, content: str = "",
                       tool_calls: Optional[list] = None, trace_id: Optional[str] = None) -> str:
    msg = Message(
        session_id=session_id, role=role, content=content,
        tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
        trace_id=trace_id,
    )
    db.add(msg)
    result = await db.execute(select(Session).where(Session.id == session_id))
    s = result.scalar_one_or_none()
    if s:
        from datetime import datetime, timedelta
        s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)
    return msg.id


# ============================================================
# DeepSeek API 调用
# ============================================================
async def call_deepseek(messages: List[Dict], stream: bool = True):
    """调用 DeepSeek API，返回流式响应或完整响应"""
    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "stream": stream,
        "tools": TOOLS,
        "tool_choice": "auto",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        if stream:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            yield data
                        except Exception:
                            continue
        else:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            yield resp.json()


# ============================================================
# Agent 处理主流程 (ReAct 循环)
# ============================================================
async def process_message(db: AsyncSession, session_id: str, content: str, user_id: str):
    """Agent 主处理流程 - SSE 流式推送"""
    trace_id = generate_trace_id()
    assistant_msg_id = generate_id()

    # 保存用户消息
    await save_message(db, session_id, "user", content, trace_id=trace_id)

    # 首条消息时自动更新会话标题
    msg_count_result = await db.execute(
        select(func.count()).select_from(Message).where(Message.session_id == session_id)
    )
    if (msg_count_result.scalar() or 0) <= 1:
        title = content[:20] + ("..." if len(content) > 20 else "")
        result = await db.execute(select(Session).where(Session.id == session_id))
        s = result.scalar_one_or_none()
        if s:
            s.title = title
            await db.commit()

    yield {"event": "message_start", "data": json.dumps({"messageId": assistant_msg_id, "traceId": trace_id})}

    # 构建对话历史
    history = await get_messages(db, session_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history["items"]:
        if m["role"] == "user":
            messages.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            messages.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "tool_call" and m.get("toolCalls"):
            for tc in m["toolCalls"]:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["toolName"], "arguments": json.dumps(tc.get("params", {}))},
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tc.get("result", {}), ensure_ascii=False),
                })

    full_response = ""
    max_rounds = settings.max_conversation_rounds
    round_count = 0
    tool_call_records = []

    while round_count < max_rounds:
        round_count += 1
        current_tool_calls = []
        current_content = ""

        try:
            async for chunk in call_deepseek(messages, stream=True):
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})

                if "content" in delta and delta["content"]:
                    current_content += delta["content"]
                    full_response += delta["content"]
                    yield {"event": "token", "data": json.dumps({"token": delta["content"]})}

                if "tool_calls" in delta:
                    for tc_delta in delta["tool_calls"]:
                        idx = tc_delta.get("index", 0)
                        while len(current_tool_calls) <= idx:
                            current_tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                        tc = current_tool_calls[idx]
                        if "id" in tc_delta:
                            tc["id"] = tc_delta["id"]
                        if "function" in tc_delta:
                            fn = tc_delta["function"]
                            if "name" in fn:
                                tc["function"]["name"] = fn["name"]
                            if "arguments" in fn:
                                tc["function"]["arguments"] += fn["arguments"]

            if current_tool_calls:
                # Agent 决定调用工具 —— 安全护栏前置检查
                messages.append({"role": "assistant", "content": current_content or None, "tool_calls": current_tool_calls})

                blocked_any = False
                pending_approval = None
                pending_confirm = None

                for tc in current_tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_call_id = tc.get("id", generate_id())
                    try:
                        tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                    except json.JSONDecodeError:
                        tool_args = {}

                    risk = get_tool_risk_level(tool_name, tool_args)
                    safety = _check_tool_safety(tool_name, tool_args)

                    # ── 阻止（高危命令如 mkfs, rm -rf /）──
                    if safety["blocked"]:
                        blocked_any = True
                        block_msg = safety["block_message"]

                        yield {"event": "blocked", "data": json.dumps({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "message": block_msg,
                            "status": "blocked",
                        })}

                        tool_call_records.append({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "status": "blocked",
                            "result": {"success": False, "error": block_msg},
                        })
                        continue

                    # ── 需审批（L3+ 写操作：重启服务、用户管理、iptables修改等）──
                    if safety["require_approval"]:
                        risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
                        now = datetime.utcnow()
                        expires_at = now + timedelta(seconds=settings.approval_timeout)

                        approval = Approval(
                            trace_id=trace_id,
                            session_id=session_id,
                            tool_name=tool_name,
                            tool_params_json=json.dumps(tool_args, ensure_ascii=False),
                            risk_level=safety["risk_level"],
                            detail=risk_desc,
                            requested_by=user_id,
                            expires_at=expires_at,
                        )
                        db.add(approval)
                        await db.commit()
                        await db.refresh(approval)

                        # 保存待处理执行记录，审批通过后继续
                        pe = await _save_pending_execution(
                            db, session_id, trace_id, user_id,
                            tool_name, tool_args, safety["risk_level"],
                            messages_snapshot=messages,
                            need_approval=True,
                            approval_id=approval.id,
                        )

                        yield {"event": "need_approval", "data": json.dumps({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "approvalId": approval.id,
                            "message": f"{risk_desc}\n请在审批管理页面确认此操作（{settings.approval_timeout}秒超时）",
                            "status": "pending_approval",
                            "expiresAt": expires_at.isoformat(),
                        })}

                        tool_call_records.append({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "status": "pending_approval",
                            "approvalId": approval.id,
                        })
                        pending_approval = approval.id
                        continue

                    # ── 需确认（L2 可逆操作：kill TERM, service start等）──
                    if safety["require_confirm"]:
                        risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])

                        pe = await _save_pending_execution(
                            db, session_id, trace_id, user_id,
                            tool_name, tool_args, safety["risk_level"],
                            messages_snapshot=messages,
                            need_confirm=True,
                        )

                        yield {"event": "need_confirm", "data": json.dumps({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "pendingExecutionId": pe.id,
                            "message": f"{risk_desc}\n确认执行此操作？",
                            "status": "pending_confirm",
                        })}

                        tool_call_records.append({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "status": "pending_confirm",
                            "pendingExecutionId": pe.id,
                        })
                        pending_confirm = pe.id
                        continue

                    # ── L1 安全操作：直接执行 ──
                    yield {"event": "tool_call", "data": json.dumps({
                        "id": tool_call_id,
                        "toolName": tool_name,
                        "params": tool_args,
                        "riskLevel": risk,
                        "status": "executing",
                    })}

                    result = execute_tool(tool_name, tool_args)

                    yield {"event": "tool_result", "data": json.dumps({
                        "toolName": tool_name,
                        "status": "completed",
                        "result": result,
                    })}

                    tool_call_records.append({
                        "id": tool_call_id,
                        "toolName": tool_name,
                        "params": tool_args,
                        "riskLevel": risk,
                        "status": "completed",
                        "result": result,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                # 如果有待审批/待确认的操作，停止 ReAct 循环等待用户操作
                if pending_approval or pending_confirm:
                    yield {"event": "message_done", "data": json.dumps({
                        "messageId": assistant_msg_id,
                        "traceId": trace_id,
                        "status": "awaiting_user_action",
                        "approvalId": pending_approval,
                        "pendingConfirm": bool(pending_confirm),
                    })}
                    return

                # 如果有被阻止的工具但有其他成功的，继续循环
                if blocked_any and not any(
                    tc["status"] == "completed" for tc in tool_call_records
                ):
                    yield {"event": "message_done", "data": json.dumps({
                        "messageId": assistant_msg_id,
                        "traceId": trace_id,
                        "status": "blocked",
                    })}
                    return

                continue
            else:
                # Agent 完成回复，没有工具调用
                break

        except Exception as e:
            yield {"event": "token", "data": json.dumps({"token": f"\n\n[Agent 调用出错: {str(e)}]"})}
            break

    # 保存 assistant 消息
    await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)

    # 工具调用记录保存在 assistant 之后，确保前端只显示一个 Agent 头部
    if tool_call_records:
        await save_message(db, session_id, "tool_call", "",
                           tool_calls=tool_call_records, trace_id=trace_id)

    # 写入审计记录
    try:
        from app.models.audit import AuditRecord
        tools_used = list(set(tc["toolName"] for tc in tool_call_records)) if tool_call_records else []
        risks = [tc.get("riskLevel", "L1") for tc in tool_call_records] if tool_call_records else ["L1"]
        max_risk = "L4" if "L4" in risks else ("L3" if "L3" in risks else ("L2" if "L2" in risks else "L1"))
        audit = AuditRecord(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            event_type="chat",
            summary=content[:100] if not tools_used else f"调用 {','.join(tools_used)} | {content[:60]}",
            risk_level=max_risk,
            detail_json=json.dumps({
                "question": content[:200],
                "answer": full_response[:300],
                "tools": [{"name": tc["toolName"], "status": tc.get("status"), "risk": tc.get("riskLevel")}
                          for tc in (tool_call_records or [])],
            }, ensure_ascii=False),
        )
        db.add(audit)
        await db.commit()
    except Exception:
        pass  # 审计记录写入失败不阻塞对话

    yield {"event": "message_done", "data": json.dumps({
        "messageId": assistant_msg_id, "traceId": trace_id,
        "usage": {"outputTokens": len(full_response)},
    })}


def generate_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


# ============================================================
# 审批/确认 后恢复执行
# ============================================================
async def resume_after_approval(db: AsyncSession, session_id: str, user_id: str,
                               approval_id: str = None, pending_execution_id: str = None):
    """用户审批/确认通过后，继续执行被挂起的工具调用并恢复 ReAct 循环"""

    # 查找待处理执行记录
    if approval_id:
        result = await db.execute(
            select(PendingExecution).where(
                PendingExecution.session_id == session_id,
                PendingExecution.approval_id == approval_id,
                PendingExecution.status == "pending",
            )
        )
    elif pending_execution_id:
        result = await db.execute(
            select(PendingExecution).where(
                PendingExecution.id == pending_execution_id,
                PendingExecution.session_id == session_id,
                PendingExecution.status == "pending",
            )
        )
    else:
        yield {"event": "error", "data": json.dumps({
            "message": "缺少 approvalId 或 pendingExecutionId",
        })}
        return

    pe = result.scalar_one_or_none()
    if not pe:
        yield {"event": "error", "data": json.dumps({
            "message": "未找到待处理的执行记录，审批可能已过期或已处理",
        })}
        return

    # 如果需要审批，验证审批确实通过了
    if pe.need_approval and pe.approval_id:
        approval_result = await db.execute(
            select(Approval).where(Approval.id == pe.approval_id, Approval.status == "approved")
        )
        approval = approval_result.scalar_one_or_none()
        if not approval:
            pe.status = "rejected"
            await db.commit()
            yield {"event": "error", "data": json.dumps({
                "message": "审批未通过，无法继续执行",
            })}
            return

    # 标记 pending 为已处理
    pe.status = "resolved"
    pe.resolved_at = datetime.utcnow()

    tool_name = pe.tool_name
    tool_args = json.loads(pe.tool_params_json) if pe.tool_params_json else {}
    trace_id = pe.trace_id
    risk = pe.risk_level

    assistant_msg_id = generate_id()

    yield {"event": "message_start", "data": json.dumps({
        "messageId": assistant_msg_id, "traceId": trace_id,
    })}

    # 执行被审批通过的工具
    yield {"event": "tool_call", "data": json.dumps({
        "id": pe.id,
        "toolName": tool_name,
        "params": tool_args,
        "riskLevel": risk,
        "status": "executing",
        "approved": True,
    })}

    result = execute_tool(tool_name, tool_args)

    yield {"event": "tool_result", "data": json.dumps({
        "toolName": tool_name,
        "status": "completed",
        "result": result,
    })}

    tool_call_record = {
        "id": pe.id,
        "toolName": tool_name,
        "params": tool_args,
        "riskLevel": risk,
        "status": "completed",
        "result": result,
    }

    # 恢复 ReAct 循环
    try:
        messages = json.loads(pe.messages_snapshot_json) if pe.messages_snapshot_json else []
    except Exception:
        messages = []

    # 确保系统提示在最前面
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    # 将已执行工具的结果追加到消息中
    messages.append({
        "role": "tool",
        "tool_call_id": pe.id,
        "content": json.dumps(result, ensure_ascii=False),
    })

    full_response = ""
    max_rounds = settings.max_conversation_rounds
    existing_assistant = sum(1 for m in messages if m["role"] == "assistant")
    round_count = existing_assistant
    tool_call_records = [tool_call_record]

    while round_count < max_rounds:
        round_count += 1
        current_tool_calls = []
        current_content = ""

        try:
            async for chunk in call_deepseek(messages, stream=True):
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})

                if "content" in delta and delta["content"]:
                    current_content += delta["content"]
                    full_response += delta["content"]
                    yield {"event": "token", "data": json.dumps({"token": delta["content"]})}

                if "tool_calls" in delta:
                    for tc_delta in delta["tool_calls"]:
                        idx = tc_delta.get("index", 0)
                        while len(current_tool_calls) <= idx:
                            current_tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                        tc = current_tool_calls[idx]
                        if "id" in tc_delta:
                            tc["id"] = tc_delta["id"]
                        if "function" in tc_delta:
                            fn = tc_delta["function"]
                            if "name" in fn:
                                tc["function"]["name"] = fn["name"]
                            if "arguments" in fn:
                                tc["function"]["arguments"] += fn["arguments"]

            if current_tool_calls:
                messages.append({"role": "assistant", "content": current_content or None, "tool_calls": current_tool_calls})

                local_tool_records = []
                blocked_any = False

                for tc in current_tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_call_id = tc.get("id", generate_id())
                    try:
                        tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                    except json.JSONDecodeError:
                        tool_args = {}

                    risk = get_tool_risk_level(tool_name, tool_args)
                    safety = _check_tool_safety(tool_name, tool_args)

                    if safety["blocked"]:
                        blocked_any = True
                        yield {"event": "blocked", "data": json.dumps({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "message": safety["block_message"],
                            "status": "blocked",
                        })}
                        local_tool_records.append({
                            "id": tool_call_id, "toolName": tool_name,
                            "params": tool_args, "riskLevel": safety["risk_level"],
                            "status": "blocked",
                            "result": {"success": False, "error": safety["block_message"]},
                        })
                        continue

                    if safety["require_approval"] or safety["require_confirm"]:
                        # 恢复执行中如果遇到需要审批的，创建新的审批
                        risk_desc = _build_risk_description(tool_name, tool_args, safety["risk_level"])
                        now = datetime.utcnow()
                        expires_at = now + timedelta(seconds=settings.approval_timeout)

                        new_approval = Approval(
                            trace_id=trace_id,
                            session_id=session_id,
                            tool_name=tool_name,
                            tool_params_json=json.dumps(tool_args, ensure_ascii=False),
                            risk_level=safety["risk_level"],
                            detail=risk_desc,
                            requested_by=user_id,
                            expires_at=expires_at,
                        )
                        db.add(new_approval)
                        await db.commit()
                        await db.refresh(new_approval)

                        await _save_pending_execution(
                            db, session_id, trace_id, user_id,
                            tool_name, tool_args, safety["risk_level"],
                            messages_snapshot=messages,
                            need_approval=safety["require_approval"],
                            need_confirm=safety["require_confirm"],
                            approval_id=new_approval.id,
                        )

                        event_name = "need_approval" if safety["require_approval"] else "need_confirm"
                        yield {"event": event_name, "data": json.dumps({
                            "id": tool_call_id,
                            "toolName": tool_name,
                            "params": tool_args,
                            "riskLevel": safety["risk_level"],
                            "approvalId": new_approval.id if safety["require_approval"] else None,
                            "message": f"{risk_desc}\n{'请在审批管理页面确认此操作' if safety['require_approval'] else '确认执行此操作？'}",
                            "status": "pending_approval" if safety["require_approval"] else "pending_confirm",
                            "expiresAt": expires_at.isoformat() if safety["require_approval"] else None,
                        })}

                        local_tool_records.append({
                            "id": tool_call_id, "toolName": tool_name,
                            "params": tool_args, "riskLevel": safety["risk_level"],
                            "status": "pending_approval" if safety["require_approval"] else "pending_confirm",
                            "approvalId": new_approval.id if safety["require_approval"] else None,
                        })

                        await save_message(db, session_id, "tool_call", "",
                                           tool_calls=local_tool_records, trace_id=trace_id)
                        await db.commit()

                        yield {"event": "message_done", "data": json.dumps({
                            "messageId": assistant_msg_id,
                            "traceId": trace_id,
                            "status": "awaiting_user_action",
                            "approvalId": new_approval.id if safety["require_approval"] else None,
                        })}
                        return

                    # L1 或其他安全操作：直接执行
                    yield {"event": "tool_call", "data": json.dumps({
                        "id": tool_call_id,
                        "toolName": tool_name,
                        "params": tool_args,
                        "riskLevel": risk,
                        "status": "executing",
                    })}

                    exec_result = execute_tool(tool_name, tool_args)

                    yield {"event": "tool_result", "data": json.dumps({
                        "toolName": tool_name,
                        "status": "completed",
                        "result": exec_result,
                    })}

                    local_tool_records.append({
                        "id": tool_call_id, "toolName": tool_name,
                        "params": tool_args, "riskLevel": risk,
                        "status": "completed", "result": exec_result,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(exec_result, ensure_ascii=False),
                    })

                tool_call_records.extend(local_tool_records)
                await save_message(db, session_id, "tool_call", "",
                                   tool_calls=local_tool_records, trace_id=trace_id)

                if not any(tc["status"] == "completed" for tc in local_tool_records):
                    yield {"event": "message_done", "data": json.dumps({
                        "messageId": assistant_msg_id,
                        "traceId": trace_id,
                        "status": "some_blocked",
                    })}
                    return

                continue
            else:
                break

        except Exception as e:
            yield {"event": "token", "data": json.dumps({"token": f"\n\n[Agent 调用出错: {str(e)}]"})}
            break

    await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)

    # 工具调用记录保存在 assistant 之后，确保前端分组正确
    await save_message(db, session_id, "tool_call", "",
                       tool_calls=[tool_call_record], trace_id=trace_id)

    # 审计
    try:
        from app.models.audit import AuditRecord
        tools_used = list(set(tc["toolName"] for tc in tool_call_records)) if tool_call_records else []
        risks = [tc.get("riskLevel", "L1") for tc in tool_call_records] if tool_call_records else ["L1"]
        max_risk = "L4" if "L4" in risks else ("L3" if "L3" in risks else ("L2" if "L2" in risks else "L1"))
        audit = AuditRecord(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            event_type="chat_resume",
            summary=f"{'审批' if approval_id else '确认'}恢复: {','.join(tools_used)}",
            risk_level=max_risk,
            detail_json=json.dumps({
                "approval_id": approval_id or pe.approval_id,
                "pending_execution_id": pending_execution_id or pe.id,
                "tools": [{"name": tc["toolName"], "status": tc.get("status"), "risk": tc.get("riskLevel")}
                          for tc in (tool_call_records or [])],
            }, ensure_ascii=False),
        )
        db.add(audit)
        await db.commit()
    except Exception:
        pass

    yield {"event": "message_done", "data": json.dumps({
        "messageId": assistant_msg_id, "traceId": trace_id,
        "usage": {"outputTokens": len(full_response)},
    })}


# reload


