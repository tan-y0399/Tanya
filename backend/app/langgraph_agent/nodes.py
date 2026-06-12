"""
LangGraph 节点实现 - 各处理阶段
"""
import asyncio
import json
import logging
import httpx
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.services.intent_classifier import classify as classify_intent
from app.services.prompt_guard import security_gate
from app.services.knowledge_rag import knowledge_rag
from app.services.session_memory import get_memory
from app.services.tool_definitions import SYSTEM_PROMPT, TOOLS
from app.core.command_security import analyze_command, get_risk_level_info
from app.core.config import settings

from .state import AgentState, AgentStage, RiskLevel, ToolCall, ReasoningStep

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 故障分析引导提示词（Phase 4: 多轮根因引导）
# ═══════════════════════════════════════════

FAULT_ANALYSIS_GUIDANCE = """
## 故障诊断引导

你正在执行故障根因分析。请按照以下结构化流程进行诊断：

### 诊断流程
1. **信息收集** — 了解故障现象：什么服务出问题？什么时间开始？有什么错误信息？
2. **假设生成** — 基于现象提出2-3个最可能的原因假设
3. **验证测试** — 依次验证每个假设，使用只读工具获取数据（日志、指标、状态）
4. **根因确认** — 基于验证结果确认根因
5. **修复建议** — 提出具体的修复方案和风险评估

### 诊断原则
- 从最可能的原因开始排查，逐步缩小范围
- 每次工具调用后，分析结果再决定下一步
- 优先使用只读工具，修改操作需用户确认
- 用表格或结构化格式呈现诊断结论
"""


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def _generate_id() -> str:
    return uuid.uuid4().hex[:12]


def _detect_diagnostic_stage(content: str, current: Optional[str] = None) -> str:
    """从LLM输出中检测当前诊断阶段"""
    content_lower = content.lower()
    # 信息收集阶段的关键词
    if any(kw in content_lower for kw in ["查看", "检查", "获取", "查询", "状态", "日志", "指标",
                                             "先了解", "先看看", "收集", "get_", "list_", "read_"]):
        return "info_gathering"
    # 假设生成阶段
    if any(kw in content_lower for kw in ["可能", "假设", "怀疑", "推测", "原因可能是", "hypothesis",
                                             "可能是", "也许是", "有几个可能"]):
        return "hypothesis"
    # 验证阶段
    if any(kw in content_lower for kw in ["验证", "测试", "确认", "检测", "排查", "verify", "test", "check"]):
        return "verification"
    # 根因确认
    if any(kw in content_lower for kw in ["根因", "根本原因", "root cause", "确认是", "原因是",
                                             "症结", "根源", "定位到"]):
        return "root_cause"
    # 修复建议
    if any(kw in content_lower for kw in ["修复", "解决", "建议", "方案", "处理", "remediation",
                                             "fix", "solution", "操作步骤"]):
        return "remediation"
    return current or "info_gathering"


def _tool_risk_level(tool_name: str, tool_args: dict) -> str:
    """获取工具调用的风险级别"""
    args = tool_args or {}
    risk_map = {
        "get_system_info": "L1", "get_cpu_info": "L1", "get_memory_info": "L1",
        "get_disk_usage": "L1", "list_processes": "L1", "get_process_detail": "L1",
        "get_network_connections": "L1", "search_journal_logs": "L1", "get_logs": "L1",
        "get_file_list": "L1", "read_file": "L1", "get_users": "L1", "get_groups": "L1",
        "get_service_status": "L1", "summarize_task": "L1",
        "kill_process": "L3", "manage_service": "L3", "execute_command": "L3",
    }
    risk = risk_map.get(tool_name, "L3")

    if tool_name == "kill_process":
        if args.get("signal", "").upper() in ("KILL", "9"):
            risk = "L4"
    if tool_name == "manage_service":
        if args.get("action", "").lower() in ("stop", "restart"):
            risk = "L4"
    if tool_name == "execute_command":
        command = args.get("command", "")
        analysis = analyze_command(command)
        if analysis.get("success"):
            risk = analysis.get("risk_level", "L3")
    return risk


def _check_tool_safety(tool_name: str, tool_args: dict) -> dict:
    """检查工具调用安全性"""
    risk = _tool_risk_level(tool_name, tool_args)

    result = {
        "safe": True, "blocked": False, "block_message": None,
        "require_approval": False, "require_confirm": False, "risk_level": risk,
    }

    if risk == "L1":
        return result

    if tool_name == "execute_command":
        command = tool_args.get("command", "")
        if not command.strip():
            return {**result, "safe": False, "blocked": True, "block_message": "空命令"}

        analysis = analyze_command(command)
        if analysis.get("blocked"):
            return {**result, "safe": False, "blocked": True,
                    "block_message": analysis.get("block_message", "此命令被安全策略阻止"),
                    "risk_level": analysis.get("risk_level", risk)}
        if analysis.get("require_approval"):
            return {**result, "safe": False, "require_approval": True,
                    "require_confirm": analysis.get("require_confirm", True),
                    "risk_level": analysis.get("risk_level", risk)}
        if analysis.get("require_confirm"):
            return {**result, "safe": False, "require_confirm": True,
                    "risk_level": analysis.get("risk_level", risk)}
        if risk in ("L3", "L4", "L5"):
            return {**result, "safe": False, "require_approval": True, "require_confirm": True}
        if risk == "L2":
            return {**result, "safe": False, "require_confirm": True}
        return result

    if tool_name == "kill_process":
        if tool_args.get("signal", "").upper() in ("KILL", "9"):
            return {**result, "safe": False, "require_approval": True,
                    "require_confirm": True, "risk_level": "L3"}
        return {**result, "safe": False, "require_confirm": True, "risk_level": "L2"}

    if tool_name == "manage_service":
        if tool_args.get("action", "").lower() in ("stop", "restart", "reload"):
            return {**result, "safe": False, "require_approval": True,
                    "require_confirm": True, "risk_level": "L4"}
        return {**result, "safe": False, "require_confirm": True, "risk_level": "L2"}

    if risk == "L2":
        return {**result, "safe": False, "require_confirm": True}
    if risk in ("L3", "L4", "L5"):
        return {**result, "safe": False, "require_approval": True, "require_confirm": True}
    return result


def _execute_tool(name: str, args: dict) -> dict:
    """执行工具调用 - MCP优先 + 沙箱保护"""
    from app.services.remote_executor import execute_tool as remote_exec

    tool_map = {
        "get_system_info": "get_system_info", "get_cpu_info": "get_cpu_info",
        "get_memory_info": "get_memory_info", "get_disk_usage": "get_disk_info",
        "list_processes": "get_process_list", "get_network_connections": "get_network_connections",
        "get_process_detail": "get_process_detail", "kill_process": "kill_process",
        "get_service_status": "get_service_status", "manage_service": "manage_service",
        "get_file_list": "get_file_list", "read_file": "read_file",
        "get_logs": "get_logs", "get_users": "get_users", "get_groups": "get_groups",
    }

    # 命令类工具使用沙箱包装
    if name == "execute_command":
        from app.services.sandbox_executor import build_safe_command
        command = args.get("command", "")
        if command.strip():
            safe_result = build_safe_command(command, timeout=args.get("timeout", 30))
            if not safe_result["safe"]:
                return {"success": False, "error": f"沙箱拒绝: {safe_result['warnings']}"}
            return remote_exec("run_command", command=safe_result["command"],
                              timeout=args.get("timeout", 30))

    if name in tool_map:
        from app.services.tool_args import normalize_tool_args
        remote_name = tool_map[name]
        return remote_exec(remote_name, **normalize_tool_args(remote_name, args))

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

    if name == "summarize_task":
        return {"success": True, "data": {"summary": args.get("summary", ""), "task_completed": True}}

    return {"success": False, "error": f"未知工具: {name}"}


# ═══════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════

async def _call_llm(messages: List[Dict], stream: bool = False):
    """调用 DeepSeek API"""
    from app.services.chat_service import prepare_messages_for_llm
    messages = prepare_messages_for_llm(messages)
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

    max_retries = 2
    for attempt in range(max_retries):
        try:
            if stream:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as resp:
                        if resp.status_code >= 400:
                            body = await resp.aread()
                            if resp.status_code == 429 and attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            raise Exception(f"LLM HTTP {resp.status_code}: {body.decode()[:200]}")
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    return
                                try:
                                    yield json.loads(data_str)
                                except Exception:
                                    continue
                        return
            else:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    yield resp.json()
                    return
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5 ** attempt)
                continue
            raise


async def _call_llm_sync(messages: List[Dict]) -> Dict:
    """非流式调用 LLM，返回完整响应"""
    result = None
    async for chunk in _call_llm(messages, stream=False):
        result = chunk
    if result is None:
        raise Exception("LLM returned no response")
    return result


# ═══════════════════════════════════════════
# 节点1: 意图风险过滤层
# ═══════════════════════════════════════════

async def intent_risk_filter_node(state: AgentState) -> AgentState:
    """注入检测 + 意图分类 + 风险初判"""
    user_input = state["user_input"]
    logger.info(f"[意图风险过滤] 处理输入: {user_input[:50]}...")

    # 1. 注入检测 v2（含角色预检）
    role = state.get("user_role", "user")
    text = state.get("sanitized_input") or user_input
    security_result = await security_gate(text, use_llm=True, user_role=role)
    if not security_result["pass"]:
        return {
            **state,
            "current_stage": AgentStage.FALLBACK,
            "is_injection": True,
            "injection_severity": security_result["severity"],
            "blocked": True,
            "block_reason": security_result["reason"],
        }

    # 2. 意图分类
    intent_result = await classify_intent(text)
    if intent_result.get("is_injection"):
        return {
            **state,
            "current_stage": AgentStage.FALLBACK,
            "is_injection": True,
            "injection_severity": intent_result.get("injection_severity", "medium"),
            "blocked": True,
            "block_reason": "检测到潜在的提示词注入行为",
        }

    intent = intent_result["intent"]

    return {
        **state,
        "current_stage": AgentStage.PARALLEL_PROCESS,
        "intent": intent,
        "intent_confidence": intent_result["confidence"],
        "is_injection": False,
        "injection_severity": None,
        "blocked": False,
        "intent_result": intent_result,
        "security_gate_details": security_result.get("details"),
        "sanitized_input": security_result.get("sanitized_input", text),
    }


# ═══════════════════════════════════════════
# 节点2: 并行执行 - 意图分类器 + 知识库检索
# ═══════════════════════════════════════════

async def parallel_intent_rag_node(state: AgentState) -> AgentState:
    """并行: 意图分类器 & 知识库检索"""
    user_input = state["user_input"]
    intent = state.get("intent")

    logger.info(f"[并行执行] 意图: {intent}, 并行检索知识库...")

    async def _rag_search():
        if intent in ["knowledge_qa", "fault_analysis", "ops_query"]:
            try:
                rag_context = knowledge_rag.generate_context(user_input, top_k=3)
                rag_sources = knowledge_rag.search(user_input, top_k=3)
                return rag_context, rag_sources
            except Exception as e:
                logger.warning(f"RAG检索失败: {e}")
                return "", []
        return "", []

    rag_task = asyncio.create_task(_rag_search())
    rag_context, rag_sources = await rag_task

    return {
        **state,
        "current_stage": AgentStage.FUSION,
        "rag_context": rag_context,
        "rag_sources": rag_sources,
    }


# ═══════════════════════════════════════════
# 节点3: 融合层
# ═══════════════════════════════════════════

async def fusion_node(state: AgentState) -> AgentState:
    """融合: SYSTEM_PROMPT + 意图 + RAG + 记忆 → 构建 messages"""
    user_input = state["user_input"]
    intent = state.get("intent")
    rag_context = state.get("rag_context", "")
    intent_result = state.get("intent_result", {})

    logger.info("[融合层] 构建融合提示词...")

    # 构建系统提示词
    fused_parts = [SYSTEM_PROMPT]

    if intent_result:
        intent_meta = intent_result.get("metadata", {})
        fused_parts.append(
            f"\n## 用户意图分析\n"
            f"- 意图类型: {intent_meta.get('label', intent)}\n"
            f"- 置信度: {state.get('intent_confidence', 0):.2f}"
        )
        entities = intent_result.get("entities", {})
        if entities:
            entity_str = ", ".join([f"{k}={v}" for k, v in entities.items() if v])
            fused_parts.append(f"- 提取实体: {entity_str}")

    if rag_context:
        fused_parts.append(f"\n## 相关知识库\n{rag_context}")

    # 故障分析引导
    if intent == "fault_analysis":
        fused_parts.append(FAULT_ANALYSIS_GUIDANCE)

    # 会话记忆
    session_id = state["session_id"]
    user_id = state["user_id"]
    memory = get_memory(session_id, user_id)
    memory_prompt = memory.build_memory_prompt()
    if memory_prompt:
        fused_parts.append(memory_prompt)

    fused_prompt = "\n".join(fused_parts)

    # 构建初始 messages 列表
    messages = [{"role": "system", "content": fused_prompt}]

    # 加载对话历史
    for msg in state.get("dialog_history", []):
        role = msg.get("role", "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": msg.get("content", "")})
        elif role == "tool_call" and msg.get("toolCalls"):
            for tc in msg["toolCalls"]:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc.get("id", _generate_id()),
                        "type": "function",
                        "function": {
                            "name": tc.get("toolName", tc.get("tool_name", "")),
                            "arguments": json.dumps(tc.get("params", tc.get("tool_args", {})), ensure_ascii=False),
                        },
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(tc.get("result", {}), ensure_ascii=False),
                })

    # 添加当前用户消息
    messages.append({"role": "user", "content": user_input})

    return {
        **state,
        "current_stage": AgentStage.DIALOG_MANAGE,
        "fused_prompt": fused_prompt,
        "messages": messages,
    }


# ═══════════════════════════════════════════
# 节点4: 对话管理引擎
# ═══════════════════════════════════════════

async def dialog_manager_node(state: AgentState) -> AgentState:
    """对话管理: 更新会话记忆和状态"""
    logger.info("[对话管理] 更新会话上下文...")

    session_id = state["session_id"]
    user_id = state["user_id"]
    memory = get_memory(session_id, user_id)
    memory.total_messages += 1

    return {
        **state,
        "current_stage": AgentStage.REASONING,
        "session_memory": memory.to_dict(),
        "round_count": 0,
        "max_rounds": getattr(settings, 'max_conversation_rounds', 5),
        "tool_calls": [],
        "execution_results": [],
    }


# ═══════════════════════════════════════════
# 节点5: 推理决策层 (核心实现)
# ═══════════════════════════════════════════

async def reasoning_node(state: AgentState) -> AgentState:
    """
    推理决策层 - LLM推理 + 任务规划 + 工具调用决策

    调用 DeepSeek API，支持 function calling。
    如果是 ReAct 循环的后续轮次，messages 中已包含之前的工具调用结果。
    """
    messages = state.get("messages", [])
    round_count = state.get("round_count", 0)
    max_rounds = state.get("max_rounds", 5)

    logger.info(f"[推理决策] 第 {round_count + 1} 轮推理, 消息数: {len(messages)}")

    if round_count >= max_rounds:
        logger.warning(f"[推理决策] 达到最大轮次 {max_rounds}，强制结束")
        return {
            **state,
            "current_stage": AgentStage.RESPONSE_ASSEMBLY,
            "reasoning_output": "已达到最大处理轮次，正在汇总结果...",
            "tool_calls": [],
        }

    reasoning_steps = list(state.get("reasoning_steps", []))
    streaming_tokens = list(state.get("streaming_tokens", []))

    try:
        # 使用流式调用实时收集 token
        content = ""
        raw_tool_calls = []
        tool_call_buffers: Dict[int, Dict] = {}

        async for chunk in _call_llm(messages, stream=True):
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {})

            # 文本 token
            if "content" in delta and delta["content"]:
                token = delta["content"]
                content += token
                streaming_tokens.append(token)

            # 工具调用 token
            if "tool_calls" in delta:
                for tc_delta in delta["tool_calls"]:
                    idx = tc_delta.get("index", 0)
                    if idx not in tool_call_buffers:
                        tool_call_buffers[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                    buf = tool_call_buffers[idx]
                    if "id" in tc_delta:
                        buf["id"] = tc_delta.get("id", "")
                    if "function" in tc_delta:
                        fn = tc_delta["function"]
                        if "name" in fn:
                            buf["function"]["name"] += fn["name"]
                        if "arguments" in fn:
                            buf["function"]["arguments"] += fn["arguments"]

        raw_tool_calls = [tool_call_buffers[i] for i in sorted(tool_call_buffers.keys())]

        # 诊断阶段检测
        diagnostic_stage = state.get("diagnostic_stage")
        if state.get("intent") == "fault_analysis":
            diagnostic_stage = _detect_diagnostic_stage(content, diagnostic_stage)

        # 记录推理步骤
        step_num = len(reasoning_steps) + 1
        if raw_tool_calls:
            tool_names = [tc.get("function", {}).get("name", "unknown") for tc in raw_tool_calls]
            # 获取上一轮工具执行结果作为 observation
            prev_results = state.get("execution_results", [])
            observation = None
            if prev_results:
                last = prev_results[-1]
                if last.get("result", {}).get("success"):
                    observation = f"工具执行成功: {json.dumps(last.get('result', {}).get('data', ''), ensure_ascii=False)[:200]}"
                else:
                    observation = f"工具执行失败: {last.get('error', last.get('result', {}).get('error', '未知'))}"
            reasoning_steps.append({
                "step": step_num,
                "thought": content or f"决定调用工具: {', '.join(tool_names)}",
                "action": f"调用 {', '.join(tool_names)}",
                "observation": observation,
            })
        else:
            reasoning_steps.append({
                "step": step_num,
                "thought": content[:300] if content else "分析完成",
                "action": None,
                "observation": None,
            })

        # 如果有工具调用 → 进入安全校验
        if raw_tool_calls:
            tool_calls: List[ToolCall] = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    tool_args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}

                tool_calls.append({
                    "id": tc.get("id", _generate_id()),
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "risk_level": "L3",
                    "status": "pending",
                    "result": None,
                    "error": None,
                })

            messages.append({
                "role": "assistant",
                "content": content or None,
                "tool_calls": raw_tool_calls,
            })

            return {
                **state,
                "current_stage": AgentStage.SAFETY_CHECK,
                "messages": messages,
                "reasoning_steps": reasoning_steps,
                "reasoning_output": content,
                "streaming_tokens": streaming_tokens,
                "diagnostic_stage": diagnostic_stage,
                "tool_calls": tool_calls,
                "error": None,
            }

        # 没有工具调用 → 最终回复，直接进入响应组装
        messages.append({"role": "assistant", "content": content})

        return {
            **state,
            "current_stage": AgentStage.RESPONSE_ASSEMBLY,
            "messages": messages,
            "reasoning_steps": reasoning_steps,
            "reasoning_output": content,
            "streaming_tokens": streaming_tokens,
            "diagnostic_stage": diagnostic_stage or "remediation",
            "final_response": content,
            "tool_calls": [],
            "error": None,
        }

    except Exception as e:
        logger.error(f"[推理决策] LLM调用失败: {e}", exc_info=True)
        retry_count = state.get("retry_count", 0)
        if retry_count < 2:
            return {
                **state,
                "current_stage": AgentStage.REASONING,
                "error": str(e),
                "retry_count": retry_count + 1,
                "streaming_tokens": streaming_tokens,
            }
        return {
            **state,
            "current_stage": AgentStage.FALLBACK,
            "error": str(e),
            "retry_count": retry_count + 1,
            "block_reason": f"LLM调用失败(已重试{retry_count}次): {str(e)[:100]}",
            "streaming_tokens": streaming_tokens,
        }


# ═══════════════════════════════════════════
# 节点6: 安全校验层 (核心实现)
# ═══════════════════════════════════════════

async def safety_check_node(state: AgentState) -> AgentState:
    """
    安全校验层 - 指令过滤 + 高危识别 + 权限校验

    对 reasoning_node 产出的每个 tool_call 进行5层分析:
      L1: 命令分组 → L2: 黑名单 → L3: 高危参数 → L4: 绕过检测 → L5: 路径保护
    """
    tool_calls = state.get("tool_calls", [])
    logger.info(f"[安全校验] 检查 {len(tool_calls)} 个工具调用...")

    any_blocked = False
    any_approval = False
    any_confirm = False
    highest_risk = RiskLevel.L1

    for tc in tool_calls:
        tool_name = tc["tool_name"]
        tool_args = tc["tool_args"]
        safety = _check_tool_safety(tool_name, tool_args)

        tc["risk_level"] = safety["risk_level"]

        if safety["blocked"]:
            tc["status"] = "blocked"
            tc["error"] = safety["block_message"]
            any_blocked = True
            logger.warning(f"[安全校验] 阻止: {tool_name} - {safety['block_message']}")
        elif safety["require_approval"]:
            tc["status"] = "pending_approval"
            any_approval = True
            logger.info(f"[安全校验] 需审批: {tool_name} [{safety['risk_level']}]")
        elif safety["require_confirm"]:
            tc["status"] = "pending_confirm"
            any_confirm = True
            logger.info(f"[安全校验] 需确认: {tool_name} [{safety['risk_level']}]")
        else:
            tc["status"] = "approved"  # L1 直接标记为可执行
            logger.info(f"[安全校验] 安全: {tool_name} [L1]")

        # 追踪最高风险级别
        risk_order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}
        if risk_order.get(safety["risk_level"], 0) > risk_order.get(highest_risk.value, 0):
            highest_risk = RiskLevel(safety["risk_level"])

    return {
        **state,
        "current_stage": AgentStage.TOOL_EXECUTION,
        "tool_calls": tool_calls,
        "require_approval": any_approval,
        "require_confirm": any_confirm,
        "blocked": any_blocked and not any_approval and not any_confirm,
        "safety_decision": {
            "allowed": not any_blocked,
            "require_approval": any_approval,
            "require_confirm": any_confirm,
            "highest_risk": highest_risk.value,
        },
    }


# ═══════════════════════════════════════════
# 节点6.5: 确认请求节点 ④.5
# ═══════════════════════════════════════════

async def confirmation_node(state: AgentState) -> AgentState:
    """
    确认请求节点 - 对标架构图 ④.5

    对高风险但可执行的操作构造"否决式确认"请求:
    - L3/L4: 生成审批请求
    - L2: 生成确认请求
    - 构造结构化确认卡片，暂停等待用户操作
    """
    tool_calls = state.get("tool_calls", [])
    logger.info(f"[确认请求] 处理 {len(tool_calls)} 个待确认项...")

    # 分类待确认项
    approval_items = []
    confirm_items = []

    for tc in tool_calls:
        if tc.get("status") == "pending_approval":
            approval_items.append({
                "id": tc["id"],
                "tool_name": tc["tool_name"],
                "tool_args": tc["tool_args"],
                "risk_level": tc.get("risk_level", "L3"),
                "reason": tc.get("error") or f"高风险操作 [{tc.get('risk_level', 'L3')}]",
            })
        elif tc.get("status") == "pending_confirm":
            confirm_items.append({
                "id": tc["id"],
                "tool_name": tc["tool_name"],
                "tool_args": tc["tool_args"],
                "risk_level": tc.get("risk_level", "L2"),
                "reason": f"需要确认 [{tc.get('risk_level', 'L2')}]",
            })

    # 构建确认信息
    needs_approval = len(approval_items) > 0
    needs_confirm = len(confirm_items) > 0

    return {
        **state,
        "current_stage": AgentStage.RESPONSE_ASSEMBLY,
        "require_approval": needs_approval,
        "require_confirm": needs_confirm,
        "safety_decision": {
            **(state.get("safety_decision") or {}),
            "needs_confirmation": True,
            "confirm_type": "approval" if needs_approval else "confirm",
            "approval_items": approval_items,
            "confirm_items": confirm_items,
        },
    }


# ═══════════════════════════════════════════
# 节点7: 工具调用执行层 (核心实现)
# ═══════════════════════════════════════════

async def tool_execution_node(state: AgentState) -> AgentState:
    """
    工具调用执行层

    处理逻辑:
    - L1 安全工具 → 直接执行
    - 需确认/审批 → 创建审批记录，暂停等待用户操作
    - 已阻止 → 记录错误
    """
    tool_calls = state.get("tool_calls", [])
    messages = state.get("messages", [])
    execution_results = list(state.get("execution_results", []))

    logger.info(f"[工具执行] 执行 {len(tool_calls)} 个工具...")

    any_executed = False
    any_pending_approval = False
    any_pending_confirm = False
    cmd_log = list(state.get("execution_command_log") or [])

    for tc in tool_calls:
        status = tc.get("status", "pending")

        if status == "blocked":
            execution_results.append({
                "tool_name": tc["tool_name"],
                "status": "blocked",
                "error": tc.get("error", "被安全策略阻止"),
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps({"success": False, "error": tc.get("error", "被阻止")}, ensure_ascii=False),
            })
            continue

        if status == "pending_approval":
            any_pending_approval = True
            continue

        if status == "pending_confirm":
            any_pending_confirm = True
            continue

        if status == "approved":
            # L1 安全操作 → 直接执行
            try:
                result = _execute_tool(tc["tool_name"], tc["tool_args"])
                tc["status"] = "executed"
                tc["result"] = result
                execution_results.append({
                    "tool_name": tc["tool_name"],
                    "tool_args": tc["tool_args"],
                    "status": "completed" if result.get("success") else "failed",
                    "result": result,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })
                any_executed = True
                from .nodes_supervision import append_execution_log
                cmd_log = append_execution_log(
                    {**state, "execution_command_log": cmd_log},
                    tc["tool_name"], tc["tool_args"], result,
                )
                logger.info(f"[工具执行] {tc['tool_name']} → {'成功' if result.get('success') else '失败'}")
            except Exception as e:
                tc["status"] = "executed"
                tc["error"] = str(e)
                execution_results.append({
                    "tool_name": tc["tool_name"],
                    "status": "failed",
                    "error": str(e),
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps({"success": False, "error": str(e)}, ensure_ascii=False),
                })
                logger.error(f"[工具执行] {tc['tool_name']} 异常: {e}")

    # 决定下一步
    round_count = state.get("round_count", 0) + 1

    base_out = {
        "messages": messages,
        "tool_calls": tool_calls,
        "execution_results": execution_results,
        "execution_command_log": cmd_log,
        "round_count": round_count,
    }

    if any_pending_approval or any_pending_confirm:
        return {
            **state,
            **base_out,
            "current_stage": AgentStage.RESPONSE_ASSEMBLY,
            "require_approval": any_pending_approval,
            "require_confirm": any_pending_confirm,
        }

    if any_executed:
        return {
            **state,
            **base_out,
            "current_stage": AgentStage.REASONING,
        }

    return {
        **state,
        **base_out,
        "current_stage": AgentStage.RESPONSE_ASSEMBLY,
    }


# ═══════════════════════════════════════════
# 节点8: 响应组装层
# ═══════════════════════════════════════════

async def response_assembly_node(state: AgentState) -> AgentState:
    """响应组装: 结果 + 推理链 + 状态卡片 + 风险色标"""
    logger.info("[响应组装] 组装最终响应...")

    # 风险色标映射
    risk_color_map = {
        RiskLevel.L1: "green",
        RiskLevel.L2: "yellow",
        RiskLevel.L3: "orange",
        RiskLevel.L4: "red",
        RiskLevel.L5: "purple",
    }

    # 确定最高风险级别
    tool_calls = state.get("tool_calls", [])
    highest_risk = RiskLevel.L1
    risk_order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}
    for tc in tool_calls:
        rl = tc.get("risk_level", "L1")
        if risk_order.get(rl, 0) > risk_order.get(highest_risk.value, 0):
            highest_risk = RiskLevel(rl)

    # 构建状态卡片
    state_cards = []

    # 意图卡片
    intent = state.get("intent", "unknown")
    intent_labels = {
        "general_qa": "普通问答", "knowledge_qa": "知识查询",
        "ops_query": "运维查询", "fault_analysis": "故障分析",
        "high_risk": "高风险操作", "prompt_injection": "注入拦截",
    }
    state_cards.append({
        "title": "意图分析",
        "content": intent_labels.get(intent, intent),
        "status": "success" if intent != "prompt_injection" else "error",
    })

    # 安全检查卡片
    safety = state.get("safety_decision", {})
    if safety:
        if safety.get("require_approval"):
            state_cards.append({
                "title": "安全检查",
                "content": f"需审批 [{safety.get('highest_risk', 'L3')}]",
                "status": "warning",
            })
        elif safety.get("require_confirm"):
            state_cards.append({
                "title": "安全检查",
                "content": f"需确认 [{safety.get('highest_risk', 'L2')}]",
                "status": "warning",
            })
        elif state.get("blocked"):
            state_cards.append({
                "title": "安全检查",
                "content": "已拦截",
                "status": "error",
            })
        else:
            state_cards.append({
                "title": "安全检查",
                "content": "通过",
                "status": "success",
            })

    # 工具执行卡片
    for tc in tool_calls:
        status = tc.get("status", "pending")
        status_map = {
            "executed": "success",
            "completed": "success",
            "blocked": "error",
            "pending_approval": "warning",
            "pending_confirm": "warning",
            "failed": "error",
        }
        state_cards.append({
            "title": f"工具: {tc['tool_name']}",
            "content": f"[{tc.get('risk_level', 'L1')}] {status}",
            "status": status_map.get(status, "info"),
        })

    # 诊断阶段卡片
    diagnostic_stage = state.get("diagnostic_stage")
    if diagnostic_stage:
        stage_labels = {
            "info_gathering": ("信息收集", "info"),
            "hypothesis": ("假设生成", "info"),
            "verification": ("验证测试", "warning"),
            "root_cause": ("根因确认", "warning"),
            "remediation": ("修复建议", "success"),
        }
        label, status = stage_labels.get(diagnostic_stage, (diagnostic_stage, "info"))
        state_cards.append({
            "title": "诊断阶段",
            "content": label,
            "status": status,
        })

    # RAG 卡片
    if state.get("rag_context"):
        state_cards.append({
            "title": "知识库",
            "content": f"已检索 {len(state.get('rag_sources', []))} 条相关内容",
            "status": "info",
        })

    # 最终回复
    final_response = state.get("final_response") or state.get("reasoning_output") or "处理完成"

    # 如果需要审批/确认，生成特殊回复
    if state.get("require_approval"):
        pending_tools = [tc for tc in tool_calls if tc.get("status") == "pending_approval"]
        tool_list = ", ".join([f"{t['tool_name']}({t.get('risk_level', 'L3')})" for t in pending_tools])
        final_response = (
            f"⚠️ **需要审批**\n\n"
            f"以下操作需要审批后方可执行：\n\n"
            f"{tool_list}\n\n"
            f"请在审批管理页面进行审批操作。"
        )

    if state.get("require_confirm") and not state.get("require_approval"):
        pending_tools = [tc for tc in tool_calls if tc.get("status") == "pending_confirm"]
        tool_list = ", ".join([f"{t['tool_name']}({t.get('risk_level', 'L2')})" for t in pending_tools])
        final_response = (
            f"🟡 **需要确认**\n\n"
            f"以下操作需要您确认后执行：\n\n"
            f"{tool_list}\n\n"
            f"请在下方确认或取消。"
        )

    ops_report = None
    if state.get("route_path") == "react_b" and tool_calls:
        from app.services.human_supervision import build_structured_ops_report
        tool_records = [
            {
                "toolName": tc["tool_name"],
                "status": tc.get("status"),
                "riskLevel": tc.get("risk_level"),
                "result": tc.get("result"),
                "displaySummary": (tc.get("result") or {}).get("display_summary", ""),
            }
            for tc in tool_calls
        ]
        ops_report = build_structured_ops_report(
            state.get("user_input", ""),
            state.get("trace_id", ""),
            tool_records,
            state.get("intent", ""),
        )
        if ops_report and "<!--KYLIN_REPORT-->" not in final_response:
            final_response = final_response + "\n\n<!--KYLIN_REPORT-->\n\n" + ops_report

    final_status = state.get("final_status", "processing")
    if state.get("require_approval"):
        final_status = "awaiting_approval"
    elif state.get("require_confirm"):
        final_status = "awaiting_confirm"
    elif state.get("awaiting_user_action"):
        final_status = "awaiting_plan_confirm"

    return {
        **state,
        "current_stage": AgentStage.COMPLETED,
        "final_response": final_response,
        "ops_report": ops_report,
        "final_status": final_status,
        "risk_color": risk_color_map.get(highest_risk, "blue"),
        "state_cards": state_cards,
        "reasoning_chain_visible": len(state.get("reasoning_steps", [])) > 0,
    }


# ═══════════════════════════════════════════
# 降级节点
# ═══════════════════════════════════════════

async def fallback_node(state: AgentState) -> AgentState:
    """降级处理"""
    logger.warning("[降级处理] 进入降级流程...")

    error_msg = state.get("block_reason") or state.get("error") or "处理失败，请稍后重试"

    return {
        **state,
        "current_stage": AgentStage.COMPLETED,
        "final_response": f"⚠️ {error_msg}",
        "risk_color": "red",
        "state_cards": [
            {"title": "处理状态", "content": "拦截", "status": "error"},
        ],
        "reasoning_chain_visible": False,
    }
