"""知识库数据导入脚本 — 解析 md 文件并导入 PostgreSQL"""
import os, re, sys, uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select, delete, func
from app.core.config import settings
from app.models.knowledge import KnowledgeArticle

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge")
FILE_ZHISHIKU = os.path.join(DATA_DIR, "zhishiku.md")
FILE_KYLIN = os.path.join(DATA_DIR, "kylin_os_knowledge_base.md")

CATEGORY_MAP = {
    "安装": "操作指南", "启动": "故障排查", "登录": "故障排查",
    "激活": "操作指南", "权限": "安全策略", "版本": "操作指南",
    "软件安装": "操作指南", "软件": "操作指南",
    "外设": "操作指南", "手册": "操作指南", "显示": "故障排查",
    "网络": "故障排查", "输入": "故障排查", "挂卸载": "操作指南",
    "应用": "故障排查", "其他": "故障排查",
}
SEVERITY_MAP = {
    "故障排查": "warning", "操作指南": "info",
    "安全策略": "critical", "案例库": "warning",
}


def gen_id():
    return uuid.uuid4().hex[:12]


def parse_zhishiku(text: str):
    """解析 zhishiku.md Q&A 格式"""
    articles = []
    lines = text.split("\n")
    current_section = "其他"
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        # 检测分类标题: "1 安装问题"
        m = re.match(r"^\d+\s+(.+)$", line)
        if m and i + 1 < len(lines) and lines[i + 1].strip() == "":
            section_name = m.group(1).strip()
            current_section = section_name
            i += 1
            continue

        # 检测Q: "1. question text"
        m = re.match(r"^(\d+)\.\s+(.+)", line)
        if m:
            question = m.group(2).strip()
            answers = []
            i += 1
            # 收集答案行
            while i < len(lines):
                aline = lines[i].rstrip()
                # 遇到新分类标题则停止
                if re.match(r"^\d+\s+[^.].+$", aline) and i + 1 < len(lines) and lines[i + 1].strip() == "":
                    break
                # 遇到新问题则停止
                if re.match(r"^\d+\.\s+", aline):
                    break
                answers.append(aline)
                i += 1

            content = f"## {question}\n\n"
            answer_text = "\n".join(answers).strip()
            # 清理答案开头的 "A:" 或 "A:"
            answer_text = re.sub(r"^A[:\xef\xbc\x9a]\s*", "", answer_text)
            content += answer_text

            # 确定分类
            category = "故障排查"
            for key, cat in CATEGORY_MAP.items():
                if key in current_section:
                    category = cat
                    break

            severity = SEVERITY_MAP.get(category, "info")
            tags_str = ",".join(list(dict.fromkeys(
                re.findall(r"[一-龥a-zA-Z]{2,6}", current_section + question[:30])
            ))[:6])

            articles.append({
                "title": question[:200],
                "category": category,
                "tags": tags_str,
                "content": content[:8000],
                "source": "imported",
                "severity": severity,
            })
            continue

        i += 1

    return articles


def parse_kylin_kb(text: str):
    """解析 kylin_os_knowledge_base.md 表格格式"""
    articles = []
    lines = text.split("\n")
    current_section = ""
    current_sub = ""
    current_table_rows = []
    in_table = False

    for line in lines:
        line = line.rstrip()

        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        if line.startswith("### "):
            current_sub = line[4:].strip()
            continue

        if line.startswith("| ") and "---|---" not in line:
            if not in_table:
                in_table = True
                current_table_rows = []
            current_table_rows.append(line)
            continue
        else:
            if in_table and current_table_rows:
                article = _parse_table_rows(current_table_rows, current_section, current_sub)
                if article:
                    articles.append(article)
                current_table_rows = []
                in_table = False

    if in_table and current_table_rows:
        article = _parse_table_rows(current_table_rows, current_section, current_sub)
        if article:
            articles.append(article)

    return articles


def _parse_table_rows(rows: list, section: str, sub: str):
    fields = {}
    for row in rows:
        parts = [p.strip() for p in row.split("|")[1:-1]]
        if len(parts) >= 2:
            key = parts[0].replace("**", "").strip()
            val = " ".join(parts[1:]).strip()
            fields[key] = val

    title = fields.get("问题描述", sub)
    if not title or len(title) < 3:
        return None

    content_parts = [f"## {title}\n"]
    label_map = {
        "问题编号": "编号", "问题描述": "描述", "典型表现": "典型表现",
        "常见诱因": "常见原因", "排查命令": "排查命令",
        "解决方案": "解决方案", "预防措施": "预防措施",
    }
    for key, label in label_map.items():
        if key in fields:
            content_parts.append(f"### {label}\n{fields[key]}\n")

    category = "故障排查"
    for sec_key, cat in [("磁盘", "故障排查"), ("进程", "故障排查"), ("内存", "故障排查"),
                           ("网络", "故障排查"), ("服务", "操作指南"), ("启动", "故障排查"),
                           ("内核", "故障排查"), ("安全", "安全策略"), ("配置", "操作指南"),
                           ("日志", "故障排查"), ("国产", "操作指南"), ("实践", "操作指南")]:
        if sec_key in section:
            category = cat
            break

    severity = SEVERITY_MAP.get(category, "info")
    tags_str = ",".join(list(dict.fromkeys(
        re.findall(r"[一-龥a-zA-Z]{2,6}", section + title[:30])
    ))[:6])

    return {
        "title": title[:200],
        "category": category,
        "tags": tags_str,
        "content": "\n".join(content_parts)[:8000],
        "source": "imported",
        "severity": severity,
    }


async def main():
    engine = create_async_engine(settings.database_url, echo=False)

    with open(FILE_ZHISHIKU, encoding="utf-8") as f:
        zhishiku_text = f.read()
    with open(FILE_KYLIN, encoding="utf-8") as f:
        kylin_text = f.read()

    articles = parse_zhishiku(zhishiku_text)
    print(f"Parsed {len(articles)} articles from zhishiku.md")

    kylin_articles = parse_kylin_kb(kylin_text)
    print(f"Parsed {len(kylin_articles)} articles from kylin_os_knowledge_base.md")
    articles.extend(kylin_articles)

    print(f"Total: {len(articles)} articles")

    async with AsyncSession(engine) as db:
        old_count = (await db.execute(select(func.count()).select_from(KnowledgeArticle))).scalar() or 0
        await db.execute(delete(KnowledgeArticle))
        await db.commit()
        print(f"Cleared {old_count} existing articles")

        for a in articles:
            db.add(KnowledgeArticle(
                id=gen_id(),
                title=a["title"],
                category=a["category"],
                tags=a["tags"],
                content=a["content"],
                source=a["source"],
                severity=a["severity"],
            ))

        await db.commit()
        new_count = (await db.execute(select(func.count()).select_from(KnowledgeArticle))).scalar() or 0
        print(f"Inserted {new_count} articles")

    await engine.dispose()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
