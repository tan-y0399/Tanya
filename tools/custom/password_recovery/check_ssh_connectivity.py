"""KylinOps 工具：check_ssh_connectivity — 检测目标 VM SSH 连通性与登录账号"""
NAME = "check_ssh_connectivity"
DESCRIPTION = (
    "生成在目标麒麟 VM 上检测 SSH 连通性的命令集与判定规则。"
    "用于决定走「在线 reset_user_password」还是「离线 get_password_recovery_playbook」流程。"
)
CATEGORY = "system_monitor"
RISK_LEVEL = 1

TRIAL_ARGS = {"host": "192.168.1.100", "port": 22, "ssh_user": "root"}

REMOTE_COMMANDS = [
    {"command": "whoami", "purpose": "确认当前 SSH 登录账号"},
    {"command": "hostname", "purpose": "确认目标主机名"},
    {"command": "echo kylinops-ssh-ok", "purpose": "连通性探针"},
    {"command": "getent passwd root | cut -d: -f1,3,6,7", "purpose": "确认 root 账户存在"},
]


def run(**kwargs):
    host = (kwargs.get("host") or kwargs.get("target_host") or "").strip()
    port = int(kwargs.get("port") or 22)
    ssh_user = (kwargs.get("ssh_user") or kwargs.get("username") or "root").strip()

    route_online = {
        "condition": "SSH 可达且为 root 或具备 sudo passwd 权限的运维账号",
        "next_tools": [
            "get_user_account_info",
            "check_account_lock_status",
            "get_password_policy",
            "reset_user_password",
            "verify_account_after_reset",
        ],
    }
    route_offline = {
        "condition": "SSH 不可达或仅有目标用户自身凭证且已遗忘",
        "next_tools": ["check_console_access_available", "get_password_recovery_playbook"],
    }

    return {
        "success": True,
        "data": {
            "tool": NAME,
            "execution_mode": "remote_ssh",
            "target": {"host": host, "port": port, "ssh_user": ssh_user},
            "commands": REMOTE_COMMANDS,
            "agent_instruction": (
                "先确认 KylinOps 已绑定目标服务器且 SSH 连接成功；"
                "再对目标 VM 通过 execute_command 执行 commands 列表；"
                "若全部成功则走 online 流程，否则走 offline 流程。"
            ),
            "decision_rules": {
                "ssh_ok": route_online,
                "ssh_fail": route_offline,
            },
            "trial_simulated": {
                "ssh_reachable": True,
                "logged_in_as": ssh_user,
                "recommended_route": "online",
            },
            "summary": f"已生成 SSH 连通性检查方案（目标 {host or '已选服务器'}:{port}，账号 {ssh_user}）",
        },
    }
