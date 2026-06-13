"""KylinOps 工具：check_account_lock_status — 检查账户是否被 PAM 锁定"""
NAME = "check_account_lock_status"
DESCRIPTION = (
    "生成 faillock / pam_tally2 检查命令，判断账户是否因多次输错密码被锁定。"
    "若仅锁定而非遗忘密码，优先解锁而非重置。"
)
CATEGORY = "system_operation"
RISK_LEVEL = 1

TRIAL_ARGS = {"username": "kylin"}


def _cmds(username: str):
    u = username.replace("'", "")
    return [
        {"command": f"faillock --user {u} 2>/dev/null || echo 'faillock-not-installed'", "purpose": "faillock 锁定记录（较新系统）"},
        {"command": f"pam_tally2 --user {u} 2>/dev/null || echo 'pam_tally2-not-installed'", "purpose": "pam_tally2 失败次数（旧系统）"},
        {"command": f"grep -E '^{u}:' /etc/shadow 2>/dev/null | cut -d: -f2 | head -c 20 || echo 'no-shadow-access'", "purpose": "shadow 状态抽样（!! 表示锁定，无直接改密）"},
    ]


def run(**kwargs):
    username = (kwargs.get("username") or kwargs.get("user") or "").strip()
    if not username:
        return {"success": False, "error": "请提供 username 参数"}

    return {
        "success": True,
        "data": {
            "tool": NAME,
            "execution_mode": "remote_ssh",
            "username": username,
            "commands": _cmds(username),
            "unlock_commands": [
                {"command": f"faillock --user {username} --reset", "purpose": "解除 faillock 锁定", "risk": "L3"},
                {"command": f"pam_tally2 --user {username} --reset", "purpose": "重置 pam_tally2 计数", "risk": "L3"},
            ],
            "decision_rules": {
                "locked": "优先执行 unlock_commands 后让用户重试原密码",
                "not_locked": "继续 get_password_policy → reset_user_password 流程",
            },
            "agent_instruction": "先执行检查命令；若锁定则解锁并告知用户，勿急于改密",
            "trial_simulated": {"username": username, "locked": False, "fail_count": 0},
            "summary": f"已生成用户「{username}」账户锁定状态检查方案",
        },
    }
