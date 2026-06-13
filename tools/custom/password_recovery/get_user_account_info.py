"""KylinOps 工具：get_user_account_info — 查询指定 Linux 用户账户信息"""
NAME = "get_user_account_info"
DESCRIPTION = (
    "生成查询指定用户 UID、GID、家目录、登录 Shell、账户过期信息的远程命令。"
    "用于密码重置前确认目标用户存在且信息正确。"
)
CATEGORY = "system_operation"
RISK_LEVEL = 1

TRIAL_ARGS = {"username": "kylin"}


def _cmds(username: str):
    u = username.replace("'", "")
    return [
        {"command": f"getent passwd {u}", "purpose": "基础账户信息（用户:密码占位:UID:GID:描述:家目录:Shell）"},
        {"command": f"id {u}", "purpose": "UID/GID 及所属组"},
        {"command": f"chage -l {u} 2>/dev/null || echo 'chage-not-available'", "purpose": "密码过期与锁定策略"},
        {"command": f"test -d $(getent passwd {u} | cut -d: -f6) && echo homedir-ok || echo homedir-missing", "purpose": "家目录是否存在"},
    ]


def _parse_hints():
    return {
        "getent_missing": "用户不存在，请核对用户名或是否仅为系统用户",
        "homedir_missing": "家目录缺失可能导致登录异常，重置密码后仍需修复目录",
        "shell_nologin": "Shell 为 /sbin/nologin 时无法交互登录",
    }


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
            "parse_hints": _parse_hints(),
            "agent_instruction": "通过 execute_command 执行 commands，解析 getent passwd 输出字段",
            "trial_simulated": {
                "username": username,
                "uid": 1000,
                "home": f"/home/{username}",
                "shell": "/bin/bash",
                "exists": True,
            },
            "summary": f"已生成用户「{username}」账户信息查询命令",
        },
    }
