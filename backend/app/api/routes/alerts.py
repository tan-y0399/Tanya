"""告警管理 API"""
from datetime import datetime, timedelta
from fastapi import APIRouter

router = APIRouter(prefix="/alerts", tags=["告警"])


def _mock_alerts() -> list:
    now = datetime.utcnow()
    return [
        {
            "id": "alt-001", "severity": "critical",
            "title": "nginx 服务 502 错误激增", "type": "服务异常",
            "source": "nginx 监控", "host": "kylin-server-01",
            "detail": "最近5分钟内出现 47 次 502 错误，upstream connection timed out",
            "rootCause": "PHP-FPM 进程池耗尽，pm.max_children 设置过低",
            "suggestion": "1. 增大 pm.max_children 到 50\n2. 检查慢查询\n3. 考虑增加服务器",
            "knowledgeIds": [],
            "status": "active",  # active / acknowledged / resolved
            "time": (now - timedelta(minutes=5)).isoformat(),
            "relatedMetrics": {"errorRate": 12.5, "avgResponseTime": 3200},
        },
        {
            "id": "alt-002", "severity": "warning",
            "title": "/dev/sda1 磁盘 I/O 延迟升高", "type": "性能降级",
            "source": "iostat 监控", "host": "kylin-server-01",
            "detail": "iowait 从 2% 升至 18%，磁盘 util 达到 95%",
            "rootCause": "mysqld 进程大量写入 binlog，sync_binlog=1 导致频繁同步",
            "suggestion": "1. 调整 sync_binlog=100\n2. 检查是否有大事务\n3. 考虑 SSD 扩容",
            "knowledgeIds": ["kb-001"],
            "status": "active",
            "time": (now - timedelta(minutes=35)).isoformat(),
            "relatedMetrics": {"iowait": 18.3, "diskUtil": 95},
        },
        {
            "id": "alt-003", "severity": "warning",
            "title": "内存使用率持续高于 85%", "type": "资源压力",
            "source": "内存监控", "host": "kylin-server-01",
            "detail": "java 进程占用 34.5%，系统可用内存降至 1.2G",
            "rootCause": "Java heap 配置过大 + GC 未能有效回收",
            "suggestion": "1. 分析 heap dump\n2. 调整 -Xmx 参数\n3. 排查内存泄漏",
            "knowledgeIds": ["kb-002"],
            "status": "acknowledged",
            "time": (now - timedelta(hours=2)).isoformat(),
            "relatedMetrics": {"memoryUsage": 87.2, "availableGB": 1.2},
        },
        {
            "id": "alt-004", "severity": "info",
            "title": "/var 分区使用率接近阈值", "type": "容量预警",
            "source": "磁盘监控", "host": "kylin-server-01",
            "detail": "当前使用率 78%，预计 3 天内达到 85% 阈值",
            "rootCause": "应用日志未配置轮转，/var/log 持续增长",
            "suggestion": "1. 配置 logrotate\n2. 清理30天前日志\n3. 调整日志级别",
            "knowledgeIds": [],
            "status": "active",
            "time": (now - timedelta(hours=5)).isoformat(),
            "relatedMetrics": {"diskUsage": 78, "estimatedDaysFull": 3},
        },
        {
            "id": "alt-005", "severity": "critical",
            "title": "检测到暴力 SSH 登录攻击", "type": "安全事件",
            "source": "安全审计", "host": "kylin-server-01",
            "detail": "IP 10.0.0.99 在 3 分钟内尝试 89 次 SSH 登录，用户名 root/admin",
            "rootCause": "外部攻击者进行密码爆破",
            "suggestion": "1. 已自动封禁 IP: 10.0.0.99\n2. 检查是否有账户被攻破\n3. 启用 fail2ban\n4. 禁用 root SSH 登录",
            "knowledgeIds": ["kb-003"],
            "status": "resolved",
            "time": (now - timedelta(hours=12)).isoformat(),
            "relatedMetrics": {"failedLogins": 89, "sourceIp": "10.0.0.99"},
        },
        {
            "id": "alt-006", "severity": "info",
            "title": "系统 CPU 使用率波动", "type": "性能波动",
            "source": "CPU 监控", "host": "kylin-server-01",
            "detail": "CPU 使用率在最近1小时内出现周期性峰值，从 25% 到 78%",
            "rootCause": "定时任务 crontab 每小时执行数据备份",
            "suggestion": "1. 确认备份任务必要\n2. 调整备份时间到低峰期\n3. 使用 ionice 限制 I/O 优先级",
            "knowledgeIds": [],
            "status": "acknowledged",
            "time": (now - timedelta(hours=1)).isoformat(),
            "relatedMetrics": {"cpuPeak": 78, "cpuAvg": 35},
        },
    ]


@router.get("/list")
async def list_alerts(severity: str = "", status: str = ""):
    """获取告警列表"""
    alerts = _mock_alerts()
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]
    if status:
        alerts = [a for a in alerts if a["status"] == status]
    return {"code": 0, "data": {"items": alerts, "total": len(alerts)}}


@router.get("/stats")
async def alert_stats():
    """告警统计"""
    alerts = _mock_alerts()
    stats = {
        "total": len(alerts),
        "active": sum(1 for a in alerts if a["status"] == "active"),
        "acknowledged": sum(1 for a in alerts if a["status"] == "acknowledged"),
        "resolved": sum(1 for a in alerts if a["status"] == "resolved"),
        "critical": sum(1 for a in alerts if a["severity"] == "critical"),
        "warning": sum(1 for a in alerts if a["severity"] == "warning"),
        "info": sum(1 for a in alerts if a["severity"] == "info"),
    }
    return {"code": 0, "data": stats}
