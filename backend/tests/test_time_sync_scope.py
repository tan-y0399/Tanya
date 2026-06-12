"""时间同步诉求识别与方案生成测试。"""
import asyncio

from app.core.command_security import analyze_command
from app.services.chat_service import _parse_plan_step_to_tool
from app.services.human_supervision import build_diagnostic_plan
from app.services.ops_scope import is_time_sync_execution_request, is_time_sync_request
from app.services.response_summarizer import (
    _tools_irrelevant_to_request,
    build_rule_based_conclusion,
)


USER_QUERY = "将该系统的时间设计同步与主机时间"


def test_detect_time_sync_request():
    assert is_time_sync_request(USER_QUERY)
    assert is_time_sync_execution_request(USER_QUERY)
    assert is_time_sync_execution_request("将该系统的时间与主机继续同步")
    assert not is_time_sync_execution_request("如何配置 NTP 时间同步")


def test_build_time_sync_plan():
    plan = asyncio.run(build_diagnostic_plan(USER_QUERY, "high_risk", ""))
    hints = [s["tool_hint"] for s in plan["steps"]]
    assert "execute_command: timedatectl status" in hints
    assert "execute_command: chronyc tracking" in hints
    assert "execute_command: chronyc -a makestep" in hints
    assert "get_disk_usage" not in " ".join(hints)


def test_parse_plan_steps():
    plan = asyncio.run(build_diagnostic_plan(USER_QUERY, "high_risk", ""))
    tools = []
    for step in plan["steps"]:
        parsed = _parse_plan_step_to_tool(step)
        if parsed:
            tools.append(parsed[0])
    assert tools == [
        "execute_command",
        "execute_command",
        "execute_command",
        "execute_command",
    ]


def test_command_security_readonly_time_cmds():
    ro = analyze_command("timedatectl status")
    assert ro["risk_level"] == "L1"
    assert not ro["require_approval"]
    assert not ro["require_confirm"]

    wr = analyze_command("chronyc -a makestep")
    assert wr["require_confirm"]
    assert not wr["require_approval"]


def test_irrelevant_tools_guard():
    records = [{"toolName": "get_disk_usage", "status": "completed", "result": {"success": True}}]
    assert _tools_irrelevant_to_request(USER_QUERY, records)
    conclusion = build_rule_based_conclusion(USER_QUERY, records)
    assert "尚未执行时间同步" in conclusion or "未执行与时间同步相关" in conclusion
