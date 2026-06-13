"""知识库管理 API"""
import os
import re
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete as sql_delete
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.knowledge import KnowledgeArticle
from app.services.knowledge_engagement import (
    ensure_knowledge_schema,
    get_user_engagements,
    toggle_like,
    toggle_favorite,
)
from app.services.article_file_validator import validate_article_file

router = APIRouter(prefix="/knowledge", tags=["知识库"])


def _article_item(r: KnowledgeArticle, engagement: dict | None = None) -> dict:
    item = {
        "id": r.id, "title": r.title, "category": r.category,
        "tags": r.tags.split(",") if r.tags else [],
        "content": r.content, "source": r.source, "severity": r.severity,
        "viewCount": r.view_count or 0,
        "likeCount": getattr(r, "like_count", 0) or 0,
        "favoriteCount": getattr(r, "favorite_count", 0) or 0,
        "createdAt": r.created_at.isoformat() if r.created_at else "",
        "updatedAt": r.updated_at.isoformat() if r.updated_at else "",
    }
    if engagement is not None:
        item["liked"] = engagement.get("liked", False)
        item["favorited"] = engagement.get("favorited", False)
    return item

# 知识库文件路径（多级回退查找）
def _resolve_kb_paths() -> dict:
    """查找所有知识库文件，返回 {来源名: 文件路径}"""
    base_dir = r"C:\Users\33255\Desktop\新建文件夹"
    sources = {
        "kylin_ops": ["kylin_os_knowledge_base.md"],
        "common_faq": ["zhishiku.md"],
    }
    result = {}
    for src_name, filenames in sources.items():
        for fn in filenames:
            candidates = [
                os.path.join(base_dir, fn),
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "新建文件夹", fn),
                os.path.join(os.path.dirname(__file__), "..", "..", "..", fn),
            ]
            for p in candidates:
                normalized = os.path.normpath(p)
                if os.path.exists(normalized):
                    result[src_name] = normalized
                    break
    return result

KB_PATHS = _resolve_kb_paths()


def parse_markdown_knowledge(md_path: str = None) -> List[Dict]:
    """解析银河麒麟运维问题知识库 Markdown 文件"""
    path = md_path or KB_PATHS.get("kylin_ops", "")
    if not path or not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    articles = []
    # 按 ## 大标题拆分大类
    sections = re.split(r'\n(?=## )', text)

    for section in sections:
        # 提取大类名称
        section_match = re.match(r'^##\s+(.+?)(?:\n|$)', section)
        if not section_match:
            continue
        raw_category = section_match.group(1).strip()

        # 跳过纯参考/说明性章节（日志系统说明、最佳实践清单）
        # 提取大类简称作为 category
        category = _normalize_category(raw_category)

        # 按 ### 拆分子条目
        subsections = re.split(r'\n(?=### )', section)
        for sub in subsections:
            sub_match = re.match(r'^###\s+(.+?)(?:\n|$)', sub)
            if not sub_match:
                continue
            title = sub_match.group(1).strip()
            content = sub.strip()

            # 跳过纯信息性条目（日志文件说明、关键字说明、kylin-sysassist介绍）
            if any(skip in title for skip in ["日志系统核心文件说明", "日志分析关键关键字", "kylin-sysassist"]):
                continue

            # 提取问题编号
            problem_id = ""
            id_match = re.search(r'\*\*问题编号\*\*\s*\|\s*(\S+)', content)
            if id_match:
                problem_id = id_match.group(1)

            # 提取标签
            tags = _extract_tags(title, content, category)

            # 确定严重程度
            severity = _determine_severity(title, content)

            articles.append({
                "title": title,
                "category": category,
                "tags": ",".join(tags),
                "content": content,
                "source": "imported",
                "severity": severity,
            })

    return articles


def parse_zhishiku_faq(faq_path: str = None) -> List[Dict]:
    """解析 zhishiku.md 常见问题 FAQ 格式文件"""
    path = faq_path or KB_PATHS.get("common_faq", "")
    if not path or not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    articles = []
    # 分类名映射（前缀"常见-"避免与运维知识库分类冲突）
    FAQ_CATEGORIES = {
        "安装问题": "常见-安装问题",
        "启动问题": "常见-启动问题",
        "登录问题": "常见-登录问题",
        "激活问题": "常见-激活问题",
        "权限问题": "常见-权限问题",
        "版本问题": "常见-版本问题",
        "软件安装": "常见-软件安装",
        "外设使用": "常见-外设使用",
        "手册问题": "常见-手册问题",
        "显示问题": "常见-显示问题",
        "网络问题": "常见-网络问题",
        "输入问题": "常见-输入问题",
        "挂卸载问题": "常见-挂卸载问题",
        "应用问题": "常见-应用问题",
        "其他问题": "常见-其他问题",
    }

    current_category = None
    current_index = 0
    current_question = ""
    current_answer_lines = []
    in_answer = False

    def flush_article():
        nonlocal current_question, current_answer_lines, in_answer, current_index
        if current_question and current_answer_lines:
            answer = "\n".join(current_answer_lines).strip()
            if answer:
                faq_cat = FAQ_CATEGORIES.get(current_category, "常见-" + (current_category or "其他"))
                title = current_question[:200]
                content = "## {0}\n\n**分类**: {1}\n\n{2}".format(
                    current_question, current_category, answer)
                tags = _extract_faq_tags(current_category, current_question, answer)
                severity = _determine_faq_severity(current_question, answer)
                articles.append({
                    "title": title,
                    "category": faq_cat,
                    "tags": ",".join(tags),
                    "content": content,
                    "source": "faq_imported",
                    "severity": severity,
                })
        current_question = ""
        current_answer_lines = []
        in_answer = False

    for line_num, line in enumerate(lines):
        stripped = line.strip()

        # 检测分类行：行首数字 + 空格 + 中文标题，且整行只有分类名
        cat_match = re.match(r'^(\d{1,2})\s+(安装问题|启动问题|登录问题|激活问题|权限问题|版本问题|软件安装|外设使用|手册问题|显示问题|网络问题|输入问题|挂卸载问题|应用问题|其他问题)\s*$', stripped)
        if cat_match:
            flush_article()
            current_category = cat_match.group(2)
            current_index = 0
            continue

        # 跳过文件头（首行"银河麒麟 常见运维问题"）
        if line_num == 0 and "银河麒麟" in stripped:
            continue

        # 检测问题行：数字. 开头
        q_match = re.match(r'^(\d{1,3})\.\s+(.+)', stripped)
        if q_match and current_category:
            flush_article()
            current_index = int(q_match.group(1))
            current_question = q_match.group(2).strip()
            in_answer = False
            continue

        # 检测答案行：A: 或 A：开头
        if re.match(r'^A[：:]\s*', stripped):
            in_answer = True
            answer_text = re.sub(r'^A[：:]\s*', '', stripped)
            if answer_text:
                current_answer_lines.append(answer_text)
            continue

        # 如果正在收集答案，追加内容
        if in_answer and current_question:
            if stripped:
                # 去掉可能的前导空格/制表符
                current_answer_lines.append(stripped)
            else:
                # 空行：如果后续有内容则保留，否则可能结束当前答案
                current_answer_lines.append("")

    # 处理最后一篇文章
    flush_article()

    return articles


# FAQ 分类关键词 → 标签映射
FAQ_CATEGORY_TAGS = {
    "安装问题": ["安装", "系统安装", "部署"],
    "启动问题": ["启动", "引导", "开机"],
    "登录问题": ["登录", "认证", "密码"],
    "激活问题": ["激活", "授权", "license"],
    "权限问题": ["权限", "安全", "sudo"],
    "版本问题": ["版本", "内核", "更新"],
    "软件安装": ["软件", "安装", "卸载", "deb"],
    "外设使用": ["外设", "打印机", "光盘", "U盘"],
    "手册问题": ["手册", "文档", "帮助"],
    "显示问题": ["显示", "桌面", "任务栏", "图形"],
    "网络问题": ["网络", "IP", "DNS", "网卡"],
    "输入问题": ["输入法", "键盘", "fcitx"],
    "挂卸载问题": ["挂载", "卸载", "分区", "fstab"],
    "应用问题": ["应用", "浏览器", "办公", "兼容"],
    "其他问题": ["其他", "工具", "技巧"],
}


def _extract_faq_tags(category: str, question: str, answer: str) -> List[str]:
    """为 FAQ 文章提取标签"""
    tags = list(FAQ_CATEGORY_TAGS.get(category, [category]))[:3]
    text = question + " " + answer[:200]
    keyword_map = {
        "U盘": "U盘", "光盘": "光盘", "grub": "GRUB", "livecd": "livecd",
        "BIOS": "BIOS", "PXE": "PXE", "ghost": "ghost", "分区": "分区",
        "dd": "dd命令", "rsync": "rsync", "busybox": "BusyBox",
        "ssh": "SSH", "密码": "密码", "root": "root", "激活": "激活",
        "授权": "授权", "license": "授权", "ukey": "ukey",
        "防火墙": "防火墙", "selinux": "SELinux", "apparmor": "apparmor",
        "dpkg": "dpkg", "apt": "apt", "deb": "deb", "rpm": "rpm",
        "打印机": "打印机", "驱动": "驱动", "网卡": "网卡", "wifi": "wifi",
        "WPS": "WPS", "微信": "微信", "浏览器": "浏览器", "flash": "flash",
        "搜狗": "输入法", "fcitx": "输入法", "VMware": "VMware",
        "NFS": "NFS", "挂载": "挂载", "fstab": "fstab", "mount": "mount",
        "VNC": "VNC", "xmanager": "xmanager", "teamviewer": "teamviewer",
        "蓝牙": "蓝牙", "sudo": "sudo", "权限": "权限",
        "飞腾": "飞腾", "鲲鹏": "鲲鹏", "龙芯": "龙芯", "兆芯": "x86",
        "MySQL": "MySQL", "数据库": "数据库",
    }
    for kw, tag in keyword_map.items():
        if kw.lower() in text.lower() and tag not in tags:
            tags.append(tag)
    return tags[:8]


def _determine_faq_severity(question: str, answer: str) -> str:
    """判断 FAQ 严重程度"""
    text = question + " " + answer[:200]
    critical = ["无法启动", "卡死", "崩溃", "进不去系统", "BusyBox", "panic",
        "死机", "无法进入", "安装失败", "启动失败", "登录失败"]
    warning = ["失败", "乱码", "消失", "无法打开", "无法使用", "异常",
        "无法连接", "无法访问", "问题", "错误", "报错", "重启", "卡住"]
    for kw in critical:
        if kw in text:
            return "critical"
    for kw in warning:
        if kw in text:
            return "warning"
    return "info"


def parse_all_knowledge() -> List[Dict]:
    """解析所有知识库文件，合并返回"""
    all_articles = []
    all_articles.extend(parse_markdown_knowledge())
    all_articles.extend(parse_zhishiku_faq())
    return all_articles


def _normalize_category(raw: str) -> str:
    """清理大类名称，返回简洁分类名"""
    # 去掉编号前缀：一、二、... 十、
    name = re.sub(r'^[一二三四五六七八九十]+、', '', raw).strip()
    return name


def _extract_tags(title: str, content: str, category: str) -> List[str]:
    """从标题和内容中提取标签"""
    tags = []
    # 分类 → 自动添加的标签（确保分类标签在列表中）
    category_tag_map = {
        "磁盘与文件系统问题": ["磁盘", "文件系统"],
        "进程与内存问题": ["进程", "内存"],
        "网络问题": ["网络"],
        "服务管理问题": ["服务", "systemd"],
        "系统启动与内核问题": ["内核", "启动"],
        "安全与权限问题": ["安全", "权限"],
        "配置漂移与系统管理问题": ["配置", "系统管理"],
        "国产化平台特有问题": ["国产化"],
    }
    # 自动添加分类标签
    if category in category_tag_map:
        for tag in category_tag_map[category]:
            if tag not in tags:
                tags.append(tag)

    keyword_map = {
        "磁盘": "磁盘", "I/O": "I/O", "IO": "I/O", "文件系统": "文件系统",
        "日志": "日志", "内存": "内存", "OOM": "OOM", "进程": "进程",
        "僵尸": "僵尸进程", "崩溃": "崩溃", "Segfault": "段错误",
        "网络": "网络", "端口": "端口", "防火墙": "防火墙", "DNS": "DNS",
        "网卡": "网卡", "SSH": "SSH", "服务": "服务", "systemd": "systemd",
        "启动": "启动", "内核": "内核", "panic": "Kernel Panic",
        "安全": "安全", "权限": "权限", "密码": "密码", "入侵": "入侵检测",
        "配置": "配置", "时间": "时间同步", "NTP": "NTP",
        "飞腾": "飞腾", "龙芯": "龙芯", "国产化": "国产化",
        "性能": "性能", "负载": "负载", "BusyBox": "BusyBox",
        "fsck": "fsck", "GRUB": "GRUB", "kylin": "kylin",
    }
    text = title + " " + content[:500]
    for kw, tag in keyword_map.items():
        if kw.lower() in text.lower() and tag not in tags:
            tags.append(tag)
    if len(tags) > 8:
        tags = tags[:8]
    if not tags:
        tags.append(category[:6])
    return tags


def _determine_severity(title: str, content: str) -> str:
    """根据内容判断严重程度"""
    text = title + " " + content[:300]
    critical_keywords = ["崩溃", "OOM", "Killer", "panic", "Kernel panic",
        "无法启动", "入侵", "自动重启", "BusyBox", "数据损坏"]
    warning_keywords = ["空间满", "只读", "瓶颈", "负载过高", "泄漏",
        "失败", "阻断", "过高", "闪退", "Call Trace", "漂移"]

    for kw in critical_keywords:
        if kw.lower() in text.lower():
            return "critical"
    for kw in warning_keywords:
        if kw.lower() in text.lower():
            return "warning"
    return "info"


@router.get("/articles")
async def list_articles(
    page: int = 1, size: int = 20,
    category: str = "", keyword: str = "",
    sort: str = "", tags: str = "",
    userKey: str = "",
    db: AsyncSession = Depends(get_db),
):
    q = select(KnowledgeArticle)
    conditions = []
    if category:
        conditions.append(KnowledgeArticle.category == category)
    if keyword:
        conditions.append(or_(
            KnowledgeArticle.title.contains(keyword),
            KnowledgeArticle.content.contains(keyword),
            KnowledgeArticle.tags.contains(keyword),
        ))
    if tags:
        for tag in [t.strip() for t in tags.split(",") if t.strip()]:
            conditions.append(KnowledgeArticle.tags.contains(tag))
    if conditions:
        q = q.where(*conditions)

    if sort == "views":
        q = q.order_by(KnowledgeArticle.view_count.desc(), KnowledgeArticle.updated_at.desc())
    elif sort == "title":
        q = q.order_by(KnowledgeArticle.title.asc())
    elif sort == "likes":
        q = q.order_by(KnowledgeArticle.like_count.desc(), KnowledgeArticle.updated_at.desc())
    else:
        q = q.order_by(KnowledgeArticle.updated_at.desc())

    total = (await db.execute(
        select(func.count()).select_from(KnowledgeArticle).where(*conditions) if conditions
        else select(func.count()).select_from(KnowledgeArticle)
    )).scalar() or 0

    rows = (await db.execute(q.offset((page - 1) * size).limit(size))).scalars().all()

    user_eng = {}
    if userKey:
        user_eng = await get_user_engagements(db, userKey, [r.id for r in rows])

    items = [
        _article_item(r, user_eng.get(r.id, {"liked": False, "favorited": False}) if userKey else None)
        for r in rows
    ]

    return {"code": 0, "data": {"items": items, "total": total, "page": page, "size": size}}


@router.get("/articles/{article_id}")
async def get_article(article_id: str, userKey: str = "", db: AsyncSession = Depends(get_db)):
    q = select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
    r = (await db.execute(q)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="文章不存在")
    r.view_count = (r.view_count or 0) + 1
    await db.commit()
    await db.refresh(r)

    engagement = None
    if userKey:
        user_eng = await get_user_engagements(db, userKey, [article_id])
        engagement = user_eng.get(article_id)

    return {"code": 0, "data": _article_item(r, engagement)}


@router.get("/engagement")
async def list_engagement(userKey: str = "", db: AsyncSession = Depends(get_db)):
    if not userKey:
        return {"code": 0, "data": {}}
    data = await get_user_engagements(db, userKey)
    return {"code": 0, "data": data}


@router.post("/articles/{article_id}/like")
async def like_article(article_id: str, req: dict = Body(default={}), db: AsyncSession = Depends(get_db)):
    user_key = (req.get("userKey") or "").strip()
    if not user_key:
        raise HTTPException(status_code=400, detail="缺少 userKey")
    data = await toggle_like(db, article_id, user_key)
    if not data:
        raise HTTPException(status_code=404, detail="文章不存在")
    return {"code": 0, "data": data}


@router.post("/articles/{article_id}/favorite")
async def favorite_article(article_id: str, req: dict = Body(default={}), db: AsyncSession = Depends(get_db)):
    user_key = (req.get("userKey") or "").strip()
    if not user_key:
        raise HTTPException(status_code=400, detail="缺少 userKey")
    data = await toggle_favorite(db, article_id, user_key)
    if not data:
        raise HTTPException(status_code=404, detail="文章不存在")
    return {"code": 0, "data": data}


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


@router.post("/search")
async def search_knowledge(req: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """RAG 语义搜索知识库"""
    query = req.get("query", "")
    top_k = req.get("top_k", 5)
    if not query:
        return {"code": 0, "data": {"results": []}}

    from app.services.knowledge_rag import knowledge_rag

    if not knowledge_rag._initialized:
        result = await db.execute(select(KnowledgeArticle))
        articles = []
        for a in result.scalars().all():
            articles.append({"id": a.id, "title": a.title, "content": a.content,
                "category": a.category, "tags": a.tags})
        knowledge_rag.build_index(articles)

    results = knowledge_rag.search(query, top_k)
    return {"code": 0, "data": {"results": results, "query": query}}


@router.post("/reindex")
async def reindex_knowledge(db: AsyncSession = Depends(get_db)):
    """重建知识库索引"""
    from app.services.knowledge_rag import knowledge_rag

    result = await db.execute(select(KnowledgeArticle))
    articles = []
    for a in result.scalars().all():
        articles.append({"id": a.id, "title": a.title, "content": a.content,
            "category": a.category, "tags": a.tags})
    knowledge_rag.refresh(articles)
    return {"code": 0, "message": f"索引已重建，共 {len(articles)} 篇文章"}


@router.post("/reset")
async def reset_knowledge(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空旧知识库并从所有 Markdown 文件重新导入"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可重置知识库")

    # 1. 清空旧数据
    await db.execute(sql_delete(KnowledgeArticle))
    await db.commit()

    # 2. 解析所有知识库文件
    articles = parse_all_knowledge()
    if not articles:
        files_found = list(KB_PATHS.keys())
        raise HTTPException(status_code=400,
            detail="未找到任何知识库文件。已查找: {}".format(files_found or "无"))

    for item in articles:
        db.add(KnowledgeArticle(**item))
    await db.commit()

    # 3. 重建 RAG 索引
    try:
        from app.services.knowledge_rag import knowledge_rag
        result = await db.execute(select(KnowledgeArticle))
        all_articles = []
        for a in result.scalars().all():
            all_articles.append({"id": a.id, "title": a.title, "content": a.content,
                "category": a.category, "tags": a.tags})
        knowledge_rag.refresh(all_articles)
    except Exception:
        pass

    # 4. 统计分类
    cats_result = await db.execute(
        select(KnowledgeArticle.category, func.count()).group_by(KnowledgeArticle.category)
    )
    cats = [{"name": r[0], "count": r[1]} for r in cats_result.all()]
    source_counts = {}
    for a in articles:
        s = a.get("source", "unknown")
        source_counts[s] = source_counts.get(s, 0) + 1

    return {"code": 0, "message": "知识库已重置，共导入 {} 篇文章".format(len(articles)), "data": {
        "total": len(articles), "categories": cats, "sources": source_counts,
    }}


@router.post("/validate-file")
async def validate_article_file_api(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """诊断并解析上传的知识库文件（拖拽导入前校验）"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    filename = (payload.get("filename") or "").strip()
    content = payload.get("content") or ""
    if not filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    result = validate_article_file(filename, content)
    if result.get("ok") and result.get("mode") == "single":
        title = (result.get("title") or "").strip()
        if title:
            existing = (
                await db.execute(select(KnowledgeArticle).where(KnowledgeArticle.title == title))
            ).scalar_one_or_none()
            if existing:
                result["ok"] = False
                result["stage"] = "diagnose"
                diagnose = result.setdefault("diagnose", {"ok": False, "messages": [], "errors": [], "warnings": []})
                diagnose["ok"] = False
                errors = diagnose.setdefault("errors", [])
                if f"文章标题「{title}」已存在" not in errors:
                    errors.insert(0, f"文章标题「{title}」已存在")

    return {"code": 0, "data": result}


@router.post("/import-batch")
async def import_articles_batch(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量导入知识库文章（跳过已存在标题）"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    items = payload.get("articles") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="articles 不能为空")

    created = 0
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        title = (item.get("title") or "").strip()
        if not title:
            skipped += 1
            continue
        existing = (
            await db.execute(select(KnowledgeArticle).where(KnowledgeArticle.title == title))
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        tags = item.get("tags") or ""
        if isinstance(tags, list):
            tags = ",".join(str(t).strip() for t in tags if str(t).strip())
        db.add(KnowledgeArticle(
            title=title,
            category=(item.get("category") or "")[:120],
            tags=str(tags)[:500],
            content=item.get("content") or "",
            source=item.get("source") or "file_import",
            severity=(item.get("severity") or "info")[:20],
        ))
        created += 1

    await db.commit()
    return {
        "code": 0,
        "message": f"批量导入完成：新增 {created} 篇，跳过 {skipped} 篇",
        "data": {"created": created, "skipped": skipped},
    }


@router.post("/articles")
async def create_article(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可添加文章")
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    article = KnowledgeArticle(
        title=title,
        category=payload.get("category", ""),
        tags=payload.get("tags", ""),
        content=payload.get("content", ""),
        source=payload.get("source", "manual"),
        severity=payload.get("severity", "info"),
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return {"code": 0, "data": {
        "id": article.id, "title": article.title, "category": article.category,
        "tags": article.tags.split(",") if article.tags else [],
        "content": article.content, "source": article.source, "severity": article.severity,
        "viewCount": article.view_count,
        "createdAt": article.created_at.isoformat() if article.created_at else "",
    }, "message": "文章创建成功"}


@router.put("/articles/{article_id}")
async def update_article(
    article_id: str,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可编辑文章")
    r = (await db.execute(select(KnowledgeArticle).where(KnowledgeArticle.id == article_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="文章不存在")
    if "title" in payload:
        r.title = payload["title"]
    if "category" in payload:
        r.category = payload["category"]
    if "tags" in payload:
        r.tags = payload["tags"]
    if "content" in payload:
        r.content = payload["content"]
    if "severity" in payload:
        r.severity = payload["severity"]
    await db.commit()
    await db.refresh(r)
    return {"code": 0, "data": {
        "id": r.id, "title": r.title, "category": r.category,
        "tags": r.tags.split(",") if r.tags else [],
        "content": r.content, "source": r.source, "severity": r.severity,
        "viewCount": r.view_count,
        "createdAt": r.created_at.isoformat() if r.created_at else "",
    }, "message": "文章更新成功"}


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可删除文章")
    r = (await db.execute(select(KnowledgeArticle).where(KnowledgeArticle.id == article_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="文章不存在")
    await db.delete(r)
    await db.commit()
    return {"code": 0, "message": "文章已删除"}


async def seed_knowledge(db: AsyncSession):
    """初始化知识库：清空旧数据并从所有 Markdown 文件重新导入"""
    articles = parse_all_knowledge()
    if not articles:
        count = (await db.execute(select(func.count()).select_from(KnowledgeArticle))).scalar() or 0
        if count == 0:
            articles = _fallback_articles()
        else:
            return

    # 清空旧数据，导入新知识库
    await db.execute(sql_delete(KnowledgeArticle))
    for item in articles:
        db.add(KnowledgeArticle(**item))
    await db.commit()


def _fallback_articles() -> List[Dict]:
    """当 Markdown 文件不可用时的最小预设"""
    return [
        {"title": "根目录空间满导致服务无法启动", "category": "磁盘与文件系统问题",
         "tags": "磁盘,日志,空间,服务", "severity": "critical",
         "content": "## 根目录空间满\n\n排查: `df -h` → `du -sh /var/log/*`\n\n解决: 清理旧日志, 启用 logrotate, 配置磁盘监控告警."},
        {"title": "内存泄漏/OOM Killer触发", "category": "进程与内存问题",
         "tags": "内存,OOM,进程,泄漏", "severity": "critical",
         "content": "## 内存泄漏排查\n\n`free -h` → `vmstat 1 10` → `ps aux --sort=-%mem`\n\n定位泄漏进程并修复."},
        {"title": "网络不可达排查", "category": "网络问题",
         "tags": "网络,端口,防火墙,DNS", "severity": "critical",
         "content": "## 网络不可达\n\n`ip addr` → `ip route` → `ping 网关`.\n\n检查网卡、防火墙、DNS配置."},
        {"title": "服务启动失败排查", "category": "服务管理问题",
         "tags": "服务,systemd,配置,日志", "severity": "warning",
         "content": "## 服务启动失败\n\n`systemctl status <服务>` → `journalctl -u <服务>`.\n\n检查配置文件、依赖、端口占用."},
        {"title": "系统无故自动重启", "category": "系统启动与内核问题",
         "tags": "内核,崩溃,panic,硬件", "severity": "critical",
         "content": "## 系统自动重启\n\n`dmesg | grep -i panic` → `journalctl -b -1`.\n\n分析kdump, 检测硬件."},
        {"title": "SSH登录失败排查", "category": "安全与权限问题",
         "tags": "SSH,安全,认证,防火墙", "severity": "warning",
         "content": "## SSH登录失败\n\n检查 sshd 服务状态、防火墙22端口、PAM配置."},
        {"title": "配置文件漂移问题", "category": "配置漂移与系统管理问题",
         "tags": "配置,审计,基线,合规", "severity": "warning",
         "content": "## 配置漂移\n\n`diff <当前> <基线>` → 恢复基线配置 → 部署 auditd 监控."},
        {"title": "飞腾平台网卡兼容性问题", "category": "国产化平台特有问题",
         "tags": "飞腾,网卡,驱动,国产化", "severity": "warning",
         "content": "## 飞腾网卡兼容性\n\n优化 phytium-dwmac 驱动参数, 修复 NetworkManager 配置持久化."},
    ]
