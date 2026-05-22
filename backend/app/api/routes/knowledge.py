"""知识库管理 API"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.core.database import get_db
from app.models.knowledge import KnowledgeArticle

router = APIRouter(prefix="/knowledge", tags=["知识库"])

PRESET_KNOWLEDGE = [
    {"title": "磁盘 I/O 高排查指南", "category": "故障排查",
     "tags": "磁盘,I/O,mysqld,性能", "severity": "warning",
     "content": """## 磁盘 I/O 高排查步骤

1. 使用 `iostat -x 1` 查看磁盘 I/O 使用率
2. 使用 `iotop` 定位高 I/O 进程
3. 检查 MySQL 慢查询日志
4. 检查 binlog 配置（`sync_binlog` 参数）
5. 考虑调整 InnoDB buffer pool 大小

**常见根因**：
- mysqld 大量写入 binlog
- 日志文件未及时轮转
- SSD 寿命接近极限"""},
    {"title": "内存泄漏排查方法", "category": "故障排查",
     "tags": "内存,OOM,java,进程", "severity": "critical",
     "content": """## 内存泄漏排查

1. `free -h` 查看整体内存使用
2. `top -o %MEM` 按内存排序进程
3. `pmap -x <PID>` 查看进程内存映射
4. 检查 `/proc/<PID>/smaps` 分析内存区域

**Java 应用特别关注**：
- GC 日志分析
- Heap dump 对比
- JVM 参数调优"""},
    {"title": "麒麟操作系统安全基线配置", "category": "安全策略",
     "tags": "安全,基线,配置,合规", "severity": "info",
     "content": """## 麒麟 V11 安全基线

### 账户安全
- 禁用 root SSH 登录
- 设置密码复杂度策略
- 定期审计用户账户

### 文件权限
- /etc/passwd: 644
- /etc/shadow: 000
- /etc/gshadow: 000

### 审计策略
- 启用 auditd 服务
- 配置关键文件变更监控
- 设置审计日志轮转"""},
    {"title": "nginx 502 错误排查案例", "category": "案例库",
     "tags": "nginx,502,upstream,超时", "severity": "warning",
     "content": """## 案例：nginx 大量 502 错误

**现象**：生产环境 nginx 出现大量 502 错误

**排查过程**：
1. 检查 nginx 错误日志 → `upstream timed out`
2. 检查后端服务状态 → PHP-FPM 进程数不足
3. `netstat -an | grep :9000 | wc -l` → 连接数接近上限

**解决方案**：
- 增大 PHP-FPM `pm.max_children`
- 调整 nginx `proxy_read_timeout`
- 添加健康检查策略

**预防措施**：
- 监控 upstream 响应时间
- 设置合理的连接池大小"""},
    {"title": "系统巡检标准操作流程", "category": "操作指南",
     "tags": "巡检,SOP,系统健康,检查", "severity": "info",
     "content": """## 每日巡检 SOP

### 1. 系统资源检查
- CPU 负载 < 70%
- 内存使用率 < 85%
- 磁盘使用率 < 80%
- Swap 使用 < 20%

### 2. 服务状态检查
- 关键服务运行状态
- 服务日志异常扫描
- 端口监听验证

### 3. 安全检查
- 异常登录审计
- 文件完整性校验
- 防火墙规则验证"""},
]


@router.get("/articles")
async def list_articles(
    page: int = 1, size: int = 20,
    category: str = "", keyword: str = "",
    db: AsyncSession = Depends(get_db),
):
    q = select(KnowledgeArticle).order_by(KnowledgeArticle.updated_at.desc())
    conditions = []
    if category:
        conditions.append(KnowledgeArticle.category == category)
    if keyword:
        conditions.append(or_(
            KnowledgeArticle.title.contains(keyword),
            KnowledgeArticle.content.contains(keyword),
            KnowledgeArticle.tags.contains(keyword),
        ))
    if conditions:
        q = q.where(*conditions)

    total = (await db.execute(
        select(func.count()).select_from(KnowledgeArticle).where(*conditions) if conditions
        else select(func.count()).select_from(KnowledgeArticle)
    )).scalar() or 0

    rows = (await db.execute(q.offset((page - 1) * size).limit(size))).scalars().all()

    items = []
    for r in rows:
        items.append({
            "id": r.id, "title": r.title, "category": r.category,
            "tags": r.tags.split(",") if r.tags else [],
            "content": r.content, "source": r.source, "severity": r.severity,
            "viewCount": r.view_count,
            "createdAt": r.created_at.isoformat() if r.created_at else "",
            "updatedAt": r.updated_at.isoformat() if r.updated_at else "",
        })

    return {"code": 0, "data": {"items": items, "total": total, "page": page, "size": size}}


@router.get("/articles/{article_id}")
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    q = select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
    r = (await db.execute(q)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="文章不存在")
    r.view_count = (r.view_count or 0) + 1
    await db.commit()
    return {
        "code": 0, "data": {
            "id": r.id, "title": r.title, "category": r.category,
            "tags": r.tags.split(",") if r.tags else [],
            "content": r.content, "source": r.source, "severity": r.severity,
            "viewCount": r.view_count,
            "createdAt": r.created_at.isoformat() if r.created_at else "",
        },
    }


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    q = select(KnowledgeArticle.category, func.count()).group_by(KnowledgeArticle.category)
    rows = (await db.execute(q)).all()
    categories = [{"name": r[0], "count": r[1]} for r in rows]
    return {"code": 0, "data": categories}


@router.get("/stats")
async def knowledge_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count()).select_from(KnowledgeArticle))).scalar() or 0
    views = (await db.execute(select(func.sum(KnowledgeArticle.view_count)))).scalar() or 0
    cats = (await db.execute(
        select(KnowledgeArticle.category, func.count()).group_by(KnowledgeArticle.category)
    )).all()
    return {
        "code": 0, "data": {
            "totalArticles": total,
            "totalViews": views,
            "categories": [{"name": c[0], "count": c[1]} for c in cats],
        },
    }


async def seed_knowledge(db: AsyncSession):
    """初始化预设知识库"""
    q = select(func.count()).select_from(KnowledgeArticle)
    if (await db.execute(q)).scalar() == 0:
        for item in PRESET_KNOWLEDGE:
            db.add(KnowledgeArticle(**item))
        await db.commit()
