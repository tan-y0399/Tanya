import asyncio
import json
import logging
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
from app.services.tool_definitions import TOOLS, SYSTEM_PROMPT
from app.services.intent_router import intent_router, IntentType
from app.services.performance_telemetry import TraceTelemetry, record_trace
from app.services.security_workflow import _detect_prompt_injection  # 保留兼容

logger = logging.getLogger(__name__)


# ============================================================
# 工具执行器 —— 通过 SSH 在远程麒麟VM上真实执行
# ============================================================
def execute_tool(name: str, args: dict) -> dict:
    """执行工具调用，通过 MCP 协议转发到远程麒麟VM执行。

    两层调度:
      1. MCP adapter — 标准化协议 + 安全校验 + 审计
      2. remote_executor — SSH 转发 + 沙箱执行
    """
    from app.services.remote_executor import execute_tool as remote_exec

    # ── 通过 MCP registry 查找工具定义 ──
    try:
        from app.mcp.registry import get_tool_definition, call_tool
        mcp_def = get_tool_definition(name)
    except Exception:
        mcp_def = None

    # 工具名映射：chat_service 标准名 → remote_executor 内部名
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

    # ── 优先通过 MCP protocol 调用 ──
    if mcp_def:
        try:
            mcp_result = call_tool(name, args)
            # MCP registry 可能返回了结果，也可能没有找到对应实现
            if mcp_result and not isinstance(mcp_result, dict) and mcp_result.get("_not_found"):
                pass  # fall through to remote_exec
            elif mcp_result:
                return mcp_result
        except Exception:
            pass  # MCP 调用失败则回退到远程执行

    # ── 回退：直接调用远程执行器 ──
    if name in tool_map:
        return remote_exec(tool_map[name], **args)

    if name == "search_journal_logs":
        service = args.get("service", "")
        priority = args.get("priority", "")
        lines = args.get("lines", 20)
        cmd = "journalctl"
        if service:
            cmd += " -u " + service
        if priority:
            prio_map = {"err": "3", "warning": "4", "info": "6"}
            cmd += " -p " + prio_map.get(priority, "6")
        cmd += " -n " + str(lines) + " --no-pager 2>/dev/null"
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

    return {"success": False, "error": "未知工具: " + name}


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
      L1 🟢: 安全操作，直接执行
      L2 🟡: 低风险，用户确认后执行
      L3 🟠: 中等风险，需管理员审批
      L4 🟠→🔴: 高风险，需管理员审批
      L5 🔴: 致命风险，需管理员审批/禁止
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
        # L3: 中等风险，需管理员审批
        if risk == "L3":
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = True
            return result
        # L4/L5: 必须管理员审批
        if risk in ("L4", "L5"):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = True
            return result
        if risk == "L2":
            result["safe"] = False
            result["require_confirm"] = True
            return result
        return result

    # kill_process: TERM=L2需确认, KILL=L4需审批
    if tool_name == "kill_process":
        signal = tool_args.get("signal", "").upper()
        if signal in ("KILL", "9"):
            result["safe"] = False
            result["require_approval"] = True
            result["require_confirm"] = True
            result["risk_level"] = "L4"
            return result
        result["safe"] = False
        result["require_confirm"] = True
        result["risk_level"] = "L2"
        return result

    # manage_service: start=L2需确认, stop/restart/reload=L4需审批
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

    # L3: 中等风险，需管理员审批
    if risk == "L3":
        result["safe"] = False
        result["require_approval"] = True
        result["require_confirm"] = True
        return result

    # L4~L5: 必须管理员审批
    if risk in ("L4", "L5"):
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
    """调用 DeepSeek API，带重试逻辑"""
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

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if stream:
                    async with client.stream("POST", url, headers=headers, json=payload) as resp:
                        if resp.status_code >= 400:
                            body = await resp.aread()
                            last_error = Exception(f"DeepSeek HTTP {resp.status_code}: {body.decode()[:200]}")
                            if resp.status_code == 429:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            break
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    return
                                try:
                                    data = json.loads(data_str)
                                    yield data
                                except Exception:
                                    continue
                        return
                else:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    yield resp.json()
                    return
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:
                await asyncio.sleep(2 ** attempt)
                continue
            break
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5 ** attempt)
                continue
            break

    raise last_error or Exception("DeepSeek API call failed")


# ============================================================
# Agent 处理主流程 (ReAct 循环)
# ============================================================
async def process_message(db: AsyncSession, session_id: str, content: str, user_id: str):
    """Agent 主处理流程 - SSE 流式推送（使用意图路由架构）"""
    trace_id = generate_trace_id()
    assistant_msg_id = generate_id()
    telemetry = TraceTelemetry(trace_id, session_id, user_id)

    # 会话记忆
    from app.services.session_memory import get_memory
    memory = get_memory(session_id, user_id)
    memory.total_messages += 1

    # 保存用户消息
    await save_message(db, session_id, "user", content, trace_id=trace_id)

    try:
        async for event in _process_message_impl(
            db, session_id, content, user_id, trace_id, assistant_msg_id,
            telemetry, memory,
        ):
            yield event
    except Exception as e:
        logger.exception("process_message 致命异常: %s", str(e))
        telemetry.end_step("error", error=str(e)[:200])
        record_trace(telemetry)
        yield {"event": "token", "data": json.dumps({
            "token": "\n\n⚠ 系统处理异常，请重试。Trace: {}".format(trace_id),
        })}
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id, "traceId": trace_id,
            "status": "error", "error": str(e)[:200],
        })}
        try:
            await save_message(db, session_id, "assistant",
                "⚠ 系统处理异常，请重试。Trace: {}".format(trace_id), trace_id=trace_id)
        except Exception:
            pass


async def _process_message_impl(
    db: AsyncSession, session_id: str, content: str, user_id: str,
    trace_id: str, assistant_msg_id: str, telemetry, memory,
):
    """process_message 实现体，由外层 try/except 保护"""
    telemetry.start_step("1_安全预检")
    from app.services.prompt_guard import security_gate
    security_result = await security_gate(content, use_llm=True)
    telemetry.end_step("ok", guard_pass=security_result["pass"])

    if not security_result["pass"]:
        yield {"event": "prompt_injection_detected", "data": json.dumps({
            "message": security_result["reason"],
            "severity": security_result["severity"],
            "blocked": True,
        })}
        await save_message(db, session_id, "assistant",
            f"⚠ {security_result['reason']}", trace_id=trace_id)
        try:
            from app.models.audit import AuditRecord
            audit = AuditRecord(trace_id=trace_id, session_id=session_id,
                user_id=user_id, event_type="blocked_injection",
                summary=f"注入拦截 [{security_result['severity']}]: {security_result['reason'][:100]}",
                risk_level="L5", detail_json=json.dumps(security_result, ensure_ascii=False, default=str))
            db.add(audit)
            await db.commit()
        except Exception:
            pass
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id, "traceId": trace_id, "status": "blocked_injection"})}
        return

    # 使用净化后的输入
    content = security_result.get("sanitized_input", content)

    # ── Step 2: 意图分类 ∥ RAG知识检索（并行执行）──
    telemetry.start_step("2_意图分类+RAG检索(并行)")
    import asyncio
    from app.services.intent_classifier import classify as classify_async, IntentType as NewIntentType
    from app.services.knowledge_rag import knowledge_rag
    from app.models.knowledge import KnowledgeArticle

    # 确保 RAG 索引已初始化（非阻塞预热）
    if not knowledge_rag._initialized:
        try:
            result = await db.execute(select(KnowledgeArticle))
            articles = [{"id": a.id, "title": a.title, "content": a.content,
                         "category": a.category, "tags": a.tags}
                        for a in result.scalars().all()]
            if articles:
                knowledge_rag.build_index(articles)
        except Exception:
            pass

    # 意图分类始终异步执行（含 LLM 调用，~200ms）
    intent_task = asyncio.ensure_future(classify_async(content))

    # RAG 检索直接同步执行（纯本地计算，通常 <50ms，无需线程池）
    rag_context = ""
    try:
        if knowledge_rag._initialized:
            rag_context = knowledge_rag.generate_context(content, top_k=3)
    except Exception:
        pass

    # 等待意图分类完成
    intent_result = await intent_task

    yield {"event": "intent", "data": json.dumps({
        "intent": intent_result["intent"],
        "confidence": intent_result["confidence"],
        "matchedKeywords": intent_result.get("matched_keywords", [])[:5],
        "method": intent_result.get("method", "keyword"),
    })}

    if rag_context:
        yield {"event": "rag_context", "data": json.dumps({
            "sources": [s["title"] for s in knowledge_rag.search(content, top_k=3)] if knowledge_rag._initialized else [],
        })}

    telemetry.end_step("ok", intent=intent_result["intent"],
                       confidence=intent_result.get("confidence", 0),
                       rag_hit=bool(rag_context))

    # ── Step 3: 注入二次确认 ──
    telemetry.start_step("3_注入二次确认")
    if intent_result.get("is_injection"):
        telemetry.end_step("error", blocked=True, reason="injection_detected")
        record_trace(telemetry)
        yield {"event": "prompt_injection_detected", "data": json.dumps({
            "message": "检测到潜在的提示词注入行为",
            "severity": intent_result.get("injection_severity", "medium"),
            "blocked": True,
        })}
        await save_message(db, session_id, "assistant",
            "⚠ 检测到潜在的提示词注入行为，该请求已被安全系统拦截。", trace_id=trace_id)
        yield {"event": "message_done", "data": json.dumps({
            "messageId": assistant_msg_id, "traceId": trace_id, "status": "blocked_injection"})}
        return

    telemetry.end_step("ok", intent=intent_result["intent"])
    intent = intent_result["intent"]

    # ── Step 4: 意图敏感词提醒 ──
    if intent == IntentType.HIGH_RISK.value:
        yield {"event": "risk_notice", "data": json.dumps({
            "message": "您的请求涉及高风险操作，相关指令将需要审批后方可执行。",
            "intent": "high_risk",
        })}

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

    # ── Step 5: 路由分发：纯闲聊 → Handler，其余 → ReAct 循环（可调用工具+RAG）──
    telemetry.start_step("5_路由分发")
    if intent == IntentType.GENERAL_QA.value:
        history = await get_messages(db, session_id)
        chat_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history["items"] if m["role"] in ("user", "assistant")
        ]
        from app.services.task_router import dispatch
        async for event in dispatch(
            db, session_id, content, user_id, chat_messages,
            intent_result=intent_result, trace_id=trace_id,
            assistant_msg_id=assistant_msg_id,
        ):
            yield event
        return

    # ── RAG 知识增强（已在步骤3并行完成，此处仅对尚未索引的场景做延迟初始化）──
    if rag_context is None:
        rag_context = ""
    if intent in (IntentType.KNOWLEDGE_QA.value, IntentType.FAULT_ANALYSIS.value):
        try:
            if not knowledge_rag._initialized:
                result = await db.execute(select(KnowledgeArticle))
                articles = []
                for a in result.scalars().all():
                    articles.append({"id": a.id, "title": a.title, "content": a.content,
                        "category": a.category, "tags": a.tags})
                knowledge_rag.build_index(articles)
                rag_context = knowledge_rag.generate_context(content, top_k=3)
                if rag_context:
                    yield {"event": "rag_context", "data": json.dumps({
                        "sources": [s["title"] for s in knowledge_rag.search(content, top_k=3)],
                    })}
        except Exception as e:
            logger.warning(f"RAG delayed init failed: {e}")

    # ── 任务编排器（OPS_QUERY / FAULT_ANALYSIS 时启动）──
    orchestrator = None
    if intent in (IntentType.OPS_QUERY.value, IntentType.FAULT_ANALYSIS.value):
        try:
            from app.services.task_orchestrator import TaskOrchestrator, TaskStage
            orchestrator = TaskOrchestrator(
                session_id=session_id, trace_id=trace_id, user_id=user_id)
            orchestrator.transition(TaskStage.PERCEIVING)
            yield {"event": "task_progress", "data": json.dumps(orchestrator.get_progress_event())}
        except Exception as e:
            logger.warning(f"Task orchestrator init failed: {e}")

    # 构建对话历史（含工具调用 + 会话记忆）
    history = await get_messages(db, session_id)
    memory_context = memory.build_memory_prompt()
    system_prompt = SYSTEM_PROMPT
    if memory_context:
        system_prompt += "\n" + memory_context
    if rag_context:
        system_prompt += "\n\n" + rag_context
    messages = [{"role": "system", "content": system_prompt}]
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

                    # ── 需审批（L4/L5 高危操作：重启服务、用户管理、iptables修改等）──
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
                    # 权限校验（非阻塞，记录越权操作）
                    try:
                        from app.services.permission_service import validate_operation_scope
                        perm_check = validate_operation_scope(tool_name, tool_args, "admin")
                        if not perm_check["allowed"]:
                            yield {"event": "permission_notice", "data": json.dumps({
                                "toolName": tool_name,
                                "message": perm_check["message"],
                                "restricted": True,
                            })}
                    except Exception:
                        pass  # 权限校验失败不阻塞主流程

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

                    # ── 任务编排器步骤追踪 ──
                    if orchestrator:
                        step = orchestrator.add_step(tool_name, tool_name, tool_args)
                        step.status = "completed" if result.get("success", False) else "failed"
                        step.result = result
                        from app.services.task_orchestrator import TaskStage
                        if orchestrator.steps and len(orchestrator.steps) >= 2 and orchestrator.current_stage != TaskStage.EXECUTING:
                            orchestrator.transition(TaskStage.EXECUTING)
                        yield {"event": "task_progress", "data": json.dumps(orchestrator.get_progress_event())}

                    # ── 可信度标记 ──
                    try:
                        from app.services.context_credibility import CredibilityTracker
                        tracker = CredibilityTracker()
                        tag = tracker.tag_source("system_tool", tool_name)
                        result["_credibility"] = tag
                    except Exception:
                        pass

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

        except httpx.TimeoutException as e:
            from app.services.fallback_handler import get_fallback, FallbackReason, classify_fallback, build_error_log
            fb = get_fallback(FallbackReason.TIMEOUT)
            yield fb
            full_response += "\n\n⚠ LLM 服务响应超时，请稍后重试。"
            logger.warning(f"Task timeout: {build_error_log(FallbackReason.TIMEOUT, str(e), content, trace_id, session_id)}")
            break
        except httpx.ConnectError as e:
            from app.services.fallback_handler import get_fallback, FallbackReason, build_error_log
            fb = get_fallback(FallbackReason.LLM_UNAVAILABLE)
            yield fb
            full_response += "\n\n⚠ LLM 服务暂时不可用，请检查网络连接。"
            logger.warning(f"LLM unavailable: {build_error_log(FallbackReason.LLM_UNAVAILABLE, str(e), content, trace_id, session_id)}")
            break
        except Exception as e:
            from app.services.fallback_handler import get_fallback, FallbackReason, classify_fallback, build_error_log
            reason = classify_fallback(e)
            fb = get_fallback(reason, str(e)[:200])
            yield fb
            logger.error(f"Agent error: {build_error_log(reason, str(e), content, trace_id, session_id)}")
            full_response += f"\n\n⚠ Agent 处理异常，请联系管理员。Trace: {trace_id}"
            break

    # 如果 agent 调用了工具但没有给出文字回复，自动生成摘要
    if not full_response and tool_call_records:
        completed = [tc for tc in tool_call_records if tc.get("status") == "completed"]
        failed = [tc for tc in tool_call_records if tc.get("status") != "completed"]
        parts = []
        if completed:
            parts.append("已执行 {} 个工具：{}".format(
                len(completed),
                "、".join(tc["toolName"] for tc in completed[:5])
            ))
        if failed:
            parts.append("{} 个工具执行异常".format(len(failed)))
        full_response = "。".join(parts) + "。请查看上方详情。"

    # 保存 assistant 消息
    await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)

    # 工具调用记录保存在 assistant 之后，确保前端只显示一个 Agent 头部
    if tool_call_records:
        await save_message(db, session_id, "tool_call", "",
                           tool_calls=tool_call_records, trace_id=trace_id)

    # ── Step 10: 写入审计记录 ──
    telemetry.start_step("10_审计写入")
    try:
        from app.models.audit import AuditRecord
        tools_used = list(set(tc["toolName"] for tc in tool_call_records)) if tool_call_records else []
        risks = [tc.get("riskLevel", "L1") for tc in tool_call_records] if tool_call_records else ["L1"]
        max_risk = "L4" if "L4" in risks else ("L3" if "L3" in risks else ("L2" if "L2" in risks else "L1"))
        # 合并遥测数据到审计详情
        telemetry_json = telemetry.to_audit_json()
        detail = {
            "question": content[:200],
            "answer": full_response[:300],
            "tools": [{"name": tc["toolName"], "status": tc.get("status"), "risk": tc.get("riskLevel")}
                      for tc in (tool_call_records or [])],
            "telemetry": json.loads(telemetry_json),
        }
        audit = AuditRecord(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            event_type="chat",
            summary=content[:100] if not tools_used else "调用 {} | {}".format(','.join(tools_used), content[:60]),
            risk_level=max_risk,
            detail_json=json.dumps(detail, ensure_ascii=False),
        )
        db.add(audit)
        await db.commit()
        telemetry.end_step("ok")
    except Exception:
        telemetry.end_step("error")
        pass  # 审计记录写入失败不阻塞对话

    # ── Step 11: 遥测反馈 —— 记录全链路耗时 ──
    record_trace(telemetry)

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
                PendingExecution.status.in_(["pending", "approved"]),
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
