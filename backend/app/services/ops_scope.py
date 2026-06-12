"""
运维领域边界 — 判断问题是否属于 KylinOps 可回答范围，以及是否为「知识问答」而非「实时查数」。
"""
from __future__ import annotations

import re
from typing import Tuple

# 明显非运维话题（优先拦截）
NON_OPS_TOPICS = (
    "做菜", "菜谱", "烹饪", "美食推荐", "红烧肉", "做饭", "食材",
    "股票", "基金", "炒股", "理财",
    "医疗", "看病", "药物", "处方",
    "法律", "律师", "起诉",
    "旅游攻略", "景点推荐", "酒店预订",
    "游戏攻略", "手游", "网游",
    "写作文", "小说", "诗歌",
    "谈恋爱", "情感咨询",
    "天气怎么样", "今天天气",
    "明星", "娱乐八卦",
    "数学题", "物理题", "化学题",
    "翻译这段", "翻译成英文",
)

# 运维领域词（命中则视为本系统职责范围内）
OPS_DOMAIN_KEYWORDS = (
    "服务器", "主机", "linux", "unix", "系统", "运维", "运维管理",
    "nginx", "apache", "tomcat", "mysql", "redis", "postgresql", "docker", "k8s", "kubernetes",
    "内存", "磁盘", "cpu", "进程", "服务", "日志", "网络", "端口", "防火墙", "iptables",
    "ssh", "systemd", "journal", "挂载", "分区", "nfs", "磁盘满", "负载",
    "麒麟", "kylin", "v11", "内核", "root", "sudo", "chmod", "chown",
    "备份", "恢复", "监控", "告警", "巡检", "故障", "异常", "宕机",
    "swap", "pagecache", "drop_caches", "free", "top", "df", "ss", "netstat", "ping",
    "rm", "chmod", "chown", "iptables", "systemctl", "kill", "命令", "风险",
    "usb", "umount", "unmount", "mount", "卸载", "挂载", "存储", "fuser", "sync",
)

# 存储/挂载类运维（USB、NFS、device busy 等）
STORAGE_MOUNT_MARKERS = (
    "usb", "umount", "unmount", "mount", "卸载", "挂载", "存储设备", "存储",
    "device is busy", "device busy", "fuser", "/dev/sd", "dev/sd",
)

# 知识库常见排障/安装/激活/软件主题（覆盖 deploy/sql/knowledge_articles.sql 条目）
OPS_TROUBLESHOOTING_MARKERS = (
    "dns", "解析", "解析失败", "网卡", "驱动", "驱动不兼容", "板载", "网络",
    "登录", "无法登录", "闪退", "密码", "忘记", "图形界面", "logo", "界面",
    "busybox", "断电", "非法断电", "启动", "开机", "无法启动", "内核", "引导",
    "权限", "无法访问", "配置文件", "配置漂移", "漂移", "文件系统",
    "飞腾", "龙芯", "国产化", "兼容性", "兼容", "平台",
    "安装", "安装界面", "光盘", "光驱", "镜像", "u盘", "启动盘", "格式化",
    "激活", "授权", "试用", "版本", "绑定", "二维码", "ukey", "过期", "错误代码",
    "软件", "deb", "rpm", "apt", "软件源", "应用商店", "apk", "微信", "wps", "office",
    "浏览器", "第三方", "重装", "更新", "下载", "post-installation", "软件包",
    "kysec", "桌面", "管理员", "替换授权", "永中",
    "失败", "无法", "报错", "异常", "问题", "故障", "排查", "怎么办", "怎么处理",
    "设备", "busy", "nfs", "挂载点", "卡死", "卡住", "空间满", "空间不足",
    "服务", "systemd", "ssh", "rsyslog", "docker", "journal",
    "屏保", "锁屏", "任务栏", "开始菜单", "状态栏", "桌面", "回收站", "显示",
    "输入法", "搜狗", "五笔", "拼音", "乱码", "键盘", "输入",
    "wifi", "wi-fi", "mac地址", "mac ", "以太网", "内网", "网线", "上不了网", "连接",
    "手册", "flash", "qt5", "designer", "firefox", "java", "applet", "xmanager",
    "编译", "ltp", "打印机", "外设", "打印", "驱动",
    "时间不同步", "不同步", "ntp", "对时",
)

# 知识库结构化标题：如「1.1 根目录空间满…」「3.4 DNS解析失败」
KB_STRUCTURED_TITLE_RE = re.compile(r"^\d+\.\d+\s+\S")

# 知识/方法类问法（倾向知识库回答，不查实时）
PROCEDURAL_MARKERS = (
    "如何", "怎么", "怎样", "怎么办", "如何做", "怎么做", "该怎么",
    "步骤", "方法", "教程", "指南", "手册", "规范", "最佳实践",
    "是什么", "什么是", "介绍", "原理", "概念", "区别",
    "建议", "方案", "注意事项", "有哪些", "列举",
    "操作指南", "配置方法", "清理方法", "优化方法",
)

# 服务/进程写操作（关闭、重启等）— 必须走 ReAct + 审批/确认，禁止 general_qa 无工具作答
SERVICE_CONTROL_VERBS = (
    "关闭", "停止", "停用", "停掉", "关掉", "shutdown", "stop",
    "开启", "启动", "start", "重启", "restart", "reload", "重新加载",
)
SERVICE_CONTROL_CONTINUATION = (
    "继续关闭", "继续停止", "继续执行", "接着关闭", "接着停", "现在关闭", "现在停止",
    "执行关闭", "执行停止", "帮我关", "帮我停",
)

# 时间同步 / NTP / chrony
TIME_SYNC_MARKERS = (
    "时间同步", "时钟同步", "ntp", "chrony", "timedatectl", "对时", "校时",
    "时间一致", "与主机时间", "和主机时间", "同步时间", "同步与主机", "与宿主机时间",
    "宿主机时间", "主机时间同步", "系统时间同步", "继续同步", "与主机继续",
)
TIME_SYNC_CONTEXT = ("时间", "时钟", "ntp", "chrony", "时区", "日期")
TIME_SYNC_VERBS = ("同步", "对时", "校时", "一致", "对齐", "校准", "同步与")
TIME_SYNC_EXEC_HELP = (
    "帮我", "执行", "将该", "把该", "把这", "让该", "使该", "进行", "立即", "现在",
)

# 磁盘/系统清理执行（非「如何清理」知识问答）
CLEANUP_EXECUTION_MARKERS = (
    "清理垃圾", "无用垃圾", "垃圾文件", "系统垃圾", "清理该系统",
    "释放磁盘", "释放空间", "腾出空间",
    "帮我清理", "开始清理", "执行清理", "清理一下",
    "清一下", "清掉", "删掉临时", "删除临时", "清空临时", "清理临时",
    "清理缓存", "清理日志", "清理 apt", "清理软件包",
)
CLEANUP_EXECUTION_HELP = (
    "帮我", "开始", "执行", "现在", "马上", "请", "直接", "立刻",
)

# LLM 在无工具路径下谎称已执行的特征
FAKE_EXECUTION_PHRASES = (
    "已清理", "已完成", "已执行", "已清空", "已移除", "已成功",
    "开始清理\n", "sudo apt-get clean", "journalctl --vacuum",
    "rm -rf /tmp", "rm -rf ~/.cache",
)

# 实时查数/巡检类（倾向工具）
LIVE_QUERY_MARKERS = (
    "查看", "检查", "查询", "显示", "列出", "获取", "看看", "看下", "查一下",
    "我来查", "帮我查", "帮我看", "看一下",
    "当前", "现在", "实时", "目前", "此刻",
    "多少", "占用", "使用情况", "是否正常", "状态如何", "有没有",
    "show", "check", "list", "get", "status",
)

# 用户明确要查本机（即使带「如何」也走运维查询的例外）
LIVE_OVERRIDE = (
    "我这台", "本机", "这台服务器", "当前系统", "现在系统",
    "帮我看", "帮我查", "看一下", "查一下",
)


def _has_any(text: str, phrases: tuple) -> bool:
    t = text.lower()
    return any(p.lower() in t for p in phrases)


def is_procedural_knowledge_question(text: str) -> bool:
    """
    是否为「怎么做/是什么」类运维知识问题（应用 RAG+文本回答，不调用 SSH 工具）。
    例：如何进行内存清理、nginx 怎么配置反向代理
    """
    if not text or not text.strip():
        return False
    if _has_any(text, LIVE_OVERRIDE):
        return False
    has_proc = _has_any(text, PROCEDURAL_MARKERS)
    has_live = _has_any(text, LIVE_QUERY_MARKERS)
    if not has_proc:
        return False
    # 「如何查看内存」= 实时查询
    if has_live and re.search(r"(查看|检查|查询|显示|列出|获取|看看|查)", text):
        return False
    return True


def is_live_ops_query(text: str) -> bool:
    """是否为查看当前系统状态的实时运维查询。"""
    if not text:
        return False
    if is_service_control_request(text):
        return False
    if is_procedural_knowledge_question(text):
        return False
    return _has_any(text, LIVE_QUERY_MARKERS)


def is_service_control_request(text: str) -> bool:
    """
    是否要求对服务/进程执行写操作（关闭、启动、重启等）。
    此类请求必须走 ReAct 工具链（含 L4 审批与用户确认执行），不得走 general_qa。
    """
    if not text or not text.strip():
        return False
    t = text.strip().lower()
    if _has_any(text, SERVICE_CONTROL_CONTINUATION):
        return True
    if not _has_any(text, SERVICE_CONTROL_VERBS):
        return False
    # 带服务名或通用「服务」语境
    if _has_any(text, OPS_DOMAIN_KEYWORDS):
        return True
    if re.search(r"(nginx|mysql|redis|sshd|docker|httpd|tomcat|服务)", t, re.I):
        return True
    return _has_any(text, ("服务", "进程"))


def is_time_sync_request(text: str) -> bool:
    """是否涉及系统时间与 NTP/宿主机时钟同步。"""
    if not text or not text.strip():
        return False
    t = text.strip()
    tl = t.lower()
    if _has_any(t, TIME_SYNC_MARKERS):
        return True
    if _has_any(t, TIME_SYNC_CONTEXT) and _has_any(t, TIME_SYNC_VERBS):
        return True
    if re.search(r"时间.{0,8}(同步|一致|对齐|校准)", t):
        return True
    if re.search(r"(同步|对齐|校准).{0,8}(主机|宿主机|hypervisor|宿主机时间)", tl):
        return True
    return False


def is_time_sync_execution_request(text: str) -> bool:
    """
    是否要求在本机**执行**时间同步（非纯知识问答）。
    例：「将该虚拟机时间与主机同步」→ 必须走工具链。
    反例：「如何配置 NTP 时间同步」→ 知识问答。
    """
    if not is_time_sync_request(text):
        return False
    t = text.strip()
    if re.search(r"^(如何|怎么|怎样|什么是)", t):
        return False
    if re.search(r"(如何|怎么|怎样).{0,16}(配置|设置|同步|对时)", t) and not _has_any(t, TIME_SYNC_EXEC_HELP):
        return False
    return True


def is_disk_cleanup_execution_request(text: str) -> bool:
    """
    是否要求在本机**执行**磁盘/垃圾清理（非纯知识问答）。
    例：「清理垃圾释放空间」「帮我清理无用文件」→ 必须走 ReAct + execute_command + 确认/审批。
    反例：「如何进行内存清理」「磁盘满了怎么排查」→ 知识/查询，不走本函数。
    """
    if not text or not text.strip():
        return False
    t = text.strip()
    if is_procedural_knowledge_question(t) and not _has_any(t, CLEANUP_EXECUTION_MARKERS):
        return False
    if re.search(r"(如何|怎么|怎样|排查|诊断|分析)", t) and not _has_any(t, CLEANUP_EXECUTION_HELP):
        if not re.search(r"清理\s*(垃圾|无用|临时|缓存)", t, re.I):
            return False
    if _has_any(t, CLEANUP_EXECUTION_MARKERS):
        return True
    if re.search(r"清理\s*(垃圾|无用|临时|缓存|日志|文件)", t, re.I):
        if not re.search(r"(如何|怎么|怎样|步骤|方法|教程|原理)", t):
            return True
    if re.search(r"清理.{0,8}(垃圾|无用文件|临时文件)", t, re.I):
        if not re.search(r"(如何|怎么|怎样|步骤|方法|教程|原理)", t):
            return True
    if re.search(r"(释放|腾出)\s*(磁盘|空间)", t):
        return True
    if ("磁盘满了" in t or "空间不足" in t) and _has_any(t, CLEANUP_EXECUTION_HELP + ("清理", "删除", "清掉")):
        return True
    if _has_any(t, ("清理", "垃圾", "释放空间", "磁盘空间", "无用文件")) and _has_any(t, CLEANUP_EXECUTION_HELP):
        return True
    return False


def parse_service_control_target(text: str) -> tuple:
    """解析服务控制诉求 → (action, service_name)。action: stop|start|restart"""
    t = (text or "").strip().lower()
    action = "stop"
    if _has_any(text, ("启动", "开启", "start", "enable")):
        action = "start"
    elif _has_any(text, ("重启", "restart", "reload")):
        action = "restart"
    svc = "nginx"
    m = re.search(
        r"\b(nginx|mysql|mariadb|redis|sshd|docker|httpd|tomcat|postgresql|postfix|"
        r"memcached|rabbitmq|kubelet|containerd|firewalld|networkmanager)\b",
        t, re.I,
    )
    if m:
        svc = m.group(1).lower()
    return action, svc


def response_claims_fake_execution(text: str) -> bool:
    """无工具调用时，回答是否谎称已执行命令/已完成清理。"""
    if not text or len(text) < 20:
        return False
    hits = sum(1 for p in FAKE_EXECUTION_PHRASES if p in text)
    if hits >= 2:
        return True
    if hits >= 1 and any(k in text for k in ("apt-get", "journalctl", "rm -rf", "sudo ")):
        return True
    return False


def build_out_of_scope_refusal() -> str:
    """域外问题标准礼貌拒绝文案（general_qa / out_of_scope）。"""
    return (
        "抱歉，我是 **KylinOps 智能运维助手**，仅支持 Linux/麒麟服务器与系统运维相关问题。\n\n"
        "您当前的问题与运维无关，我无法提供该领域的解答。\n\n"
        "**您可以尝试这样提问：**\n"
        "- 如何进行内存清理\n"
        "- nginx 反向代理如何配置\n"
        "- 如何排查磁盘空间不足\n"
        "- 查看当前 CPU / 内存使用情况"
    )


def react_execution_redirect_message(text: str) -> str:
    """引导用户走工具链 + 安全确认/审批，禁止无工具幻觉作答。"""
    if is_service_control_request(text):
        return (
            "检测到您要**关闭/启停服务**，此类操作需通过运维工具执行并经过审批。\n\n"
            "请重新发送明确指令，例如：「关闭 nginx 服务」。"
            "系统将走 L4 审批流程，管理员批准后在对话页点击「执行」才会真正运行命令。"
        )
    if is_time_sync_execution_request(text):
        return (
            "检测到您要**配置/执行时间同步**，此类操作需通过 SSH 工具在虚拟机执行：\n\n"
            "- **L1 只读**：`timedatectl status`、`chronyc tracking` 查看当前偏差\n"
            "- **L3 写操作**：`chronyc makestep` 或 `timedatectl set-ntp true` 需您确认后执行\n\n"
            "正在为您转入 **ReAct 运维执行链路**…"
        )
    if is_disk_cleanup_execution_request(text):
        return (
            "检测到您要**在本机执行磁盘/垃圾清理**，此类写操作不能仅在对话中说明步骤，"
            "必须通过 SSH 工具逐条执行，并经过安全校验：\n\n"
            "- **L2 低风险**（如 `apt-get clean`）：对话页弹出确认框，您点击「执行」后才会运行\n"
            "- **L3 中风险**（如 `journalctl --vacuum-time`）：需确认并记录审计\n"
            "- **L4 高风险**（如 `rm -rf /tmp/*`）：需管理员审批，批准后再由您确认执行\n"
            "- **L5 禁止**（如 `rm -rf /`）：直接拦截\n\n"
            "正在为您转入 **ReAct 运维执行链路**…"
        )
    return ""


def requires_react_tools(text: str, intent_result: dict | None = None) -> bool:
    """是否必须使用工具执行（不可走无工具 Handler）。"""
    if is_service_control_request(text):
        return True
    if is_disk_cleanup_execution_request(text):
        return True
    if is_time_sync_execution_request(text):
        return True
    if intent_result and intent_result.get("intent") in (
        "ops_query", "fault_analysis", "high_risk",
    ):
        return True
    return False


def assess_ops_scope(text: str) -> Tuple[str, str]:
    """
    评估问题是否在运维范围内。
    返回 (scope, reason): scope in ('in_scope', 'out_of_scope', 'uncertain')
    """
    if not text or not text.strip():
        return "uncertain", "empty"

    t = text.strip()

    for topic in NON_OPS_TOPICS:
        if topic in t:
            return "out_of_scope", f"非运维话题:{topic}"

    if KB_STRUCTURED_TITLE_RE.match(t):
        return "in_scope", "结构化运维知识条目"

    if _has_any(t, STORAGE_MOUNT_MARKERS):
        return "in_scope", "存储/挂载运维"

    if _has_any(t, OPS_TROUBLESHOOTING_MARKERS):
        return "in_scope", "运维排障/系统支持"

    if _has_any(t, OPS_DOMAIN_KEYWORDS):
        return "in_scope", "运维领域词"

    # 有「怎么做」但无任何运维/排障特征 → 域外
    if _has_any(t, PROCEDURAL_MARKERS) and not _has_any(t, OPS_DOMAIN_KEYWORDS):
        if not _has_any(t, OPS_TROUBLESHOOTING_MARKERS):
            return "out_of_scope", "方法类问题但无运维主题"

    if is_disk_cleanup_execution_request(t):
        return "in_scope", "磁盘清理执行"

    if is_time_sync_request(t):
        return "in_scope", "时间同步"

    if is_service_control_request(t):
        return "in_scope", "服务控制操作"

    if is_procedural_knowledge_question(t):
        return "in_scope", "运维方法类问法"

    if is_live_ops_query(t):
        return "in_scope", "运维查询类问法"

    # 短问候
    if len(t) <= 12 and _has_any(t, ("你好", "您好", "hi", "hello", "谢谢", "再见", "帮助", "help")):
        return "in_scope", "问候"

    # 较长文本仍无任何运维/排障特征时才判域外（避免误伤知识库短标题）
    if len(t) >= 40:
        if not (
            _has_any(t, OPS_DOMAIN_KEYWORDS)
            or _has_any(t, OPS_TROUBLESHOOTING_MARKERS)
            or _has_any(t, PROCEDURAL_MARKERS)
        ):
            return "out_of_scope", "未识别运维相关主题"

    # 常见运维/support 问句（知识库条目多为此类）
    if len(t) >= 4 and (
        re.search(r"[?？]", t)
        or _has_any(t, ("怎么", "如何", "为什么", "能否", "能不能", "是否", "哪里", "在哪"))
    ):
        return "in_scope", "运维支持问句"

    if len(t) >= 4:
        return "in_scope", "麒麟系统支持类"

    return "uncertain", "过短"
