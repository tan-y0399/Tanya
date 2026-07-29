"""多模态多 Agent 深度思考链路服务。"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import quote

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.trace import generate_trace_id
from app.services.human_supervision import validate_user_input
from app.services.image_store import save_message_attachments
from app.services.multimodal_rag import search_multimodal_knowledge
from app.services.prompt_guard import security_gate

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> Dict[str, Any]:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def _step(step_id: str, title: str, detail: str = "", status: str = "running") -> Dict[str, Any]:
    return _sse("exploring_step", {
        "id": step_id,
        "title": title,
        "detail": detail,
        "status": status,
    })


def _answer_media(
    media_id: str,
    kind: str,
    status: str,
    title: str,
    **extra: Any,
) -> Dict[str, Any]:
    return _sse("answer_media", {
        "id": media_id,
        "kind": kind,
        "status": status,
        "title": title,
        **{key: value for key, value in extra.items() if value is not None},
    })


def _consume_intent_choice(content: str) -> tuple[str, Optional[str]]:
    """Extract an explicit UI intent choice and return cleaned user content."""
    text = content or ""
    lowered = text.lower()
    markers = [
        ("[intent:professional_answer]", "professional_answer"),
        ("[intent:plan_execute]", "plan_execute"),
        ("意图选择：生成专业图文方案", "professional_answer"),
        ("意图选择:生成专业图文方案", "professional_answer"),
        ("意图选择：进入 plan-execute 执行", "plan_execute"),
        ("意图选择:进入 plan-execute 执行", "plan_execute"),
    ]
    choice: Optional[str] = None
    for marker, value in markers:
        if marker.lower() in lowered:
            choice = value
            text = text.replace(marker, "").replace(marker.upper(), "")
            text = text.replace("【" + marker + "】", "").replace("[" + marker + "]", "")
    for prefix in ("原问题：", "原问题:", "用户原问题：", "用户原问题:"):
        if prefix in text:
            text = text.split(prefix, 1)[1]
            break
    return text.strip() or (content or ""), choice


def _has_ops_problem(content: str) -> bool:
    text = (content or "").lower()
    markers = (
        "故障", "异常", "报错", "失败", "无法", "不能", "开不了机", "无法开机", "启动失败",
        "无法启动", "登录循环", "黑屏", "闪一下", "显示不全", "图形界面", "3d加速",
        "vmware", "boot", "failed", "error", "虚拟机", "kylin", "麒麟",
    )
    return any(m in text for m in markers)


def _asks_for_execution(content: str) -> bool:
    text = (content or "").lower()
    markers = (
        "执行", "实施", "处理一下", "帮我处理", "帮我解决", "帮我修复", "直接修复",
        "开始排查", "自动排查", "进入排查", "实际解决", "连接服务器", "plan-execute",
        "plan execute", "按方案执行", "继续执行", "execute", "run the plan", "fix it",
        "repair it", "troubleshoot it", "start troubleshooting",
    )
    return any(m in text for m in markers)


def _asks_for_professional_answer(content: str) -> bool:
    """Detect an explicit request for a formatted answer instead of execution."""
    text = (content or "").lower()
    markers = (
        "图文结合", "图文回答", "图文方案", "专业回答", "专业方案", "原因分析",
        "添加表格", "使用表格", "表格方式", "解决流程图", "处理流程图", "流程图",
        "给出解决步骤", "给出处理步骤", "回答通俗易懂", "通俗易懂地回答",
        "illustrated answer", "professional answer", "include a table", "flowchart",
    )
    return any(m in text for m in markers)


def _asks_for_answer_only(content: str) -> bool:
    text = (content or "").lower()
    markers = (
        "只给", "只需要", "仅给", "仅需", "不要执行", "不执行", "无需执行", "先不要执行",
        "不要操作", "不连接服务器", "无需连接服务器", "只分析", "仅分析", "知识讲解",
        "文档方案", "专业文档", "answer only", "do not execute", "don't execute",
        "no execution", "no server operation", "documentation only",
    )
    return any(m in text for m in markers) or (
        _asks_for_professional_answer(content) and not _asks_for_execution(content)
    )


def _needs_intent_clarification(content: str, route: Dict[str, Any]) -> bool:
    if route.get("link") != "deep_plan_execute":
        return False
    if not _has_ops_problem(content):
        return False
    if _asks_for_execution(content) or _asks_for_answer_only(content):
        return False
    solution_markers = (
        "方案", "解决方案", "怎么解决", "如何解决", "如何处理", "图文", "图文结合",
        "solution", "how to fix", "how to resolve", "how to troubleshoot", "guide",
    )
    return any(m in (content or "").lower() for m in solution_markers)


def _intent_clarification_payload(content: str, trace_id: str) -> Dict[str, Any]:
    question = (
        "我识别到这是一个可进入执行链路的运维故障问题，但你当前更像是在请求“图文结合解决方案”。"
        "请先确认目标，避免把知识解答误执行到服务器上。"
    )
    return {
        "traceId": trace_id,
        "question": question,
        "originalQuestion": content,
        "options": [
            {
                "id": "professional_answer",
                "title": "生成专业图文方案",
                "description": "只做图文结合分析、知识库/图片检索和标准化解决方案，不执行服务器操作。",
                "prompt": "意图选择：生成专业图文方案。原问题：",
            },
            {
                "id": "plan_execute",
                "title": "进入 Plan-Execute 执行",
                "description": "生成可执行排查计划，确认后按安全分级、审批和回滚链路逐步处理问题。",
                "prompt": "意图选择：进入 Plan-Execute 执行。原问题：",
            },
        ],
    }


async def _vision_expert(content: str, attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """优先调用配置的视觉模型；未配置时返回可审计的图片摘要。"""
    results: List[Dict[str, Any]] = []
    if not attachments:
        return results

    api_key = getattr(settings, "vision_llm_api_key", "") or getattr(settings, "llm_api_key", "")
    api_base = getattr(settings, "vision_llm_api_base", "") or getattr(settings, "llm_api_base", "")
    model = getattr(settings, "vision_llm_model", "")
    can_call_vision = bool(model and api_key and api_base)

    for item in attachments:
        summary = (
            f"用户上传图片《{item.get('name', 'image')}》，类型 {item.get('contentType', '')}，"
            f"大小 {round((item.get('size') or 0) / 1024, 1)}KB。"
        )
        detail = ""
        if can_call_vision and item.get("url"):
            # 后端本地 URL 对外部模型不可访问，因此仅在前端传 dataUrl 时可真正视觉理解。
            pass
        if can_call_vision and item.get("dataUrl"):
            try:
                payload = {
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": (
                                "你是麒麟服务器运维截图分析专家。请识别图片中的错误、命令、界面状态、"
                                "可能的故障点，并给出可用于知识库检索的关键词。用户问题："
                                + (content or "请分析这张图片")
                            )},
                            {"type": "image_url", "image_url": {"url": item["dataUrl"]}},
                        ],
                    }],
                    "temperature": 0.1,
                    "max_tokens": 800,
                }
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.post(
                        f"{api_base.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    detail = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if detail:
                        summary = detail
            except Exception as exc:
                logger.warning("vision expert fallback: %s", exc)
        results.append({
            "attachmentId": item.get("id"),
            "name": item.get("name"),
            "url": item.get("url"),
            "summary": summary,
            "detail": detail,
        })
    return results


def _route_deep_link(content: str, attachments: List[Dict[str, Any]], rag_result: Dict[str, Any]) -> Dict[str, Any]:
    text = (content or "").lower()
    ops_markers = (
        "故障", "异常", "报错", "失败", "无法", "排查", "修复", "执行", "清理", "重启", "关闭", "启动",
        "登录循环", "黑屏", "闪一下", "显示不全", "图形界面", "3d加速",
        "fail", "failed", "failure", "cannot", "can't", "unable", "error", "start", "boot",
        "vm", "vmware", "virtual machine", "kylin",
    )
    if any(m in text for m in ops_markers):
        link = "deep_plan_execute"
        label = "深度思考 · 多模态 Plan-Execute"
        desc = "图文理解 + 知识检索 + 专家方案，必要时再进入安全执行"
    elif attachments:
        link = "deep_multimodal_qa"
        label = "深度思考 · 图文知识问答"
        desc = "结合图片理解、知识库与候选配图回答"
    else:
        link = "deep_knowledge_qa"
        label = "深度思考 · 多专家知识问答"
        desc = "多专家协同检索、校验与规范化回答"
    if not rag_result.get("text_results"):
        desc += "；知识库低命中，将标注知识缺口"
    return {"link": link, "linkLabel": label, "linkDescription": desc}


def _build_boot_failure_plan(content: str, rag_result: Dict[str, Any], vision_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    sources = [r.get("title") for r in rag_result.get("text_results", [])[:3]]
    vision_note = "；".join(v.get("summary", "")[:120] for v in vision_results[:2])
    return {
        "plan_type": "multimodal_plan_execute",
        "title": "麒麟虚拟机启动失败排查方案",
        "phenomenon": content[:300],
        "query_goal": "确认宿主机/虚拟化服务/磁盘空间/虚拟机状态/相关日志，定位虚拟机无法开机或启动失败原因。",
        "possible_causes": [
            "宿主机磁盘空间不足导致虚拟磁盘或快照写入失败",
            "libvirt/虚拟化服务异常导致虚拟机启动失败",
            "虚拟机定义、镜像文件或存储池异常",
            "来宾系统文件系统损坏，需要进入救援模式人工修复",
        ],
        "steps": [
            {
                "order": 1,
                "agent": "Tool Executor",
                "action": "检查宿主机磁盘空间，确认是否因空间不足导致虚拟机无法启动",
                "tool_hint": "get_disk_usage",
                "risk": "L1",
                "core": True,
                "expected": "各挂载点容量、可用空间、使用率",
            },
            {
                "order": 2,
                "agent": "Tool Executor",
                "action": "检查宿主机 CPU 负载，确认是否存在资源耗尽",
                "tool_hint": "get_cpu_info",
                "risk": "L1",
                "core": True,
                "expected": "CPU 使用率、核心数、系统负载",
            },
            {
                "order": 3,
                "agent": "Tool Executor",
                "action": "检查宿主机内存与 Swap 使用情况",
                "tool_hint": "get_memory_info",
                "risk": "L1",
                "core": True,
                "expected": "内存总量、可用量、使用率、Swap 状态",
            },
            {
                "order": 4,
                "agent": "Tool Executor",
                "action": "检查 libvirt 虚拟化服务状态",
                "tool_hint": "get_service_status:libvirtd",
                "risk": "L1",
                "core": True,
                "expected": "libvirtd 是否 active、主进程 PID、最近状态",
            },
            {
                "order": 5,
                "agent": "Tool Executor",
                "action": "列出虚拟机清单与运行状态",
                "tool_hint": "execute_command: virsh list --all",
                "risk": "L1",
                "core": True,
                "expected": "虚拟机名称、ID、运行/关闭/异常状态",
            },
            {
                "order": 6,
                "agent": "Tool Executor",
                "action": "查看 libvirt 最近错误日志",
                "tool_hint": "execute_command: journalctl -u libvirtd -n 80 --no-pager",
                "risk": "L1",
                "core": True,
                "expected": "启动失败、镜像缺失、权限不足、存储池异常等错误线索",
            },
            {
                "order": 7,
                "agent": "Tool Executor",
                "action": "检查块设备和文件系统标识，辅助判断存储/挂载异常",
                "tool_hint": "execute_command: lsblk -f",
                "risk": "L1",
                "expected": "磁盘、分区、文件系统、挂载点信息",
            },
        ],
        "manual_steps": [
            "若虚拟机卡在 Logo 或引导界面，需要通过控制台截图/报错继续定位；此步骤不能由 SSH 工具自动完成。",
            "若确认来宾系统文件系统损坏，应在救援模式下执行 fsck，执行前必须确认磁盘镜像已备份。",
            "若需要启动/重启 libvirtd 或修改虚拟机配置，应进入 L2-L4 确认/审批流程。",
        ],
        "planned_commands": [
            "df -h",
            "systemctl status libvirtd",
            "virsh list --all",
            "journalctl -u libvirtd -n 80 --no-pager",
            "lsblk -f",
        ],
        "risk_note": "当前自动执行步骤均为 L1 只读排查；修复、重启、fsck、删除快照等动作必须另行确认或审批。",
        "requires_confirm": True,
        "rag_sources": [{"title": s} for s in sources if s],
        "rag_reference": (rag_result.get("context") or "")[:400] or None,
        "multimodal_context": {
            "vision_summary": vision_note,
            "image_count": len(vision_results),
            "image_candidates": rag_result.get("image_results", [])[:3],
        },
    }


async def _build_plan(
    content: str,
    rag_result: Dict[str, Any],
    vision_results: List[Dict[str, Any]],
    server_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    # Keep planning eligibility aligned with Supervisor routing. Previously a query could
    # route to deep ops because it mentioned a virtual machine, then fail to build the
    # visual plan because this function used a narrower keyword list.
    if not _has_ops_problem(content):
        return None

    t = (content or "").lower()
    boot_markers = (
        "开机", "启动失败", "无法启动", "无法开机", "boot", "logo", "虚拟机",
        "fails to start", "failed to start", "startup failure", "start failure", "cannot start",
        "unable to start", "virtual machine", "vm",
    )
    if any(m in t for m in boot_markers):
        return _build_boot_failure_plan(content, rag_result, vision_results)

    try:
        from app.services.human_supervision import build_diagnostic_plan, enrich_diagnostic_plan_with_env
        plan = await build_diagnostic_plan(content, "fault_analysis", rag_result.get("context") or "")
        plan = await enrich_diagnostic_plan_with_env(
            plan,
            content,
            rag_result.get("context") or "",
            sensing_mode="fault_diagnosis",
            server_id=server_id,
        )
    except Exception:
        plan = {
            "plan_type": "multimodal_plan_execute",
            "title": "多模态运维排查方案",
            "phenomenon": content[:300],
            "possible_causes": ["资源不足", "服务异常", "配置或日志中存在错误线索"],
            "steps": [
                {"order": 1, "action": "查看 CPU 与负载", "tool_hint": "get_cpu_info", "risk": "L1", "core": True},
                {"order": 2, "action": "查看内存状态", "tool_hint": "get_memory_info", "risk": "L1", "core": True},
                {"order": 3, "action": "查看磁盘空间", "tool_hint": "get_disk_usage", "risk": "L1", "core": True},
                {"order": 4, "action": "查看关键日志线索", "tool_hint": "execute_command: journalctl -p err -n 80 --no-pager", "risk": "L1"},
            ],
            "risk_note": "自动步骤仅做 L1 只读排查；任何修复动作需再次确认。",
            "requires_confirm": True,
        }

    executable_steps = []
    for step in plan.get("steps") or []:
        hint = (step.get("tool_hint") or "").strip()
        if not hint or hint in ("env_precheck", "按意图选择工具", "summary") or step.get("virtual"):
            continue
        executable_steps.append({**step, "order": len(executable_steps) + 1})
    if not executable_steps:
        executable_steps = [
            {"order": 1, "action": "查看 CPU 与负载", "tool_hint": "get_cpu_info", "risk": "L1", "core": True},
            {"order": 2, "action": "查看内存状态", "tool_hint": "get_memory_info", "risk": "L1", "core": True},
            {"order": 3, "action": "查看磁盘空间", "tool_hint": "get_disk_usage", "risk": "L1", "core": True},
        ]
    plan["steps"] = executable_steps
    plan["plan_type"] = plan.get("plan_type") or "multimodal_plan_execute"
    plan["requires_confirm"] = True
    plan["multimodal_context"] = {
        "vision_summary": "；".join(v.get("summary", "")[:120] for v in vision_results[:2]),
        "image_count": len(vision_results),
        "image_candidates": rag_result.get("image_results", [])[:3],
    }
    return plan


def _table_cell(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text.replace("|", "\\|")[:limit] or "-"


def _has_markdown_table(text: str) -> bool:
    return bool(re.search(r"(?m)^\s*\|[^\n]+\|\s*$\n\s*\|\s*:?-{3,}", text or ""))


def _plan_table_markdown(plan: Optional[Dict[str, Any]]) -> str:
    steps = (plan or {}).get("steps") or []
    if not steps:
        return (
            "| 阶段 | 需要确认的内容 | 输出 |\n"
            "|---|---|---|\n"
            "| 1. 识别现象 | 截图中的报错、界面状态和发生时机 | 明确故障边界 |\n"
            "| 2. 核对证据 | 系统状态、日志与配置 | 排除低相关猜测 |\n"
            "| 3. 处理验证 | 从低风险步骤开始并逐项验证 | 确认是否恢复 |"
        )
    lines = [
        "| 步骤 | 排查或处理内容 | 预期结果 | 风险 |",
        "|---:|---|---|:---:|",
    ]
    for idx, step in enumerate(steps[:8], 1):
        lines.append(
            f"| {step.get('order') or idx} | {_table_cell(step.get('action'))} | "
            f"{_table_cell(step.get('expected') or '获得可用于下一步判断的证据')} | "
            f"{_table_cell(step.get('risk') or 'L1', 12)} |"
        )
    return "\n".join(lines)


def _ensure_answer_table(response: str, plan: Optional[Dict[str, Any]]) -> str:
    text = (response or "").strip()
    if _has_markdown_table(text):
        return text
    return text + "\n\n## 标准化排查表\n\n" + _plan_table_markdown(plan)


async def _compose_with_llm_stream(
    content: str,
    vision_results: List[Dict[str, Any]],
    rag_result: Dict[str, Any],
    plan: Optional[Dict[str, Any]],
    web_result: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    vision_text = "\n".join(f"- {v.get('summary', '')}" for v in vision_results) or "无图片输入"
    sources = rag_result.get("text_results", [])
    images = rag_result.get("image_results", [])
    source_text = "\n".join(
        f"- {s.get('title')}：{_table_cell(s.get('snippet'), 320)}"
        for s in sources[:4]
    ) or "知识库未命中高相关文本"
    image_text = "\n".join(f"- {i.get('title')} ({i.get('source')})" for i in images[:4]) or "知识库未命中高相关图片"
    plan_text = json.dumps(plan, ensure_ascii=False, indent=2) if plan else "无需生成执行方案"
    if web_result:
        web_text = json.dumps({
            "status": web_result.get("status"),
            "provider": web_result.get("provider"),
            "items": [
                {
                    "title": item.get("title"),
                    "snippet": item.get("snippet"),
                    "sourceUrl": item.get("url"),
                    "score": item.get("score"),
                }
                for item in (web_result.get("items") or [])[:6]
            ],
        }, ensure_ascii=False, indent=2)
    else:
        web_text = "未触发外部资料检索"

    system = (
        "你是 KylinOps 多模态多 Agent 总结专家。请输出中文、结构化、专业、谨慎的运维回答。"
        "必须区分事实依据、图片观察、知识库依据和下一步建议。"
        "回答必须按：问题理解、综合判断、依据与相关性、图文说明、处理建议/步骤、风险提示、参考来源 的顺序组织。"
        "只要是运维故障分析，正文必须至少包含一张 Markdown 表格，用于对比可能原因或列出排查步骤。"
        "表格中的结论必须来自当前输入、图片观察或提供的检索资料，不得编造已执行结果。"
        "图片会由系统审核、缓存并插入对应位置；正文不要自行输出图片 Markdown、图片 URL 或占位图。"
        "不要把普通网页地址当作图片地址，也不要输出占位图或省略号 URL。"
        "不要输出 Mermaid、graph TD、flowchart、drawio XML 或任何流程图源码；流程图会由系统另行生成图片并插入。"
        "若没有实时执行工具，禁止声称已经执行。"
    )
    user = f"""
用户问题：
{content or "请结合图片进行分析"}

Vision Expert 观察：
{vision_text}

Knowledge Expert 检索：
{source_text}

候选图片：
{image_text}

Ops Diagnosis Planner 方案：
{plan_text}

Web Research 结果：
{web_text}

请给出：1. 综合判断 2. 依据 3. 处理建议/步骤 4. 风险提示 5. 可用配图说明。
"""
    try:
        from app.services.chat_service import call_deepseek
        emitted = False
        async for chunk in call_deepseek(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            stream=True,
            use_tools=False,
            extra_tools=[],
        ):
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            if delta.get("content"):
                emitted = True
                yield delta["content"]
        if emitted:
            return
    except Exception as exc:
        logger.warning("multimodal composer llm fallback: %s", exc)

    likely_causes = (plan or {}).get("possible_causes") or []
    judgment = (
        "当前已根据用户描述、原始截图和可用资料形成排查方向；尚未执行服务器命令。"
        if vision_results
        else "当前未获得可用的图片识别结论，只能依据文字和检索资料给出保守排查方向；尚未执行服务器命令。"
    )
    parts = [
        "## 问题理解",
        _table_cell(content, 420),
        "## 综合判断",
        judgment + ((" 优先核查：" + "；".join(_table_cell(v, 100) for v in likely_causes[:3]) + "。") if likely_causes else ""),
        "## 图片观察",
        vision_text,
        "## 依据与相关性",
        source_text,
        "## 标准化排查表",
        _plan_table_markdown(plan),
    ]
    if plan:
        parts.extend([
            "## 处理建议/步骤",
            "\n".join(
                f"{s.get('order', i)}. {s.get('action', '继续排查')}（{s.get('agent', 'Ops Expert')}，风险 {s.get('risk', 'L1')}）"
                for i, s in enumerate(plan.get("steps") or [], 1)
            ),
        ])
    parts.extend([
        "## 风险提示",
        "涉及修改、清理、重启、删除等动作时，必须先走确认/审批和回滚保护。外部检索不可用时，不应把未经验证的猜测当作事实。",
        "## 参考来源",
        "以上依据来自用户输入、用户截图及当前通过相关性重排的知识资料；无法访问的外部来源未作为确定性依据。",
    ])
    yield "\n\n".join(parts)


async def _compose_with_llm(
    content: str,
    vision_results: List[Dict[str, Any]],
    rag_result: Dict[str, Any],
    plan: Optional[Dict[str, Any]],
    web_result: Optional[Dict[str, Any]] = None,
) -> str:
    chunks: List[str] = []
    async for chunk in _compose_with_llm_stream(content, vision_results, rag_result, plan, web_result):
        chunks.append(chunk)
    return "".join(chunks)


def _images_to_step_markdown(images: List[Dict[str, Any]], title: str = "图文辅助说明") -> str:
    if not images:
        return ""
    lines = [f"## {title}"]
    for idx, img in enumerate(images[:3], 1):
        step_hint = img.get("step") or img.get("correspondingStep") or f"建议步骤 {idx}"
        caption = img.get("description") or img.get("snippet") or img.get("source") or "用于辅助理解该步骤的参考图"
        lines.append(f"### {step_hint}：{img.get('title', '参考图片')}")
        if img.get("url"):
            safe_url = _safe_markdown_url(str(img["url"]))
            lines.append(f"![{img.get('title', '参考图片')}]({safe_url})")
            lines.append(f"> {caption}")
        elif img.get("localPath"):
            lines.append(f"- 本地候选图片：`{img.get('localPath')}`。{caption}")
    return "\n\n".join(lines)


def _vision_images(vision_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    images: List[Dict[str, Any]] = []
    for idx, item in enumerate(vision_results or [], 1):
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith(("/api/", "http://", "https://", "data:image/")):
            continue
        images.append({
            "title": item.get("name") or f"用户截图 {idx}",
            "description": "用户提供的原始问题截图；正文中的现象判断应以该图的视觉识别结果为准。",
            "url": url,
            "source": "user_upload",
            "step": "问题现象",
            "score": 1.0,
        })
    return images


def _prepend_user_visuals(response: str, vision_results: List[Dict[str, Any]]) -> str:
    user_image_md = _images_to_step_markdown(_vision_images(vision_results), "用户提供的问题截图")
    if not user_image_md:
        return response
    return user_image_md + "\n\n" + (response or "").strip()


def _safe_markdown_url(url: str) -> str:
    if not url:
        return url
    if url.startswith(("/api/", "data:image/")):
        return url
    try:
        return quote(url, safe=":/?&=#%._~+-")
    except Exception:
        return re.sub(r"\s+", "%20", url)


def _strip_diagram_source_blocks(text: str) -> str:
    """Remove raw Mermaid/source diagram blocks; rendered SVG is appended separately."""
    if not text:
        return text
    text = re.sub(r"```(?:mermaid)?\s*[\s\S]*?(?:graph|flowchart)\s+(?:TD|LR|BT|RL)[\s\S]*?(?:```|$)", "", text, flags=re.I)
    text = re.sub(
        r"(?:^|\n)(?:#{2,4}\s*)?(?:解决流程图|处理流程图|流程图)\s*\n+\s*(?:graph|flowchart)\s+(?:TD|LR|BT|RL)[\s\S]*?(?=\n#{2,4}\s|\n(?:详细步骤|处理建议|总结|风险提示|参考来源)\b|$)",
        "\n",
        text,
        flags=re.I,
    )
    text = re.sub(r"(?:^|\n)\s*(?:graph|flowchart)\s+(?:TD|LR|BT|RL)[\s\S]*?(?=\n#{2,4}\s|\n(?:详细步骤|处理建议|总结|风险提示|参考来源)\b|$)", "\n", text, flags=re.I)
    text = re.sub(
        r"(?:^|\n)(?: {4}|\t)(?:graph|flowchart)\s+(?:TD|LR|BT|RL)[\s\S]*?(?=\n\S|\n{2,}|$)",
        "\n",
        text,
        flags=re.I,
    )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_unmanaged_markdown_images(text: str) -> str:
    """Only system-reviewed and locally materialized images may enter an answer."""
    if not text:
        return text
    cleaned = re.sub(r"!\[[^\]\n]*\]\([^)\n]+\)", "", text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


async def _web_research(query: str, need_image: bool) -> Dict[str, Any]:
    """可配置外部资料检索。默认不联网，避免无授权外部依赖。"""
    from app.services.external_research import search_external_knowledge
    return await search_external_knowledge(query, need_image=need_image)


def _external_images_to_rag(images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i in images or []:
        url = i.get("imageUrl") or i.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://", "data:image/")):
            continue
        out.append({
            "title": i.get("title") or "外部参考图片",
            "description": i.get("snippet") or i.get("description") or i.get("source"),
            "url": url,
            "score": i.get("score", 0),
            "source": i.get("source", "external"),
        })
    return out


async def process_multimodal_message(
    db: AsyncSession,
    session_id: str,
    content: str,
    user_id: str,
    *,
    user_role: str = "user",
    server_id: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    intent_choice: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    trace_id = generate_trace_id()
    assistant_msg_id = trace_id
    incoming_attachments = attachments or []
    text = (content or "").strip() or ("请分析我上传的图片" if incoming_attachments else "")
    text, marker_intent = _consume_intent_choice(text)
    forced_intent = intent_choice if intent_choice in ("professional_answer", "plan_execute") else marker_intent

    yield _sse("message_start", {"messageId": assistant_msg_id, "traceId": trace_id, "thinkingMode": "deep"})

    pre = validate_user_input(text)
    if not pre["valid"]:
        yield _sse("error", {"message": pre["message"], "code": pre["code"]})
        yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id, "status": "validation_failed"})
        return
    text = pre["sanitized"]

    yield _step("deep-security", "Security Guardian", "输入安全与权限预检")
    sec = await security_gate(text, use_llm=True, user_role=user_role)
    if not sec["pass"]:
        msg = f"⚠ {sec['reason']}"
        from app.services.chat_service import save_message
        await save_message(db, session_id, "user", text, trace_id=trace_id)
        await save_message(db, session_id, "assistant", msg, trace_id=trace_id)
        yield _step("deep-security", "Security Guardian", sec["reason"], "error")
        yield _sse("prompt_injection_detected", {"message": sec["reason"], "severity": sec["severity"], "blocked": True})
        yield _sse("message_done", {"messageId": assistant_msg_id, "traceId": trace_id, "status": "blocked"})
        return
    yield _step("deep-security", "Security Guardian", "通过", "done")

    from app.services.chat_service import save_message
    user_msg_id = await save_message(db, session_id, "user", text, trace_id=trace_id)
    saved_attachments = await save_message_attachments(
        db,
        session_id,
        incoming_attachments,
        message_id=user_msg_id,
        role="user",
    )
    # 保留原始 dataUrl 只用于可选视觉模型调用，不写入数据库。
    for saved, raw in zip(saved_attachments, incoming_attachments):
        if raw.get("dataUrl"):
            saved["dataUrl"] = raw["dataUrl"]

    yield _sse("agent_handoff", {"from": "Supervisor", "to": "Vision Expert", "reason": "深度思考需要图文理解"})
    yield _step("vision", "Vision Expert", f"分析 {len(saved_attachments)} 张图片")
    vision_results = await _vision_expert(text, saved_attachments)
    yield _sse("vision_result", {"items": [{k: v for k, v in item.items() if k != "dataUrl"} for item in vision_results]})
    yield _step("vision", "Vision Expert", "图片理解完成" if vision_results else "无图片输入，跳过", "done")

    yield _sse("agent_handoff", {"from": "Supervisor", "to": "Knowledge Expert", "reason": "执行图文混合知识检索"})
    yield _step("mm-rag", "Knowledge Expert", "图文混合检索知识库")
    rag_result = await search_multimodal_knowledge(db, text, vision_results, top_k=5)
    yield _sse("multimodal_rag", {
        "textSources": [r.get("title") for r in rag_result.get("text_results", [])[:5]],
        "imageSources": rag_result.get("image_results", [])[:5],
        "hasHighConfidenceImage": rag_result.get("has_high_confidence_image", False),
    })
    yield _step(
        "mm-rag",
        "Knowledge Expert",
        f"文本 {len(rag_result.get('text_results', []))} 条，图片 {len(rag_result.get('image_results', []))} 条",
        "done",
    )

    web_result = None
    if not rag_result.get("text_results") or not rag_result.get("has_high_confidence_image", False):
        yield _sse("agent_handoff", {
            "from": "Supervisor",
            "to": "Web Research Agent",
            "reason": "知识库文本或图片命中不足，进入外部资料检索兜底",
        })
        yield _step("web-research", "Web Research Agent", "检查外部资料检索能力")
        web_result = await _web_research(text, need_image=not rag_result.get("has_high_confidence_image", False))
        yield _sse("web_research", web_result)
        yield _step(
            "web-research",
            "Web Research Agent",
            web_result.get("note") or web_result.get("status", "done"),
            "done" if web_result.get("status") != "failed" else "error",
        )
        if web_result.get("findings"):
            external_context = "\n".join(
                f"- {i.get('title')}: {i.get('snippet')} ({i.get('url')})"
                for i in web_result.get("findings", [])[:5]
            )
            rag_result["context"] = "\n\n".join([v for v in [rag_result.get("context"), "## 外部资料专家补充\n" + external_context] if v])
            rag_result.setdefault("text_results", []).extend([
                {
                    "title": i.get("title"),
                    "snippet": i.get("snippet"),
                    "score": i.get("score", 0),
                    "source": i.get("source", "external"),
                    "url": i.get("url"),
                }
                for i in web_result.get("findings", [])[:3]
            ])
        if web_result.get("images"):
            rag_result.setdefault("image_results", []).extend(_external_images_to_rag(web_result.get("images", [])[:4]))

    from app.services.multimodal_assets import (
        diagram_to_markdown,
        generate_drawio_flowchart,
        generate_reference_image,
        materialize_image_candidates,
        review_image_candidates,
    )
    yield _sse("agent_handoff", {"from": "Supervisor", "to": "Image Review Agent", "reason": "外部资料图片需快速审核，避免低质量配图进入回答"})
    yield _step("image-review", "图片审核", "OCR/MCP 短超时审核候选图片")
    image_review = await review_image_candidates(text, rag_result.get("image_results", []))
    yield _step("image-review", "图片审核", image_review.get("summary", "图片审核完成"), "done")
    accepted_images = image_review.get("accepted") or []
    if not accepted_images:
        yield _step("image-refill", "图片补充检索", "审核后无可用图片，降低阈值并继续搜索")
        refill_query = f"{text} 麒麟 虚拟机 启动失败 故障 排查 流程图 截图"
        refill = await _web_research(refill_query, need_image=True)
        yield _sse("web_research", {**refill, "refill": True})
        refill_images = _external_images_to_rag((refill.get("images") or refill.get("items") or [])[:6])
        if refill_images:
            second_review = await review_image_candidates(text, refill_images)
            yield _step("image-refill", "图片补充检索", second_review.get("summary", "补充图片审核完成"), "done")
            accepted_images = second_review.get("accepted") or refill_images[:1]
            image_review = {
                **second_review,
                "summary": (second_review.get("summary") or "补充图片审核完成") + " 已执行补充检索，至少保留 1 张最高相关候选图。",
            }
        else:
            yield _step("image-refill", "图片补充检索", "外部补充搜索未返回图片，继续使用候选降级策略", "done")
    if not accepted_images:
        fallback_candidates = [
            img for img in (rag_result.get("image_results", []) or [])
            if isinstance(img.get("url"), str) and img.get("url").startswith(("http://", "https://", "data:image/"))
        ]
        fallback_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        accepted_images = fallback_candidates[:1]
        if accepted_images:
            image_review = {
                **image_review,
                "summary": "严格审核未命中图片，已降低要求并保留 1 张最高相关候选图。",
            }
    if accepted_images:
        reviewed_count = len(accepted_images)
        accepted_images = await materialize_image_candidates(accepted_images)
        accepted_images = [
            item for item in accepted_images
            if isinstance(item.get("url"), str)
            and item.get("url", "").startswith(("/api/", "http://", "https://", "data:image/"))
        ]
        if len(accepted_images) < reviewed_count:
            image_review = {
                **image_review,
                "summary": (
                    (image_review.get("summary") or "图片审核完成")
                    + f" 可展示资源校验后保留 {len(accepted_images)} 张，"
                    + f"丢弃 {reviewed_count - len(accepted_images)} 张无法缓存的远程图片。"
                ),
            }
    rag_result["image_results"] = accepted_images or []
    needs_visual_answer = forced_intent == "professional_answer" or _has_ops_problem(text)
    if not accepted_images and needs_visual_answer:
        yield _answer_media(
            "reference-image-1",
            "image",
            "pending",
            "运维排查参考图",
            caption="多模态图片专家正在根据知识资料生成可展示图片。",
        )
        prompt = (
            "生成一张专业运维知识示意图，用图标表现麒麟虚拟机故障排查。"
            "画面可包含宿主机、虚拟机、显示器、日志、磁盘空间和图形服务等视觉元素，布局清晰。"
            "图片中禁止出现任何文字、字母、数字、命令、表格、品牌 Logo 或伪造的软件截图；"
            "所有解释文字由回答正文提供，图片只负责辅助理解。"
            f"用户问题：{text[:300]}"
        )
        generated_image = await generate_reference_image(prompt)
        yield _sse("image_generation", generated_image)
        if generated_image.get("status") == "ok" and generated_image.get("url"):
            accepted_images = [{
                "title": "麒麟虚拟机启动失败排查示意图",
                "description": "由多模态图片专家根据外部资料与知识库内容生成的参考示意图",
                "url": generated_image["url"],
                "score": 0.3,
                "source": "generated",
            }]
            rag_result["image_results"] = accepted_images
        else:
            yield _answer_media(
                "reference-image-1",
                "image",
                "failed",
                "运维排查参考图",
                fallback=generated_image.get("note") or "图片生成服务未返回可展示资源。",
            )
    yield _sse("image_review", image_review)
    for index, image in enumerate(accepted_images[:3], 1):
        yield _answer_media(
            f"reference-image-{index}",
            "image",
            "ready",
            image.get("title") or f"参考图片 {index}",
            url=image.get("url"),
            alt=image.get("title") or f"参考图片 {index}",
            caption=image.get("description") or image.get("snippet") or "用于辅助理解对应排查步骤。",
        )

    route = _route_deep_link(text, saved_attachments, rag_result)
    yield _sse("route_dispatch", {
        "link": route["link"],
        "linkLabel": route["linkLabel"],
        "linkDescription": route["linkDescription"],
        "reason": "用户选择深度思考或提供图片，进入独立多模态链路",
        "intent": "multimodal_ops",
    })

    if forced_intent is None and _needs_intent_clarification(text, route):
        payload = _intent_clarification_payload(text, trace_id)
        message = payload["question"] + "\n\n请选择：\n1. 生成专业图文方案\n2. 进入 Plan-Execute 执行"
        await save_message(db, session_id, "assistant", message, trace_id=trace_id)
        yield _sse("intent_clarification", payload)
        yield _sse("token", {"token": message})
        yield _sse("state_cards", {
            "cards": [
                {"title": "Supervisor Router", "content": "等待用户确认目标", "status": "warning"},
                {"title": "候选链路", "content": "图文方案 / Plan-Execute", "status": "info"},
                {"title": "安全策略", "content": "未确认前不执行工具", "status": "success"},
            ],
            "riskColor": "orange",
        })
        yield _sse("message_done", {
            "messageId": assistant_msg_id,
            "traceId": trace_id,
            "status": "awaiting_intent_clarification",
            "thinkingMode": "deep",
        })
        return

    plan = None
    if forced_intent != "professional_answer" and not _asks_for_answer_only(text):
        yield _sse("agent_handoff", {"from": "Supervisor", "to": "Ops Diagnosis Planner", "reason": "用户已确认或表达需要执行方案"})
        plan = await _build_plan(text, rag_result, vision_results, server_id)
    if plan:
        from app.services.human_supervision import save_supervision_plan
        yield _sse("agent_handoff", {"from": "Supervisor", "to": "Answer Composer", "reason": "执行前先生成图文结合说明"})
        yield _step("compose", "Answer Composer", "先生成图文结合故障说明")
        yield _answer_media("solution-flowchart", "diagram", "pending", "处理流程图", caption="正在生成可视化执行流程。")
        diagram_task = asyncio.create_task(
            generate_drawio_flowchart(plan.get("title") or "运维处理流程", plan.get("steps") or [])
        )
        response_chunks: List[str] = []
        async for token in _compose_with_llm_stream(text, vision_results, rag_result, plan, web_result):
            response_chunks.append(token)
            yield _sse("token", {"token": token})
        response = _strip_unmanaged_markdown_images(
            _strip_diagram_source_blocks("".join(response_chunks))
        )
        normalized_response = _ensure_answer_table(response, plan)
        if normalized_response != response:
            table_suffix = normalized_response[len(response):]
            if table_suffix:
                yield _sse("token", {"token": table_suffix})
        response = normalized_response
        diagram = await diagram_task
        yield _sse("diagram_result", diagram)
        if diagram.get("url"):
            yield _answer_media(
                "solution-flowchart",
                "diagram",
                "ready",
                "处理流程图",
                url=diagram.get("url"),
                alt="Plan-Execute 处理流程图",
                caption=diagram.get("note") or diagram.get("qualityReview") or "根据诊断步骤生成的可视化流程。",
            )
        else:
            yield _answer_media(
                "solution-flowchart",
                "diagram",
                "failed",
                "处理流程图",
                fallback=diagram.get("mermaid") or diagram.get("note") or "流程图生成失败。",
            )
        stored_response = _prepend_user_visuals(response, vision_results)
        diagram_md = diagram_to_markdown(diagram)
        if diagram_md:
            stored_response += "\n\n## 处理流程图\n\n" + diagram_md + "\n"
        images = rag_result.get("image_results", [])[:3]
        image_md = _images_to_step_markdown(images, "图文辅助说明")
        if image_md:
            stored_response += "\n\n" + image_md + "\n"

        sp = await save_supervision_plan(
            db,
            session_id,
            trace_id,
            user_id,
            "fault_analysis",
            plan,
        )
        intro = (
            "已生成 **深度思考 Plan-Execute 运维方案**。"
            "该方案已转换为可执行步骤，确认后会复用现有安全门禁、审批、确认与回滚链路逐步执行。\n\n"
        )
        if plan.get("preliminary_analysis"):
            intro += str(plan["preliminary_analysis"]) + "\n\n"
        intro += (
            f"- 可自动执行步骤：{len(plan.get('steps') or [])} 步\n"
            f"- 人工处理建议：{len(plan.get('manual_steps') or [])} 条\n"
            "- 自动步骤仅包含只读排查或经过风险分级的操作；不会在未确认时执行。\n"
        )
        yield _sse("token", {"token": "\n\n---\n\n" + intro.strip()})
        full_response = stored_response.strip() + "\n\n---\n\n" + intro.strip()
        await save_message(db, session_id, "assistant", full_response, trace_id=trace_id)
        yield _sse("deep_plan", {"plan": plan, "planId": sp.id, "awaitingConfirm": True})
        yield _sse("diagnostic_plan", {
            "planId": sp.id,
            "traceId": trace_id,
            "plan": plan,
            "workflowLink": "deep_plan_execute",
            "message": "已先给出图文结合说明。请确认深度思考方案；确认后将环境预检并执行可自动化步骤。人工步骤会作为处置建议保留，不阻塞自动执行进度。",
        })
        yield _sse("state_cards", {
            "cards": [
                {"title": "思考链路", "content": "深度思考", "status": "success"},
                {"title": "方案状态", "content": "等待确认", "status": "warning"},
                {"title": "可执行步骤", "content": f"{len(plan.get('steps') or [])} 步", "status": "info"},
                {"title": "图片输入", "content": f"{len(saved_attachments)} 张", "status": "success" if saved_attachments else "info"},
            ],
            "riskColor": "orange",
        })
        yield _sse("message_done", {
            "messageId": assistant_msg_id,
            "traceId": trace_id,
            "status": "awaiting_plan_confirm",
            "planId": sp.id,
            "workflowLink": "deep_plan_execute",
            "thinkingMode": "deep",
        })
        return

    yield _sse("agent_handoff", {"from": "Supervisor", "to": "Answer Composer", "reason": "汇总专家结果并生成图文回答"})
    yield _step("compose", "Answer Composer", "生成标准化图文回答")
    answer_plan = plan
    if forced_intent == "professional_answer" or _asks_for_answer_only(text):
        answer_plan = await _build_plan(text, rag_result, vision_results, server_id)
    diagram_task = None
    if answer_plan:
        yield _answer_media("solution-flowchart", "diagram", "pending", "处理流程图", caption="正在生成标准化故障处理流程。")
        diagram_task = asyncio.create_task(
            generate_drawio_flowchart(answer_plan.get("title") or "处理建议流程", answer_plan.get("steps") or [])
        )

    response_chunks: List[str] = []
    async for token in _compose_with_llm_stream(text, vision_results, rag_result, answer_plan, web_result):
        response_chunks.append(token)
        yield _sse("token", {"token": token})
    response = _strip_unmanaged_markdown_images(
        _strip_diagram_source_blocks("".join(response_chunks))
    )
    normalized_response = _ensure_answer_table(response, answer_plan)
    if normalized_response != response:
        table_suffix = normalized_response[len(response):]
        if table_suffix:
            yield _sse("token", {"token": table_suffix})
    response = normalized_response
    stored_response = _prepend_user_visuals(response, vision_results)
    if diagram_task:
        diagram = await diagram_task
        yield _sse("diagram_result", diagram)
        if diagram.get("url"):
            yield _answer_media(
                "solution-flowchart",
                "diagram",
                "ready",
                "处理流程图",
                url=diagram.get("url"),
                alt="故障处理流程图",
                caption=diagram.get("note") or diagram.get("qualityReview") or "根据标准化排查步骤生成的可视化流程。",
            )
        else:
            yield _answer_media(
                "solution-flowchart",
                "diagram",
                "failed",
                "处理流程图",
                fallback=diagram.get("mermaid") or diagram.get("note") or "流程图生成失败。",
            )
        diagram_md = diagram_to_markdown(diagram)
        if diagram_md:
            stored_response += "\n\n## 处理流程图\n\n" + diagram_md + "\n"

    images = rag_result.get("image_results", [])[:3]
    image_md = _images_to_step_markdown(images, "相关步骤配图")
    if image_md:
        stored_response += "\n\n" + image_md + "\n"

    await save_message(db, session_id, "assistant", stored_response, trace_id=trace_id)

    yield _sse("state_cards", {
        "cards": [
            {"title": "思考链路", "content": "深度思考", "status": "success"},
            {"title": "专家协同", "content": "Supervisor + 7 专家", "status": "info"},
            {"title": "图片输入", "content": f"{len(saved_attachments)} 张", "status": "success" if saved_attachments else "info"},
            {"title": "知识库", "content": f"{len(rag_result.get('text_results', []))} 条文本依据", "status": "info"},
        ],
        "riskColor": "blue",
    })
    yield _step("compose", "Answer Composer", "回答已生成", "done")
    yield _sse("message_done", {
        "messageId": assistant_msg_id,
        "traceId": trace_id,
        "status": "completed",
        "thinkingMode": "deep",
    })
