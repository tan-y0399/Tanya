"""
异常回退与兜底机制 — 超时终止、降级回答、失败归档、统一错误UX

处理策略:
  - 超时 → 友好提示 + 部分结果
  - 工具失败 → 降级回答 + 建议
  - LLM不可用 → 离线模式
  - 低置信度 → 追问用户
  - 安全拦截 → 解释原因
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FallbackReason(Enum):
    TIMEOUT = "timeout"
    TOOL_FAILURE = "tool_failure"
    LLM_UNAVAILABLE = "llm_unavailable"
    LOW_CONFIDENCE = "low_confidence"
    SECURITY_BLOCK = "security_block"
    SSH_UNAVAILABLE = "ssh_unavailable"
    UNKNOWN = "unknown"


FALLBACK_MESSAGES = {
    FallbackReason.TIMEOUT: {
        "user_message": (
            "[超时] 操作超时，服务器响应时间过长。\n\n"
            "建议：\n"
            "- 检查远程麒麟服务器是否在线\n"
            "- 简化查询条件后重试\n"
            "- 稍后重试"
        ),
        "severity": "warning",
        "retryable": True,
    },
    FallbackReason.TOOL_FAILURE: {
        "user_message": (
            "[工具失败] 工具执行失败，未能完成操作。\n\n"
            "可能原因：\n"
            "- 远程服务器命令执行异常\n"
            "- 权限不足\n"
            "- 目标资源不存在\n\n"
            "请检查后重试，或尝试其他方式查询。"
        ),
        "severity": "warning",
        "retryable": True,
    },
    FallbackReason.LLM_UNAVAILABLE: {
        "user_message": (
            "[服务不可用] AI 推理服务暂时不可用，无法处理您的请求。\n\n"
            "请检查：\n"
            "- DeepSeek API 密钥是否有效\n"
            "- 网络连接是否正常\n"
            "- API 额度是否耗尽\n\n"
            "基础查询功能（如服务器状态查看）可能仍可使用。"
        ),
        "severity": "error",
        "retryable": True,
    },
    FallbackReason.LOW_CONFIDENCE: {
        "user_message": (
            "[低置信度] 我不太确定您想做什么，能否更具体地描述一下？\n\n"
            "例如：\n"
            "- 查看 /var/log 目录下的文件\n"
            "- 检查 nginx 服务是否正常运行\n"
            "- 分析系统 CPU 使用率高的原因\n"
        ),
        "severity": "info",
        "retryable": True,
    },
    FallbackReason.SECURITY_BLOCK: {
        "user_message": (
            "[安全拦截] 该操作已被安全策略拦截。\n\n"
            "原因：操作涉及高风险命令或敏感资源。\n"
            "如需执行，请通过审批流程提交申请。"
        ),
        "severity": "error",
        "retryable": False,
    },
    FallbackReason.SSH_UNAVAILABLE: {
        "user_message": (
            "[SSH不可用] 无法连接到麒麟远程服务器 (SSH)。\n\n"
            "请检查：\n"
            "- 服务器是否在线\n"
            "- SSH 密钥配置是否正确\n"
            "- 防火墙是否放行 SSH 端口\n\n"
            "您可以在「服务器管理」页面测试连接。"
        ),
        "severity": "error",
        "retryable": True,
    },
    FallbackReason.UNKNOWN: {
        "user_message": (
            "[未知错误] 处理您的请求时发生了未知错误。\n\n"
            "请稍后重试，或联系管理员查看系统日志。"
        ),
        "severity": "error",
        "retryable": True,
    },
}


# ═══════════════════════════════════════════
# 降级策略
# ═══════════════════════════════════════════
def get_fallback(reason: FallbackReason, detail: str = "") -> dict:
    """获取标准化的兜底消息"""
    fb = FALLBACK_MESSAGES.get(reason, FALLBACK_MESSAGES[FallbackReason.UNKNOWN])
    msg = fb["user_message"]
    if detail:
        msg += f"\n\n详细信息：{detail}"
    return {
        "event": "error_fallback",
        "data": json.dumps({
            "type": reason.value,
            "message": msg,
            "severity": fb["severity"],
            "retryable": fb["retryable"],
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat(),
        }, ensure_ascii=False),
    }


def get_partial_result(completed_steps: list, failed_step_name: str,
                       reason: FallbackReason) -> dict:
    """生成部分结果（某些步骤成功但后来失败了）"""
    completed_names = [s.get("name", s.get("toolName", "?")) for s in completed_steps]
    msg = (
        f"[部分完成] 任务部分完成。\n\n"
        f"已完成 {len(completed_steps)} 个步骤：{', '.join(completed_names)}\n"
        f"在「{failed_step_name}」步骤遇到问题。\n\n"
        f"已完成的操作结果已保存，您可以基于此继续操作。"
    )
    return {
        "event": "partial_result",
        "data": json.dumps({
            "message": msg,
            "completedSteps": completed_steps,
            "failedStep": failed_step_name,
            "reason": reason.value,
            "completionPercent": min(len(completed_steps) / max(len(completed_steps) + 1, 1) * 100, 90),
        }, ensure_ascii=False),
    }


def classify_fallback(exception: Exception) -> FallbackReason:
    """从异常类型推断回退原因"""
    import httpx
    name = type(exception).__name__

    if name in ("TimeoutError", "ReadTimeout", "ConnectTimeout"):
        return FallbackReason.TIMEOUT
    if name in ("ConnectError", "ConnectionError", "SSHException"):
        return FallbackReason.SSH_UNAVAILABLE
    if name in ("HTTPStatusError", "HTTPError"):
        return FallbackReason.LLM_UNAVAILABLE

    return FallbackReason.UNKNOWN


def build_error_log(reason: FallbackReason, detail: str, user_input: str = "",
                    trace_id: str = "", session_id: str = "") -> dict:
    """构建结构化错误日志，用于审计和分析"""
    return {
        "type": reason.value,
        "detail": detail[:500],
        "userInput": user_input[:200],
        "traceId": trace_id,
        "sessionId": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "recommendation": _get_recommendation(reason),
    }


def _get_recommendation(reason: FallbackReason) -> str:
    recs = {
        FallbackReason.TIMEOUT: "检查网络连接和服务器负载，考虑增加超时时间",
        FallbackReason.TOOL_FAILURE: "检查远程服务器命令权限和资源状态",
        FallbackReason.LLM_UNAVAILABLE: "检查API密钥和网络连接，验证API服务状态",
        FallbackReason.LOW_CONFIDENCE: "优化意图识别规则，增加训练样本",
        FallbackReason.SECURITY_BLOCK: "通过审批流程或调整安全策略处理",
        FallbackReason.SSH_UNAVAILABLE: "检查SSH服务和密钥配置",
        FallbackReason.UNKNOWN: "查看完整系统日志排查",
    }
    return recs.get(reason, "排查系统日志")
