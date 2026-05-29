"""
导入银河麒麟知识库 — 解析 kylin_os_knowledge_base.md 并写入数据库

用法:
  cd backend
  python scripts/import_knowledge_base.py
"""

import re
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import async_session
from app.models.knowledge import KnowledgeArticle
from sqlalchemy import select


KB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "kylin_os_knowledge_base.md")

# 分类名映射
CATEGORY_MAP = {
    "一": "磁盘与文件系统",
    "二": "进程与内存",
    "三": "网络问题",
    "四": "服务管理",
    "五": "系统启动与内核",
    "六": "安全与权限",
    "七": "配置漂移与系统管理",
    "八": "日志系统",
    "九": "国产化平台",
    "十": "运维最佳实践",
}

# 严重程度推断关键词
SEVERITY_KEYWORDS = {
    "critical": ["崩溃", "无法启动", "OOM", "断电", "入侵", "kernel panic", "Killed", "hang", "数据损坏", "致命"],
    "warning": ["失败", "错误", "拒绝", "超时", "异常", "故障", "高", "慢", "满", "泄漏", "攻击", "阻断"],
}


def infer_severity(text: str) -> str:
    text_lower = text.lower()
    for kw in SEVERITY_KEYWORDS["critical"]:
        if kw.lower() in text_lower:
            return "critical"
    for kw in SEVERITY_KEYWORDS["warning"]:
        if kw.lower() in text_lower:
            return "warning"
    return "info"


def extract_tags(title: str, content: str) -> str:
    """从标题和内容中提取标签"""
    tag_keywords = [
        "磁盘", "I/O", "文件系统", "日志", "根分区", "只读", "性能",
        "内存", "OOM", "泄漏", "僵尸进程", "负载", "段错误", "core dump",
        "网络", "DNS", "防火墙", "端口", "连接数", "网卡", "驱动",
        "SSH", "服务", "启动", "systemd", "登录", "图形界面",
        "内核", "重启", "BusyBox", "Call Trace", "panic",
        "权限", "密码", "入侵", "安全", "SELinux",
        "配置", "时间同步", "内核参数", "sysctl",
        "麒麟", "银河麒麟", "飞腾", "龙芯", "国产化",
        "监控", "Prometheus", "fail2ban", "auditd", "logrotate",
    ]
    found = set()
    text_lower = (title + " " + content).lower()
    for kw in tag_keywords:
        if kw.lower() in text_lower:
            found.add(kw)
    return ",".join(sorted(found)[:10])


def parse_knowledge_base(text: str) -> list:
    """解析 Markdown 知识库，返回文章列表"""
    articles = []
    current_category = ""
    current_article = None
    content_lines = []

    # 按行解析
    lines = text.split("\n")

    for line in lines:
        # 一级分类
        if line.startswith("## ") and not line.startswith("### "):
            # 保存上一个文章
            if current_article and content_lines:
                content = "\n".join(content_lines).strip()
                current_article["content"] = content
                current_article["tags"] = extract_tags(current_article["title"], content)
                current_article["severity"] = infer_severity(content)
                articles.append(current_article)

            # 提取分类名
            cat_match = re.match(r"^##\s*[一二三四五六七八九十]、(.+)$", line)
            if cat_match:
                current_category = cat_match.group(1).strip()

            current_article = None
            content_lines = []
            continue

        # 二级/三级文章标题
        if line.startswith("### "):
            if current_article and content_lines:
                content = "\n".join(content_lines).strip()
                current_article["content"] = content
                current_article["tags"] = extract_tags(current_article["title"], content)
                current_article["severity"] = infer_severity(content)
                articles.append(current_article)

            title = line.replace("### ", "").strip()
            # 移除编号前缀如 "1.1 " 或 "8.1 "
            title = re.sub(r"^\d+\.\d+\s+", "", title)

            current_article = {
                "title": title,
                "category": current_category or "其他",
            }
            content_lines = []
            continue

        # 跳过 --- 分隔线
        if line.strip() == "---":
            continue

        # 收集内容
        if current_article is not None and line.strip():
            content_lines.append(line)

    # 保存最后一篇文章
    if current_article and content_lines:
        content = "\n".join(content_lines).strip()
        current_article["content"] = content
        current_article["tags"] = extract_tags(current_article["title"], content)
        current_article["severity"] = infer_severity(content)
        articles.append(current_article)

    return articles


async def import_articles():
    if not os.path.exists(KB_PATH):
        print(f"错误: 找不到知识库文件 {KB_PATH}")
        return

    with open(KB_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    articles = parse_knowledge_base(text)
    print(f"解析到 {len(articles)} 篇文章")

    async with async_session() as db:
        inserted = 0
        skipped = 0

        for a in articles:
            # 检查是否已存在（按标题去重）
            existing = await db.execute(
                select(KnowledgeArticle).where(KnowledgeArticle.title == a["title"])
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            article = KnowledgeArticle(
                title=a["title"],
                category=a["category"],
                tags=a["tags"],
                content=a["content"],
                source="imported",
                severity=a["severity"],
            )
            db.add(article)
            inserted += 1
            print(f"  + [{a['category']}] {a['title'][:50]}...")

        await db.commit()

    print(f"\n导入完成: 新增 {inserted} 篇, 跳过 {skipped} 篇 (已存在)")


if __name__ == "__main__":
    asyncio.run(import_articles())
