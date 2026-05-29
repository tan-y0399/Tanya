"""
导入 zhishiku.md — 银河麒麟常见运维问题

结构: "N 分类名" → "N. 问题标题" → "A： 答案"
"""

import re
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import async_session
from app.models.knowledge import KnowledgeArticle
from sqlalchemy import select

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "zhishiku.md")

# 严重程度关键词
SEVERITY_CRITICAL = ["失败", "无法", "崩溃", "卡死", "死机", "损坏", "无法启动", "报错"]
SEVERITY_WARNING = ["慢", "超时", "异常", "问题", "错误", "不显示", "不能", "不行", "没反应"]


def infer_severity(title: str, content: str) -> str:
    text = title + content
    for kw in SEVERITY_CRITICAL:
        if kw in text:
            return "critical"
    for kw in SEVERITY_WARNING:
        if kw in text:
            return "warning"
    return "info"


def extract_tags(title: str, content: str) -> str:
    keywords = [
        "安装", "启动", "登录", "激活", "权限", "版本", "软件", "外设",
        "显示", "网络", "输入法", "挂载", "卸载", "应用", "U盘", "光盘",
        "BIOS", "GRUB", "分区", "文件系统", "驱动", "内核", "SSH",
        "显示器", "分辨率", "显卡", "网卡", "声卡", "打印机", "蓝牙",
        "防火墙", "DNS", "IP", "DHCP", "密码", "root", "用户",
        "麒麟", "银河麒麟", "FT2000", "飞腾", "X86", "ARM", "龙芯",
    ]
    found = set()
    text_lower = (title + " " + content).lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            found.add(kw)
    return ",".join(sorted(found)[:10])


def parse_zhishiku(text: str) -> list:
    """解析 zhishiku.md 格式的知识库"""
    articles = []
    current_category = ""
    current_title = ""
    current_lines = []

    lines = text.split("\n")

    def save_article():
        nonlocal current_title, current_lines
        if current_title and current_lines:
            content = "\n".join(current_lines).strip()
            articles.append({
                "title": current_title,
                "category": current_category or "其他",
                "content": content,
                "tags": extract_tags(current_title, content),
                "severity": infer_severity(current_title, content),
            })
        current_title = ""
        current_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # 分类标题: "N 分类名" (行首数字+空格，没有点号)
        cat_match = re.match(r"^(\d+)\s+(\S.*)$", line)
        if cat_match and "." not in line[:4] and len(line) < 50:
            save_article()
            current_category = cat_match.group(2).strip()
            i += 1
            continue

        # 问题标题: "N. question title"
        q_match = re.match(r"^\d+\.[\s　]+(.+)$", line)
        if q_match:
            save_article()
            current_title = q_match.group(1).strip()
            # 清理标题末尾的 "?" 或 "？"
            current_title = current_title.rstrip("?？").strip()
            current_lines = []
            i += 1
            continue

        # 收集答案内容
        if current_title:
            # 跳过空行但累积
            current_lines.append(line)

        i += 1

    save_article()
    return articles


async def import_articles():
    if not os.path.exists(KB_PATH):
        print(f"错误: 找不到文件 {KB_PATH}")
        return

    with open(KB_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    articles = parse_zhishiku(text)
    print(f"解析到 {len(articles)} 篇文章\n")

    async with async_session() as db:
        inserted = 0
        skipped = 0

        for a in articles:
            if not a["content"].strip():
                skipped += 1
                continue

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
            cat_short = a["category"][:20]
            title_short = a["title"][:50]
            print(f"  + [{cat_short}] {title_short}")

        await db.commit()

    print(f"\n导入完成: 新增 {inserted} 篇, 跳过 {skipped} 篇")


if __name__ == "__main__":
    asyncio.run(import_articles())
