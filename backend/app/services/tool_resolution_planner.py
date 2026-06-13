"""工具库 + 知识库联合决策：是否可走可执行运维方案"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.custom_tool_registry import load_custom_tool_registry

PASSWORD_QUERY_MARKERS = [
    "忘记密码", "密码忘记", "忘了密码", "密码丢了", "密码丢失",
    "无法登录", "登录不了", "进不了系统", "密码错误", "密码不对",
    "重置密码", "找回密码", "恢复密码", "改密码", "修改密码",
    "passwd", "password",
]

PASSWORD_RECOVERY_TOOLS = [
    "check_ssh_connectivity",
    "check_console_access_available",
    "get_user_account_info",
    "check_account_lock_status",
    "get_password_policy",
    "reset_user_password",
    "verify_account_after_reset",
    "get_password_recovery_playbook",
]

PASSWORD_RECOVERY_PLAN = [
    ("check_ssh_connectivity", "检测目标 VM SSH 是否可达，决定在线改密或离线指引", "L1"),
    ("check_console_access_available", "确认用户是否具备虚拟机控制台访问能力", "L1"),
    ("get_user_account_info", "查询目标用户 UID、家目录、Shell 等信息", "L1"),
    ("check_account_lock_status", "检查是否因 faillock 锁定而非真忘密", "L1"),
    ("get_password_policy", "读取密码复杂度策略以生成合规临时密码", "L1"),
    ("reset_user_password", "SSH 可达且已审批时在线重置密码", "L5"),
    ("verify_account_after_reset", "改密后验证账户与家目录状态", "L2"),
    ("get_password_recovery_playbook", "SSH 不可达且无其他手段时生成 GRUB/救援离线手册", "L1"),
]


def is_password_recovery_query(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    if any(m in t or m in low for m in PASSWORD_QUERY_MARKERS):
        return True
    if "密码" in t and re.search(r"忘|丢|重置|找回|改|恢复|不对|错误", t):
        return True
    return False


def _score_tool_match(content: str, tool_name: str, description: str) -> float:
    text = f"{content} {tool_name} {description}".lower()
    score = 0.0
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z_]{3,}", content.lower())
    for tok in tokens:
        if tok in tool_name.lower() or tok in description.lower():
            score += 1.0
    if tool_name.replace("_", " ") in content.lower():
        score += 2.0
    return score


async def evaluate_tool_resolution(
    db: AsyncSession,
    content: str,
    rag_context: str = "",
) -> Dict[str, Any]:
    """
    结合用户诉求与已启用自定义工具，判断是否应走「可执行方案」而非纯知识问答。

    返回:
      actionable, workflow, matched_tools, reason, prefer_plan, tool_hints
    """
    registry = await load_custom_tool_registry(db)
    enabled_names = set(registry.tools.keys())

    if not enabled_names:
        return {
            "actionable": False,
            "workflow": None,
            "matched_tools": [],
            "reason": "无已启用的自定义工具",
            "prefer_plan": False,
        }

    # ── 密码找回专项流程 ──
    if is_password_recovery_query(content):
        matched = [n for n in PASSWORD_RECOVERY_TOOLS if n in enabled_names]
        if matched:
            return {
                "actionable": True,
                "workflow": "password_recovery",
                "matched_tools": matched,
                "reason": "密码找回类问题且工具库已注册诊断/执行/离线手册工具",
                "prefer_plan": True,
                "tool_hints": _tool_hints(registry, matched),
            }
        # 有知识库但无专用工具 → 仅知识问答
        if rag_context:
            return {
                "actionable": False,
                "workflow": None,
                "matched_tools": [],
                "reason": "密码找回诉求但尚未注册专用工具，回退知识库指引",
                "prefer_plan": False,
            }

    # ── 通用：按描述关键词匹配自定义工具 ──
    scored: List[tuple] = []
    for name, entry in registry.tools.items():
        s = _score_tool_match(content, name, entry.get("description") or "")
        if s >= 2.0:
            scored.append((s, name))
    scored.sort(reverse=True)

    if scored and scored[0][0] >= 3.0:
        matched = [n for _, n in scored[:5]]
        return {
            "actionable": True,
            "workflow": "custom_tools",
            "matched_tools": matched,
            "reason": f"工具库命中: {', '.join(matched[:3])}",
            "prefer_plan": len(matched) >= 2,
            "tool_hints": _tool_hints(registry, matched),
        }

    return {
        "actionable": False,
        "workflow": None,
        "matched_tools": [],
        "reason": "无足够匹配的可执行工具",
        "prefer_plan": False,
    }


def _tool_hints(registry, names: List[str]) -> List[Dict[str, str]]:
    hints = []
    for n in names:
        entry = registry.tools.get(n)
        if entry:
            hints.append({"name": n, "description": entry.get("description") or n})
    return hints


def build_password_recovery_plan_steps(matched_tools: List[str]) -> List[dict]:
    """生成 Plan-Execute 步骤（仅包含已注册工具）。"""
    matched_set = set(matched_tools)
    steps = []
    order = 1
    for name, action, risk in PASSWORD_RECOVERY_PLAN:
        if name not in matched_set:
            continue
        steps.append({
            "order": order,
            "action": action,
            "tool_hint": name,
            "risk": risk,
        })
        order += 1
    return steps


def build_tool_resolution_prompt(resolution: dict) -> str:
    """注入 ReAct system prompt 的工具执行指引。"""
    if not resolution.get("actionable"):
        return ""
    lines = [
        "\n\n## 工具库可执行方案（优先于纯文字回答）",
        f"判定：{resolution.get('reason', '')}",
        "请结合上方知识库参考，**先调用下列已注册工具**完成诊断与方案生成；",
        "仅在工具无法覆盖或用户环境不满足执行条件时，再回退为知识库步骤说明。",
        "",
        "### 推荐工具顺序",
    ]
    for h in resolution.get("tool_hints") or []:
        lines.append(f"- `{h['name']}`：{h['description']}")
    if resolution.get("workflow") == "password_recovery":
        lines.extend([
            "",
            "### 密码找回分支",
            "1. 先 `check_ssh_connectivity` → SSH 可达则走在线链（账户信息→锁定→策略→改密→验证）",
            "2. SSH 不可达 → `check_console_access_available` → 有控制台则 `get_password_recovery_playbook`",
            "3. 远程类工具返回 `commands` 时，再用 `execute_command` 在目标 VM 执行",
            "4. `reset_user_password` 需 L5 审批；禁止直接改 /etc/shadow",
        ])
    return "\n".join(lines)
