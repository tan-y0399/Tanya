"""KylinOps 工具：get_password_policy — 读取系统密码复杂度策略"""
NAME = "get_password_policy"
DESCRIPTION = (
    "生成读取 pwquality.conf、login.defs 及用户 chage 信息的命令，"
    "用于重置密码时生成符合策略的临时密码并提示用户规则。"
)
CATEGORY = "system_operation"
RISK_LEVEL = 1

TRIAL_ARGS = {"username": "kylin"}

REMOTE_COMMANDS = [
    {"command": "cat /etc/security/pwquality.conf 2>/dev/null | grep -v '^#' | grep -v '^$' || echo 'no-pwquality'", "purpose": "密码复杂度（长度、字符类、字典检查）"},
    {"command": "grep -E '^PASS_(MAX|MIN|WARN)_DAYS' /etc/login.defs 2>/dev/null || echo 'no-login-defs'", "purpose": "密码有效期策略"},
    {"command": "grep -E '^ENCRYPT_METHOD' /etc/login.defs 2>/dev/null || echo 'ENCRYPT_METHOD-SHA512'", "purpose": "加密算法"},
]

DEFAULT_POLICY = {
    "minlen": 8,
    "minclass": 3,
    "hints": [
        "建议临时密码 ≥8 位，含大小写字母、数字、特殊字符中的至少 3 类",
        "重置后提示用户首次登录立即修改",
        "禁止使用与用户名相同或连续键盘序列",
    ],
}


def run(**kwargs):
    username = (kwargs.get("username") or kwargs.get("user") or "").strip()
    cmds = list(REMOTE_COMMANDS)
    if username:
        u = username.replace("'", "")
        cmds.append({
            "command": f"chage -l {u} 2>/dev/null || echo 'chage-not-available'",
            "purpose": f"用户 {username} 的密码过期信息",
        })

    return {
        "success": True,
        "data": {
            "tool": NAME,
            "execution_mode": "remote_ssh",
            "username": username or None,
            "commands": cmds,
            "default_policy": DEFAULT_POLICY,
            "temp_password_template": "Kylin@{uid_last4}!{rand2}",
            "agent_instruction": (
                "执行 commands 解析 minlen/minclass 等；"
                "生成临时密码时遵守策略并仅通过安全渠道一次性交付用户"
            ),
            "trial_simulated": {
                "minlen": 8,
                "minclass": 3,
                "encrypt_method": "SHA512",
            },
            "summary": "已生成密码策略读取命令与临时密码生成建议",
        },
    }
