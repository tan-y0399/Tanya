"""
导入 Linux 命令风险分级知识库

用法:
  cd backend
  .venv_linux/bin/python scripts/import_linux_command_risk.py

来源: deploy/knowledge/linux_command_risk_knowledge.md
对齐: app/core/command_security.py RiskLevel L1-L5
"""

import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.core.database import async_session
from app.models.knowledge import KnowledgeArticle

KB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "deploy", "knowledge", "linux_command_risk_knowledge.md"
)

DEFAULT_CATEGORY = "安全与命令分级"


def parse_articles(text: str) -> list:
    """按 ### 标题切分文章。"""
    articles = []
    current = None
    lines_buf = []

    for line in text.split("\n"):
        if line.startswith("### "):
            if current and lines_buf:
                content = "\n".join(lines_buf).strip()
                current["content"] = content
                current["tags"] = _tags(current["title"], content)
                articles.append(current)
            title = line.replace("### ", "").strip()
            title = re.sub(r"^\d+\.\d+\s+", "", title)
            current = {"title": title, "category": DEFAULT_CATEGORY}
            lines_buf = []
            continue
        if line.startswith("## ") and not line.startswith("### "):
            continue
        if current is not None:
            lines_buf.append(line)

    if current and lines_buf:
        content = "\n".join(lines_buf).strip()
        current["content"] = content
        current["tags"] = _tags(current["title"], content)
        articles.append(current)

    return articles


def _tags(title: str, content: str) -> str:
    keys = [
        "L1", "L2", "L3", "L4", "L5", "风险", "命令", "rm", "安全", "审批",
        "只读", "高危", "内存", "网络", "防火墙", "systemctl", "find", "kill",
    ]
    text = title + " " + content
    found = [k for k in keys if k in text]
    return ",".join(sorted(set(found))[:12])


async def import_and_reindex():
    if not os.path.exists(KB_PATH):
        print(f"错误: 找不到 {KB_PATH}")
        return

    with open(KB_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    articles = parse_articles(text)
    print(f"解析到 {len(articles)} 篇命令风险知识")

    inserted = 0
    updated = 0
    skipped = 0

    async with async_session() as db:
        for a in articles:
            result = await db.execute(
                select(KnowledgeArticle).where(KnowledgeArticle.title == a["title"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.content = a["content"]
                existing.category = a["category"]
                existing.tags = a["tags"]
                existing.source = "imported_csdn_risk"
                existing.severity = "warning" if "L4" in a["content"] or "L5" in a["content"] else "info"
                updated += 1
                print(f"  ~ 更新: {a['title'][:50]}")
            else:
                db.add(KnowledgeArticle(
                    title=a["title"],
                    category=a["category"],
                    tags=a["tags"],
                    content=a["content"],
                    source="imported_csdn_risk",
                    severity="warning" if "L4" in a["content"] or "L5" in a["content"] else "info",
                ))
                inserted += 1
                print(f"  + 新增: {a['title'][:50]}")

        await db.commit()

        # 重建 RAG 索引
        from app.services.knowledge_rag import knowledge_rag
        result = await db.execute(select(KnowledgeArticle))
        all_articles = [
            {
                "id": row.id,
                "title": row.title,
                "content": row.content,
                "category": row.category,
                "tags": row.tags,
            }
            for row in result.scalars().all()
        ]
        if all_articles:
            knowledge_rag.build_index(all_articles)
            print(f"RAG 索引已重建，共 {len(all_articles)} 篇")

    print(f"\n完成: 新增 {inserted}, 更新 {updated}, 跳过 {skipped}")


if __name__ == "__main__":
    asyncio.run(import_and_reindex())
