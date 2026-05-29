import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.command_security import analyze_command, get_risk_level_info, RiskLevel
from app.core.trace import generate_trace_id
from app.models.approval import Approval
from app.models.audit import AuditRecord
from app.services.remote_executor import execute_tool


class WorkflowStage:
    PROMPT_INJECTION = "prompt_injection"
    INTENT_PARSING = "intent_parsing"
    ENV_AWARENESS = "env_awareness"
    RISK_FILTER = "risk_filter"
    PERMISSION_CHECK = "permission_check"
    EXECUTION = "execution"
    TRACE = "trace"


class WorkflowResult:
    def __init__(self):
        self.success: bool = False
        self.stage: str = ""
        self.message: str = ""
        self.data: Dict = {}
        self.risk_level: str = RiskLevel.SAFE.value
        self.require_approval: bool = False
        self.require_confirm: bool = False
        self.approval_id: Optional[str] = None
        self.blocked: bool = False
        self.trace_id: str = generate_trace_id()

    def to_dict(self):
        return {
            "success": self.success,
            "stage": self.stage,
            "message": self.message,
            "data": self.data,
            "risk_level": self.risk_level,
            "require_approval": self.require_approval,
            "require_confirm": self.require_confirm,
            "approval_id": self.approval_id,
            "blocked": self.blocked,
            "trace_id": self.trace_id,
        }


# ── 扩展的注入检测模式（含严重级别）──
INJECTION_PATTERNS = [
    # critical — 明确越狱/规则覆盖
    (re.compile(r"(?i)ignore\s+(previous|prior|above|all|earlier)\s+(instructions?|rules?|directives?|commands?)"), "critical"),
    (re.compile(r"(?i)forget\s+(everything|all|your)\s+(previous|prior|training|rules?)"), "critical"),
    (re.compile(r"(?i)(new|overwrite|replace)\s+(instructions?|directives?|rules?)"), "critical"),
    # high — 系统提示词提取/角色劫持
    (re.compile(r"(?i)(system\s*prompt|your\s*prompt)\s*(is|:|=|now|should\s*be)"), "high"),
    (re.compile(r"(?i)(display|show|print|reveal|dump)\s*(your\s*)?(system\s*)?(prompt|instructions?|rules?)"), "high"),
    (re.compile(r"(?i)you\s+are\s+now\s+(a\s+)?(different|new|another)"), "high"),
    (re.compile(r"(?i)do\s+(exactly|everything)\s+(I|the\s+user)\s+(say|tell\s+you|command)"), "high"),
    (re.compile(r"(?i)(pretend|imagine)\s+(you\s+are|to\s+be)"), "high"),
    # medium — 尝试绕过/混淆
    (re.compile(r"(?i)act\s+as\s+(if\s+you\s+are|a\s+different)"), "medium"),
    (re.compile(r"(?i)from\s+now\s+on\s+(you\s+are|your\s+name\s+is)"), "medium"),
    (re.compile(r"(?i)disregard\s+(previous|prior|above|all|earlier|existing)\s+"), "medium"),
    (re.compile(r"(?i)bypass\s*(security|check|filter|guard)"), "medium"),
    (re.compile(r"(?i)execute\s+(without|bypass|skip)\s*(check|approval|security)"), "medium"),
    # low — 危险的系统命令直接嵌入
    (re.compile(r"(?i)rm\s+-rf\s*\/"), "low"),
    (re.compile(r"(?i)format\s*(disk|partition)"), "low"),
    (re.compile(r"(?i)shutdown\s+-h\s+now"), "low"),
    (re.compile(r"(?i)reboot\s+-f"), "low"),
    (re.compile(r"(?i)mkfs\."), "low"),
]

# URL 和外部内容注入检测
EXTERNAL_CONTENT_PATTERNS = [
    (re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+'), "external_url"),
    (re.compile(r'<script[^>]*>'), "xss"),
    (re.compile(r'<iframe[^>]*>'), "xss"),
    (re.compile(r'<img[^>]*onerror[^>]*>'), "xss"),
    (re.compile(r'```[\s\S]*?```'), "code_block"),
]


def _detect_prompt_injection(user_input: str) -> dict:
    """检测提示词注入，返回 {pass, reason, pattern, severity}"""
    if not user_input or not user_input.strip():
        return {"pass": True, "reason": "", "pattern": "", "severity": "none"}

    for pattern, severity in INJECTION_PATTERNS:
        match = pattern.search(user_input)
        if match:
            pattern_desc = pattern.pattern.replace("\\s*", " ")[:80]
            return {
                "pass": severity == "low",
                "reason": f"检测到注入模式 [{severity}]: {pattern_desc}",
                "pattern": pattern.pattern,
                "severity": severity,
            }
    return {"pass": True, "reason": "", "pattern": "", "severity": "none"}


def check_external_content(user_input: str) -> dict:
    """扫描外部内容注入（URL/XSS/代码块）"""
    findings = []
    for pattern, content_type in EXTERNAL_CONTENT_PATTERNS:
        matches = pattern.findall(user_input)
        if matches:
            findings.append({"type": content_type, "count": len(matches), "matches": matches[:3]})
    return {
        "has_external_content": len(findings) > 0,
        "findings": findings,
        "safe": len(findings) == 0,
    }


class SecurityWorkflow:
    def __init__(self, db: AsyncSession, user_id: str, session_id: str):
        self.db = db
        self.user_id = user_id
        self.session_id = session_id
        self.trace_id = generate_trace_id()

    async def run(self, user_input: str) -> WorkflowResult:
        result = WorkflowResult()
        result.trace_id = self.trace_id

        result.stage = WorkflowStage.PROMPT_INJECTION
        injection_result = _detect_prompt_injection(user_input)
        if not injection_result["pass"]:
            result.success = False
            result.message = injection_result["reason"]
            result.blocked = True
            await self._record_audit(result, user_input, "blocked", "prompt_injection")
            return result

        result.stage = WorkflowStage.INTENT_PARSING
        intent_result = self._parse_intent(user_input)
        if not intent_result["success"]:
            result.success = False
            result.message = intent_result["error"]
            await self._record_audit(result, user_input, "failed", "intent_parsing")
            return result
        result.data["intent"] = intent_result

        result.stage = WorkflowStage.ENV_AWARENESS
        env_result = await self._env_awareness()
        result.data["environment"] = env_result

        result.stage = WorkflowStage.RISK_FILTER
        risk_result = await self._risk_filter(intent_result)
        result.risk_level = risk_result["risk_level"]
        result.require_approval = risk_result["require_approval"]
        result.require_confirm = risk_result["require_confirm"]
        result.blocked = risk_result.get("blocked", False)

        if risk_result.get("blocked", False):
            result.success = False
            result.message = risk_result.get("block_message", "命令被阻止")
            await self._record_audit(result, user_input, "blocked", "risk_filter")
            return result

        if result.require_approval:
            result.approval_id = await self._create_approval(intent_result)
            result.success = False
            result.message = "需要审批"
            await self._record_audit(result, user_input, "pending_approval", "risk_filter")
            return result

        result.stage = WorkflowStage.PERMISSION_CHECK
        permission_result = await self._permission_check(intent_result)
        if not permission_result["allowed"]:
            result.success = False
            result.message = permission_result["reason"]
            await self._record_audit(result, user_input, "denied", "permission_check")
            return result

        result.stage = WorkflowStage.EXECUTION
        execution_result = await self._execute(intent_result)
        result.success = execution_result["success"]
        result.message = execution_result.get("message", "")
        result.data["execution"] = execution_result

        await self._record_audit(result, user_input, "completed", "execution")

        return result

    def _parse_intent(self, user_input: str) -> Dict:
        parts = user_input.strip().split("\n")
        command = ""
        comment = ""

        for part in parts:
            if part.strip().startswith(("!", "$", ">")):
                command = part.strip().lstrip("!$> ").strip()
            elif "命令" in part or "执行" in part or "run" in part.lower():
                match = re.search(r"(?i)(?:命令|执行|run)\s*[:：]?\s*['\"`]?(.+?)['\"`]?", part)
                if match:
                    command = match.group(1).strip()
            elif command:
                comment += part + "\n"

        if not command:
            if re.match(r"^\s*[a-zA-Z][a-zA-Z0-9_-]*\s", user_input):
                command = user_input.strip()

        if not command:
            return {"success": False, "error": "未识别到命令"}

        return {
            "success": True,
            "command": command,
            "comment": comment.strip(),
            "type": "command_execution",
        }

    async def _env_awareness(self) -> Dict:
        try:
            sys_info = execute_tool("get_system_info")
            cpu_info = execute_tool("get_cpu_info")
            mem_info = execute_tool("get_memory_info")
            return {
                "system": sys_info.get("data", {}),
                "cpu": cpu_info.get("data", {}),
                "memory": mem_info.get("data", {}),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def _risk_filter(self, intent: Dict) -> Dict:
        command = intent.get("command", "")
        analysis = analyze_command(command)

        if not analysis["success"]:
            return {
                "risk_level": RiskLevel.MEDIUM.value,
                "require_approval": True,
                "require_confirm": True,
                "blocked": False,
                "reason": analysis.get("error", "命令分析失败"),
            }

        risk_info = get_risk_level_info(analysis["risk_level"])

        return {
            "risk_level": analysis["risk_level"],
            "require_approval": analysis["require_approval"],
            "require_confirm": analysis["require_confirm"],
            "blocked": analysis.get("blocked", False),
            "block_message": analysis.get("block_message"),
            "group": analysis.get("group"),
            "group_name": analysis.get("group_name"),
            "reason": analysis.get("reason", risk_info["description"]),
            "analysis": analysis,
        }

    async def _permission_check(self, intent: Dict) -> Dict:
        command = intent.get("command", "")
        analysis = analyze_command(command)

        if analysis.get("blocked", False):
            return {"allowed": False, "reason": analysis.get("block_message", "命令被阻止")}

        from sqlalchemy import select
        from app.models.user import User

        result = await self.db.execute(select(User).where(User.id == self.user_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"allowed": False, "reason": "用户不存在"}

        role = user.role
        risk_level = analysis.get("risk_level", RiskLevel.SAFE.value)

        if role == "admin":
            return {"allowed": True, "reason": "管理员权限"}

        if role == "auditor":
            if risk_level in [RiskLevel.SAFE.value, RiskLevel.LOW.value]:
                return {"allowed": True, "reason": "审计员权限允许"}
            return {"allowed": False, "reason": "审计员权限不足"}

        return {"allowed": False, "reason": "未知角色"}

    async def _create_approval(self, intent: Dict) -> str:
        analysis = analyze_command(intent.get("command", ""))
        expires_at = datetime.utcnow() + timedelta(minutes=settings.approval_timeout)

        approval = Approval(
            trace_id=self.trace_id,
            session_id=self.session_id,
            tool_name="execute_command",
            tool_params_json=json.dumps({
                "command": intent.get("command", ""),
                "comment": intent.get("comment", ""),
            }),
            risk_level=analysis.get("risk_level", RiskLevel.MEDIUM.value),
            detail=f"执行命令: {intent.get('command', '')}",
            requested_by=self.user_id,
            expires_at=expires_at,
        )

        self.db.add(approval)
        await self.db.commit()
        await self.db.refresh(approval)

        return approval.id

    async def _execute(self, intent: Dict) -> Dict:
        command = intent.get("command", "")

        try:
            result = execute_tool("run_command", command=command, timeout=30)

            if result.get("success", False):
                return {
                    "success": True,
                    "command": command,
                    "output": result.get("data", {}),
                    "message": "命令执行成功",
                }
            else:
                return {
                    "success": False,
                    "command": command,
                    "error": result.get("error", "执行失败"),
                    "message": f"命令执行失败: {result.get('error', '未知错误')}",
                }
        except Exception as e:
            return {
                "success": False,
                "command": command,
                "error": str(e),
                "message": f"命令执行异常: {str(e)}",
            }

    async def _record_audit(self, result: WorkflowResult, user_input: str, status: str, stage: str):
        try:
            audit = AuditRecord(
                trace_id=result.trace_id,
                session_id=self.session_id,
                user_id=self.user_id,
                event_type="workflow",
                summary=f"{stage}: {status} | {user_input[:50]}",
                risk_level=result.risk_level,
                detail_json=json.dumps({
                    "stage": result.stage,
                    "status": status,
                    "input": user_input[:200],
                    "risk_level": result.risk_level,
                    "require_approval": result.require_approval,
                    "require_confirm": result.require_confirm,
                    "approval_id": result.approval_id,
                    "blocked": result.blocked,
                }, ensure_ascii=False),
            )
            self.db.add(audit)
            await self.db.commit()
        except Exception:
            pass
