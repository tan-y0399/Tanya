"""KylinOps 工具：reset_user_password — 在线重置指定用户密码（需审批 L4~L5）"""
NAME = "reset_user_password"
DESCRIPTION = (
    "生成在目标麒麟 VM 上通过 chpasswd 非交互重置指定用户密码的命令。"
    "禁止直接编辑 /etc/shadow；执行前需审批；密码须符合 get_password_policy 策略。"
)
CATEGORY = "system_operation"
RISK_LEVEL = 5

TRIAL_ARGS = {
    "username": "kylin",
    "new_password": "Kylin@Temp2026!",
    "dry_run": True,
}


def run(**kwargs):
    username = (kwargs.get("username") or kwargs.get("user") or "").strip()
    new_password = kwargs.get("new_password") or kwargs.get("password") or ""
    dry_run = bool(kwargs.get("dry_run", False))

    if not username:
        return {"success": False, "error": "请提供 username 参数"}
    if not new_password:
        return {"success": False, "error": "请提供 new_password 参数"}

    safe_user = username.replace("'", "").replace(":", "")
    # chpasswd 格式 user:password，密码中含 : 需转义或改用 passwd --stdin
    escaped_pw = new_password.replace("'", "'\\''")
    command = f"echo '{safe_user}:{escaped_pw}' | chpasswd"

    audit_entry = {
        "action": "reset_user_password",
        "username": username,
        "method": "chpasswd",
        "dry_run": dry_run,
        "operator_note": "须记录工单号与审批人",
    }

    return {
        "success": True,
        "data": {
            "tool": NAME,
            "execution_mode": "remote_ssh",
            "risk_level": RISK_LEVEL,
            "requires_approval": True,
            "username": username,
            "dry_run": dry_run,
            "commands": [
                {
                    "command": command,
                    "purpose": "通过 chpasswd 非交互重置密码",
                    "forbidden": "禁止 sed/echo 直接写入 /etc/shadow",
                },
            ],
            "alternative_commands": [
                {
                    "command": f"echo '{escaped_pw}' | passwd --stdin {safe_user}",
                    "purpose": "部分旧系统可用 passwd --stdin",
                },
            ],
            "audit": audit_entry,
            "agent_instruction": (
                "确认已完成 get_user_account_info、check_account_lock_status、get_password_policy；"
                "获得 L4/L5 审批后通过 execute_command 执行；"
                "dry_run=true 时仅返回命令不执行；执行后调用 verify_account_after_reset"
            ),
            "trial_simulated": {
                "executed": False,
                "dry_run": dry_run,
                "message": "试运行模式：未实际改密，命令已生成",
            },
            "summary": f"已生成用户「{username}」密码重置命令（{'干跑' if dry_run else '待审批执行'}）",
        },
    }
