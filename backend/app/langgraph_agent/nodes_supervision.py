"""
人类监督分阶段节点 — 8 阶段优化方案对接
"""
import json
import logging
from datetime import datetime

from app.core.config import settings
from app.services.human_supervision import (
    context_injection_recheck,
    build_diagnostic_plan,
    enrich_diagnostic_plan_with_env,
    run_env_precheck,
)
from app.services.agent.chains import dispatch_chain, ChainId
from app.services.agent.file_protection import build_whitelist, check_command_against_whitelist
from app.services.agent.snapshot_manager import SnapshotManager
from app.services.agent.knowledge_cycle import ingest_ops_report
from app.services.chat_service import preview_tool_command
from app.services.intent_classifier import IntentType

from .state import AgentState, AgentStage

logger = logging.getLogger(__name__)


async def security_recheck_node(state: AgentState) -> AgentState:
    intent = state.get("intent") or ""
    rag = state.get("rag_context") or ""
    text = state.get("sanitized_input") or state["user_input"]
    recheck = context_injection_recheck(text, intent, rag)
    if not recheck["pass"]:
        return {
            **state,
            "current_stage": AgentStage.FALLBACK,
            "blocked": True,
            "block_reason": recheck["reason"],
            "recheck_passed": False,
            "final_status": "blocked_injection",
        }
    return {**state, "current_stage": AgentStage.ROUTE_DISPATCH, "recheck_passed": True}


async def route_dispatch_node(state: AgentState) -> AgentState:
    """阶段4：三路分流 link_a / link_b / link_c"""
    intent_result = state.get("intent_result") or {}
    text = state.get("sanitized_input") or state["user_input"]
    chain = dispatch_chain(text, intent_result)

    return {
        **state,
        "intent": intent_result.get("intent") or state.get("intent"),
        "intent_result": intent_result,
        "route_path": chain["route_path"],
        "workflow_link": chain["link"],
        "link_label": chain.get("link_label"),
        "link_description": chain.get("link_description"),
        "route_reason": chain.get("reason"),
        "current_stage": AgentStage.ROUTE_DISPATCH,
    }


async def chain_b_tool_safety_node(state: AgentState) -> AgentState:
    """链路 B：轻量 ReAct 入口安全预检，跳过方案直接执行。"""
    return {
        **state,
        "plan_confirmed": True,
        "current_stage": AgentStage.DIALOG_MANAGE,
        "final_status": "executing",
    }


async def diagnostic_plan_node(state: AgentState) -> AgentState:
    """链路 C 子步骤1-2：环境感知 + 方案生成"""
    if state.get("confirm_plan_id"):
        return {**state, "plan_confirmed": True, "current_stage": AgentStage.ENV_PRECHECK}

    if state.get("workflow_link") == ChainId.LIGHTWEIGHT_REACT.value:
        return {**state, "plan_confirmed": True, "current_stage": AgentStage.DIALOG_MANAGE}

    if not settings.enable_diagnostic_plan:
        return {**state, "plan_confirmed": True, "current_stage": AgentStage.ENV_PRECHECK}

    intent = state.get("intent") or ""
    text = state.get("sanitized_input") or state["user_input"]
    rag = state.get("rag_context") or ""
    sensing = "fault_diagnosis" if intent == IntentType.FAULT_ANALYSIS.value else "full_check"

    plan = await build_diagnostic_plan(text, intent, rag)
    plan = await enrich_diagnostic_plan_with_env(
        plan, text, rag, sensing_mode=sensing, server_id=state.get("server_id"),
    )
    whitelist = plan.get("file_protection_whitelist") or build_whitelist(text, rag)

    return {
        **state,
        "diagnostic_plan": plan,
        "file_protection_whitelist": whitelist,
        "plan_confirmed": False,
        "current_stage": AgentStage.DIAGNOSTIC_PLAN,
        "awaiting_user_action": True,
        "final_status": "awaiting_plan_confirm",
    }


async def env_precheck_node(state: AgentState) -> AgentState:
    """链路 C 子步骤3：快照 + 环境预检"""
    mgr = SnapshotManager(state["session_id"], state["trace_id"])
    snap = await mgr.create(state.get("server_id"))
    updates = {
        **state,
        "env_precheck": snap,
        "snapshot_id": snap.get("snapshot_id"),
        "current_stage": AgentStage.DIALOG_MANAGE,
    }
    if not snap.get("passed"):
        updates["blocked"] = True
        updates["block_reason"] = "环境预检查未通过"
        updates["current_stage"] = AgentStage.FALLBACK
        updates["final_status"] = "env_failed"
    return updates


async def atomic_step_validate_node(state: AgentState) -> AgentState:
    """原子化分步：校验当前命令是否触碰文件保护白名单"""
    whitelist = state.get("file_protection_whitelist") or []
    tool_calls = state.get("tool_calls") or []
    for tc in tool_calls:
        preview = preview_tool_command(tc.get("tool_name", ""), tc.get("tool_args") or {})
        chk = check_command_against_whitelist(preview, whitelist)
        if chk["blocked"]:
            return {
                **state,
                "blocked": True,
                "block_reason": chk["message"],
                "current_stage": AgentStage.FALLBACK,
                "final_status": "blocked",
            }
    return {**state, "current_stage": AgentStage.SAFETY_CHECK}


async def fact_check_node(state: AgentState) -> AgentState:
    intent = state.get("intent")
    if intent != IntentType.KNOWLEDGE_QA.value:
        return {**state, "fact_check_passed": True, "current_stage": AgentStage.KB_INGEST}

    response = state.get("final_response") or ""
    rag = state.get("rag_context") or ""
    notes = []
    if not rag and any(k in response for k in ("已执行", "已完成", "成功清理", "已关闭")):
        notes.append("无知识库依据却声称已执行操作")
        response += "\n\n> ⚠ 提示：以上为知识性说明，未对服务器执行任何命令。"

    return {
        **state,
        "final_response": response,
        "fact_check_passed": len(notes) == 0,
        "fact_check_notes": "; ".join(notes) if notes else None,
        "current_stage": AgentStage.KB_INGEST,
    }


async def kb_ingest_node(state: AgentState) -> AgentState:
    report = state.get("ops_report")
    if not report:
        return {**state, "current_stage": AgentStage.COMPLETED}

    try:
        from app.core.database import async_session
        title = f"[自动报告] {state.get('user_input', '')[:40]}"
        async with async_session() as db:
            article_id = await ingest_ops_report(
                db, title=title, content=report,
                trace_id=state.get("trace_id", ""),
            )
            if article_id:
                return {**state, "kb_article_id": article_id, "current_stage": AgentStage.COMPLETED}
    except Exception as e:
        logger.warning("kb_ingest failed: %s", e)
    return {**state, "current_stage": AgentStage.COMPLETED}


async def rollback_node(state: AgentState) -> AgentState:
    """全量/单步回滚节点"""
    try:
        from app.core.database import async_session
        from app.services.agent.rollback_manager import RollbackManager
        async with async_session() as db:
            mgr = RollbackManager(state["session_id"], state.get("snapshot_id"))
            result = await mgr.rollback_full(db)
            return {
                **state,
                "current_stage": AgentStage.COMPLETED,
                "final_status": "rolled_back" if result.get("success") else "rollback_failed",
                "final_response": (state.get("final_response") or "") + f"\n\n回滚结果: {json.dumps(result, ensure_ascii=False)[:500]}",
            }
    except Exception as e:
        return {**state, "error": str(e), "current_stage": AgentStage.FALLBACK, "final_status": "rollback_failed"}


def append_execution_log(state: AgentState, tool_name: str, tool_args: dict, result: dict) -> list:
    logs = list(state.get("execution_command_log") or [])
    preview = preview_tool_command(tool_name, tool_args)
    reversible = tool_name == "manage_service" and tool_args.get("action") in ("start", "stop", "restart")
    logs.append({
        "tool_name": tool_name,
        "command_preview": preview,
        "reversible": reversible,
        "at": datetime.utcnow().isoformat(),
        "result_success": result.get("success"),
    })
    return logs
