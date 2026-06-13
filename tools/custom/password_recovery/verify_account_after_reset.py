"""KylinOps 工具：verify_account_after_reset — 改密后验证账户状态"""
NAME = "verify_account_after_reset"
DESCRIPTION = (
    "生成改密后验证命令：账户未锁定、getent 可查、家目录权限正常、"
    "shadow 状态有效。确认在线改密成功且用户可登录。"
)
CATEGORY = "system_operation"
RISK_LEVEL = 2

TRIAL_ARGS = {"username": "kylin"}


def _cmds(username: str):
    u = username.replace("'", "")
    return [
        {"command": f"getent passwd {u}", "purpose": "确认账户仍存在于 NSS"},
        {"command": f"faillock --user {u} 2>/dev/null | tail -n +1 || echo 'faillock-ok-or-n/a'", "purpose": "确认未被 faillock 锁定"},
        {"command": f"id {u}", "purpose": "确认 UID/GID 未变"},
        {
            "command": (
                f"H=$(getent passwd {u} | cut -d: -f6); "
                f"ls -ld \"$H\" 2>/dev/null || echo homedir-check-failed"
            ),
            "purpose": "家目录存在且权限合理（通常 drwx------ 或 drwxr-xr-x）",
        },
        {
            "command": f"grep -E '^{u}:' /etc/shadow 2>/dev/null | cut -d: -f2 | head -c 5 || echo shadow-n/a",
            "purpose": "shadow 哈希非空且非 !! 锁定占位",
        },
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
            "pass_criteria": [
                "getent passwd 有输出",
                "faillock 无失败记录或已 reset",
                "家目录 ls -ld 成功",
                "shadow 第二字段为 $ 开头的哈希而非 !! 或空",
            ],
            "on_failure": {
                "locked": "执行 faillock --user {user} --reset",
                "homedir": "检查家目录路径与属主 chown",
                "shadow": "勿手改 shadow，重新执行 reset_user_password",
            },
            "agent_instruction": "reset_user_password 成功后执行本工具 commands，全部通过则告知用户用新密码登录",
            "trial_simulated": {
                "username": username,
                "verified": True,
                "checks_passed": 4,
            },
            "summary": f"已生成用户「{username}」改密后验证命令",
        },
    }
