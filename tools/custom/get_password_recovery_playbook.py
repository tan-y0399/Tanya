"""
KylinOps 自定义工具：get_password_recovery_playbook
按系统类型生成麒麟虚拟机「忘记密码」离线恢复操作手册。

知识库来源：
  - 6.1 用户密码忘记/无法登录（SEC-001）
  - 常见-登录问题 / 忘记用户密码
"""
NAME = "get_password_recovery_playbook"
DESCRIPTION = (
    "当用户忘记麒麟虚拟机登录密码且无法 SSH 在线改密时，"
    "按系统类型（桌面/服务器）与恢复方式（GRUB 单用户、救援模式、LiveCD）"
    "生成分步操作手册，供用户在虚拟机控制台手动执行。"
)
CATEGORY = "system_operation"
RISK_LEVEL = 1

TRIAL_ARGS = {
    "username": "kylin",
    "system_type": "desktop",
    "recovery_mode": "auto",
}

PLAYBOOK_TEMPLATES = {
    "grub_single": {
        "title": "方式一：GRUB 单用户模式重置密码",
        "kb_ref": ["SEC-001", "FAQ-忘记用户密码-方式①"],
        "prerequisites": [
            "需要虚拟机控制台访问权限（VMware/VirtualBox/物理显示器）",
            "目标系统可正常进入 GRUB 引导菜单",
        ],
        "steps": [
            "重启虚拟机，在银河麒麟 Logo 出现前连按 Esc 或 Shift，进入 GRUB 引导界面",
            "选中默认启动项，按 e 进入编辑模式",
            "找到以 linux 或 linuxefi 开头的行，在行末追加：rw init=/bin/bash",
            "按 Ctrl+X 或 F10 使用当前配置启动，进入 root shell（单用户环境）",
            "执行 mount -o remount,rw / 确保根分区可写（部分版本需要）",
            "执行 passwd {username} 按提示输入新密码两次",
            "（可选）若账户被锁定：faillock --user {username} --reset 或 pam_tally2 --user {username} --reset",
            "执行 exec /sbin/init 或 reboot -f 重启系统",
            "使用新密码在登录界面验证",
        ],
        "warnings": [
            "禁止直接编辑 /etc/shadow 明文写入密码",
            "操作前确认用户名正确，避免改错账户",
            "桌面版与服务器版 GRUB 界面文字可能略有差异",
        ],
    },
    "rescue": {
        "title": "方式二：救援模式重置密码",
        "kb_ref": ["KB-启动问题-救援模式"],
        "prerequisites": [
            "需要安装光盘/U盘启动介质或云平台救援镜像",
            "知晓原系统根分区设备名（如 /dev/vda1、/dev/mapper/klas-root）",
        ],
        "steps": [
            "使用麒麟安装光盘/U盘启动虚拟机，在引导菜单选择「救援模式」或 Troubleshooting → Rescue",
            "选择「继续」以只读挂载原系统，或选择「读写挂载」",
            "执行 chroot /mnt/sysimage 进入原系统环境（不同版本路径可能为 /mnt 或 /mnt/kylin）",
            "执行 passwd {username} 修改目标用户密码",
            "（可选）检查 /etc/selinux 配置，必要时 touch /.autorelabel",
            "输入 exit 退出 chroot，重启并从硬盘启动",
            "使用新密码登录验证",
        ],
        "warnings": [
            "救援模式下误操作可能影响原系统引导，仅修改密码相关命令",
            "chroot 路径因安装方式不同可能需人工确认",
        ],
    },
    "livecd": {
        "title": "方式三：LiveCD 模式重置密码（桌面版）",
        "kb_ref": ["FAQ-忘记用户密码-方式②", "FAQ-忘记用户密码-方式③"],
        "prerequisites": [
            "适用于银河麒麟桌面版",
            "需要光盘/U盘 LiveCD 启动介质",
            "目前主要面向桌面系统场景",
        ],
        "steps": [
            "将麒麟安装光盘放入光驱（或 U 盘引导），重启进入 LiveCD 桌面/命令行环境",
            "打开终端，执行 lsblk 或 fdisk -l 确认原系统根分区挂载点",
            "挂载原系统：mount /dev/<根分区> /mnt（按实际设备名替换）",
            "（可选）chroot /mnt 进入原系统后执行 passwd {username}",
            "或在 LiveCD 下使用 passwd 配合 chroot 修改密码",
            "卸载分区 umount /mnt，退出 LiveCD 并从硬盘重启",
            "若仅需备份数据：LiveCD 模式下拷贝 /home 等重要目录后再考虑系统还原",
            "使用新密码登录验证",
        ],
        "warnings": [
            "FAQ 提示：勿随意手工改写 /etc/shadow 字段，优先使用 passwd 命令",
            "方式③可用于备份重要数据后还原系统，会覆盖现有系统",
            "LiveCD 操作前确认挂载的是目标系统分区，避免误挂载",
        ],
    },
}

SYSTEM_HINTS = {
    "desktop": {
        "label": "银河麒麟桌面版",
        "recommended_modes": ["grub_single", "livecd", "rescue"],
        "notes": "桌面版优先尝试 GRUB 单用户；无法进入 GRUB 时使用 LiveCD。",
    },
    "server": {
        "label": "银河麒麟服务器版",
        "recommended_modes": ["grub_single", "rescue"],
        "notes": "服务器版通常无图形 LiveCD 桌面，推荐 GRUB 单用户或安装介质救援模式。",
    },
    "kylin_v11": {
        "label": "麒麟 V11 / KylinOS V11",
        "recommended_modes": ["grub_single", "rescue", "livecd"],
        "notes": "V11 可参考知识库 SEC-001：linux 行末加 rw init=/bin/bash 进入单用户。",
    },
    "auto": {
        "label": "自动识别（默认桌面版流程）",
        "recommended_modes": ["grub_single", "rescue", "livecd"],
        "notes": "Agent 应根据 get_system_info 结果细化 system_type 后再次调用本工具。",
    },
}


def _normalize_mode(mode: str) -> str:
    m = (mode or "auto").strip().lower()
    aliases = {
        "grub": "grub_single",
        "single": "grub_single",
        "single_user": "grub_single",
        "rescue_mode": "rescue",
        "live": "livecd",
        "live_cd": "livecd",
    }
    return aliases.get(m, m)


def _normalize_system_type(st: str) -> str:
    s = (st or "auto").strip().lower()
    if s in SYSTEM_HINTS:
        return s
    if "server" in s or "服务器" in s:
        return "server"
    if "desktop" in s or "桌面" in s:
        return "desktop"
    if "v11" in s or "kylin" in s:
        return "kylin_v11"
    return "auto"


def _build_playbook(username: str, mode: str) -> dict:
    tpl = PLAYBOOK_TEMPLATES[mode]
    steps = [step.format(username=username) for step in tpl["steps"]]
    return {
        "mode": mode,
        "title": tpl["title"],
        "kb_ref": tpl["kb_ref"],
        "prerequisites": tpl["prerequisites"],
        "steps": steps,
        "warnings": tpl["warnings"],
        "estimated_time_min": 15 if mode == "grub_single" else 30,
    }


def run(**kwargs):
    username = (kwargs.get("username") or kwargs.get("user") or "目标用户").strip()
    system_type = _normalize_system_type(kwargs.get("system_type") or kwargs.get("os_type"))
    recovery_mode = _normalize_mode(kwargs.get("recovery_mode") or kwargs.get("mode") or "auto")

    if not username:
        return {"success": False, "error": "请提供 username 参数（需重置密码的用户名）"}

    sys_hint = SYSTEM_HINTS.get(system_type, SYSTEM_HINTS["auto"])

    if recovery_mode == "auto":
        modes = sys_hint["recommended_modes"]
    elif recovery_mode in PLAYBOOK_TEMPLATES:
        modes = [recovery_mode]
    else:
        return {
            "success": False,
            "error": f"不支持的 recovery_mode: {recovery_mode}，可选: grub_single, rescue, livecd, auto",
        }

    playbooks = [_build_playbook(username, m) for m in modes]

    summary = (
        f"已为用户「{username}」生成 {len(playbooks)} 套离线密码恢复手册"
        f"（{sys_hint['label']}）。"
        f"请在虚拟机控制台按步骤操作，Agent 无法远程代替完成 GRUB/LiveCD 交互。"
    )

    return {
        "success": True,
        "data": {
            "tool": NAME,
            "username": username,
            "system_type": system_type,
            "system_label": sys_hint["label"],
            "system_notes": sys_hint["notes"],
            "recovery_mode_requested": recovery_mode,
            "playbooks": playbooks,
            "agent_next_actions": [
                "确认用户是否拥有虚拟机控制台（VNC/VMware 窗口）",
                "若 SSH 仍可用且为其他管理员账号，优先建议在线改密而非离线流程",
                "逐步引导用户执行手册，每步完成后请求反馈",
            ],
            "summary": summary,
        },
    }
