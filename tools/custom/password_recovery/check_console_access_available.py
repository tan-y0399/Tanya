"""KylinOps 工具：check_console_access_available — 确认是否有虚拟机控制台"""
NAME = "check_console_access_available"
DESCRIPTION = (
    "询问并记录用户是否拥有目标虚拟机控制台访问能力（VMware/VirtualBox/VNC/物理显示器/IPMI）。"
    "离线密码恢复（GRUB/LiveCD）必须在控制台操作，本工具用于分支判断：仅指引或可走在线改密。"
)
CATEGORY = "system_operation"
RISK_LEVEL = 1

TRIAL_ARGS = {
    "has_console": True,
    "console_type": "vmware",
    "target_host": "192.168.1.100",
}

CONSOLE_TYPES = {
    "vmware": "VMware Workstation / ESXi 控制台",
    "virtualbox": "VirtualBox 图形控制台",
    "vnc": "VNC / 远程 KVM",
    "physical": "物理机显示器 + 键盘",
    "ipmi": "IPMI / iLO / iDRAC 带外",
    "unknown": "未明确",
}


def run(**kwargs):
    has_console = kwargs.get("has_console")
    if has_console is None:
        has_console = kwargs.get("console_available")
    console_type = (kwargs.get("console_type") or "unknown").strip().lower()
    target_host = (kwargs.get("target_host") or kwargs.get("host") or "").strip()
    notes = (kwargs.get("notes") or "").strip()

    if has_console is None:
        return {
            "success": False,
            "error": "请提供 has_console（true/false）表示用户是否能打开虚拟机控制台",
        }

    has_console = bool(has_console)
    label = CONSOLE_TYPES.get(console_type, CONSOLE_TYPES["unknown"])

    if has_console:
        route = "offline_playbook"
        summary = f"用户具备控制台访问（{label}），可走 GRUB/救援/LiveCD 离线恢复流程"
        next_tools = ["get_password_recovery_playbook"]
        warnings = []
    else:
        route = "online_or_escalate"
        summary = "用户无控制台访问，无法执行 GRUB/LiveCD 离线改密，需尝试 SSH 在线改密或联系机房带外"
        next_tools = ["check_ssh_connectivity", "reset_user_password"]
        warnings = ["离线恢复必须在控制台完成，Agent 无法远程代替按键操作"]

    return {
        "success": True,
        "data": {
            "tool": NAME,
            "target_host": target_host,
            "has_console": has_console,
            "console_type": console_type,
            "console_label": label,
            "notes": notes,
            "recommended_route": route,
            "next_tools": next_tools,
            "warnings": warnings,
            "agent_questions": [
                "您是否能打开该虚拟机的控制台窗口（VMware/VirtualBox/物理屏幕）？",
                "控制台类型是 VMware、VirtualBox、VNC 还是物理机？",
            ],
            "summary": summary,
        },
    }
