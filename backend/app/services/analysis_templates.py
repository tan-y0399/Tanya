"""
多步分析模板 — 场景化故障诊断流程

每个模板定义一个分析流程: 感知 → 诊断 → 建议
模板引擎自动匹配用户问题到最佳模板，生成推荐操作序列
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class AnalysisStep:
    tool_name: str
    description: str
    purpose: str  # "perceive" | "diagnose" | "remediate"
    optional: bool = False


@dataclass
class AnalysisTemplate:
    name: str
    label: str
    description: str
    fault_patterns: List[str] = field(default_factory=list)
    steps: List[AnalysisStep] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


ANALYSIS_TEMPLATES: Dict[str, AnalysisTemplate] = {
    "high_cpu": AnalysisTemplate(
        name="high_cpu",
        label="CPU 使用率异常分析",
        description="诊断 CPU 使用率过高问题",
        fault_patterns=["cpu高", "CPU高", "cpu 高", "CPU使用率", "cpu使用率",
                        "负载高", "load average", "load高", "cpu飙", "CPU飙"],
        steps=[
            AnalysisStep("get_cpu_info", "获取CPU使用率和负载", "perceive"),
            AnalysisStep("list_processes", "列出CPU占用最高的进程", "perceive"),
            AnalysisStep("get_process_detail", "查看高CPU进程详情", "diagnose"),
            AnalysisStep("search_journal_logs", "查看系统日志中的相关错误", "diagnose"),
        ],
        recommendations=[
            "调整高负载进程的 nice 值: renice +10 <PID>",
            "检查是否有定时任务集中执行 (crontab -l)",
            "考虑使用 cgroups 限制进程资源",
            "如为Java应用，检查GC日志优化JVM参数",
        ],
    ),
    "high_memory": AnalysisTemplate(
        name="high_memory",
        label="内存使用率异常分析",
        description="诊断内存使用率过高/OOM问题",
        fault_patterns=["内存高", "memory high", "内存满", "OOM", "oom",
                        "内存不足", "内存泄漏", "memory leak"],
        steps=[
            AnalysisStep("get_memory_info", "获取内存和Swap使用情况", "perceive"),
            AnalysisStep("list_processes", "列出内存占用最高的进程", "perceive"),
            AnalysisStep("get_process_detail", "查看高内存进程详情", "diagnose"),
            AnalysisStep("search_journal_logs", "查看OOM Killer日志", "diagnose"),
        ],
        recommendations=[
            "检查 dmesg 中的 OOM Killer 记录",
            "使用 pmap -x <PID> 分析进程内存映射",
            "Java应用: 分析heap dump，调整-Xmx参数",
            "检查 /proc/sys/vm/swappiness 配置",
        ],
    ),
    "disk_full": AnalysisTemplate(
        name="disk_full",
        label="磁盘空间满分析",
        description="诊断磁盘空间不足问题",
        fault_patterns=["磁盘满", "磁盘空间不足", "disk full", "空间满", "磁盘不足",
                        "no space", "disk usage 100"],
        steps=[
            AnalysisStep("get_disk_info", "获取磁盘使用率", "perceive"),
            AnalysisStep("get_file_list", "查看大文件目录 /var/log", "perceive"),
            AnalysisStep("search_journal_logs", "检查磁盘相关错误", "diagnose"),
        ],
        recommendations=[
            "清理旧日志: truncate -s 0 /var/log/syslog",
            "卸载冗余软件包: yum autoremove",
            "清理旧内核: package-cleanup --oldkernels --count=2",
            "配置 logrotate 日志轮转策略",
        ],
    ),
    "service_down": AnalysisTemplate(
        name="service_down",
        label="服务异常诊断",
        description="诊断服务宕机或异常",
        fault_patterns=["服务挂了", "服务宕", "服务异常", "nginx停了", "mysql停了",
                        "服务未运行", "服务无响应", "service down", "服务无法启动"],
        steps=[
            AnalysisStep("get_service_status", "检查服务运行状态", "perceive"),
            AnalysisStep("search_journal_logs", "查看服务日志中的错误", "diagnose"),
            AnalysisStep("get_network_connections", "检查服务端口是否监听", "diagnose"),
            AnalysisStep("get_process_detail", "查看相关进程状态", "diagnose"),
        ],
        recommendations=[
            "启动服务: systemctl start <服务名>",
            "检查配置文件语法: <服务> -t",
            "检查依赖服务是否正常运行",
            "查看 /var/log/messages 中的启动错误",
        ],
    ),
    "network_issue": AnalysisTemplate(
        name="network_issue",
        label="网络异常分析",
        description="诊断网络连接问题",
        fault_patterns=["网络异常", "网络不通", "连接超时", "connection timeout",
                        "网络延迟", "丢包", "无法访问", "连不上", "端口不通"],
        steps=[
            AnalysisStep("get_network_connections", "检查网络连接和监听端口", "perceive"),
            AnalysisStep("list_processes", "检查异常网络进程", "perceive"),
            AnalysisStep("search_journal_logs", "查看网络相关日志", "diagnose"),
        ],
        recommendations=[
            "检查防火墙规则: firewall-cmd --list-all",
            "测试连通性: ping / telnet / nc",
            "检查DNS配置: cat /etc/resolv.conf",
            "检查路由表: ip route show",
        ],
    ),
    "system_health": AnalysisTemplate(
        name="system_health",
        label="系统健康巡检",
        description="全面系统健康检查",
        fault_patterns=["巡检", "健康检查", "系统状态", "全面检查", "体检",
                        "整体状态", "系统概况"],
        steps=[
            AnalysisStep("get_system_info", "系统版本和运行时间", "perceive"),
            AnalysisStep("get_cpu_info", "CPU使用率和负载", "perceive"),
            AnalysisStep("get_memory_info", "内存和Swap使用", "perceive"),
            AnalysisStep("get_disk_info", "磁盘使用率", "perceive"),
            AnalysisStep("get_network_connections", "网络连接状态", "perceive"),
            AnalysisStep("get_service_status", "关键服务状态", "perceive"),
        ],
        recommendations=[
            "CPU >80%: 检查高负载进程",
            "内存 >85%: 检查内存泄漏",
            "磁盘 >80%: 执行清理",
            "服务异常: 查看对应日志排查",
        ],
    ),
    "login_issue": AnalysisTemplate(
        name="login_issue",
        label="登录异常分析",
        description="诊断SSH/图形登录失败",
        fault_patterns=["登录失败", "无法登录", "ssh连不上", "密码错误",
                        "登录闪退", "认证失败", "login failed", "permission denied"],
        steps=[
            AnalysisStep("get_service_status", "检查sshd服务状态", "perceive"),
            AnalysisStep("search_journal_logs", "查看认证日志", "diagnose"),
            AnalysisStep("get_network_connections", "检查22端口监听", "perceive"),
            AnalysisStep("get_disk_info", "检查磁盘是否满", "perceive"),
        ],
        recommendations=[
            "启动sshd: systemctl start sshd",
            "检查 /etc/ssh/sshd_config 配置",
            "检查PAM配置: cat /etc/pam.d/sshd",
            "检查 /var/log/auth.log 中的认证失败原因",
            "磁盘满可能导致无法创建会话文件",
        ],
    ),
    "boot_issue": AnalysisTemplate(
        name="boot_issue",
        label="启动异常分析",
        description="诊断系统启动失败/卡顿",
        fault_patterns=["启动失败", "开机卡住", "无法启动", "busybox",
                        "logo界面", "boot failed", "启动报错"],
        steps=[
            AnalysisStep("get_system_info", "查看启动时间和内核信息", "perceive"),
            AnalysisStep("search_journal_logs", "查看上次启动日志", "diagnose"),
            AnalysisStep("get_disk_info", "检查分区挂载状态", "diagnose"),
        ],
        recommendations=[
            "进入救援模式执行 fsck 修复文件系统",
            "检查 /etc/fstab 挂载配置是否正确",
            "查看 dmesg 中的内核启动错误",
            "禁用问题服务: systemctl disable <服务名>",
        ],
    ),
}


class AnalysisEngine:
    def match_template(self, user_input: str) -> Optional[AnalysisTemplate]:
        input_lower = user_input.lower()
        best_match = None
        best_score = 0
        for template in ANALYSIS_TEMPLATES.values():
            score = sum(1 for p in template.fault_patterns if p.lower() in input_lower)
            if score > best_score:
                best_score = score
                best_match = template
        return best_match if best_score > 0 else None

    def get_steps(self, template_name: str) -> List[dict]:
        template = ANALYSIS_TEMPLATES.get(template_name)
        if not template:
            return []
        return [
            {"tool": s.tool_name, "description": s.description,
             "purpose": s.purpose, "optional": s.optional}
            for s in template.steps
        ]

    def get_recommendations(self, template_name: str) -> List[str]:
        template = ANALYSIS_TEMPLATES.get(template_name)
        return template.recommendations if template else []

    def get_all_templates(self) -> List[dict]:
        return [
            {"name": t.name, "label": t.label, "description": t.description,
             "steps": self.get_steps(t.name),
             "recommendations": t.recommendations,
             "faultPatterns": t.fault_patterns}
            for t in ANALYSIS_TEMPLATES.values()
        ]

    def build_diagnostic_prompt(self, user_input: str) -> str:
        """构建诊断提示词，引导LLM按模板流程分析"""
        template = self.match_template(user_input)
        if not template:
            return ""

        steps_text = "\n".join(
            f"  {i+1}. [{s.purpose}] {s.description} (工具: {s.tool_name})"
            for i, s in enumerate(template.steps)
        )
        recs_text = "\n".join(f"  - {r}" for r in template.recommendations)

        return (
            f"\n## 诊断计划: {template.label}\n\n"
            f"### 分析步骤\n{steps_text}\n\n"
            f"### 修复建议\n{recs_text}\n\n"
            f"请按以上步骤执行诊断，每步完成后分析结果再决定下一步。"
        )


analysis_engine = AnalysisEngine()
