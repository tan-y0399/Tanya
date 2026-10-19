"""
将 deploy/sql 与 deploy/knowledge 导入当前数据库。

用法:
  cd backend
  python scripts/import_deploy_data.py

导入内容:
  - deploy/sql/tool_configs.sqlite.sql  （或 PostgreSQL 版）
  - deploy/sql/knowledge_articles.sql   （银河麒麟运维知识库，约 100 篇）
  - deploy/knowledge/*.md               （Linux 命令风险分级等）
  - deploy/sql/users.sql                （演示账号，按 username  upsert）
  - deploy/sql/servers.sql              （默认服务器，按 name upsert）
"""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, engine, init_db
from app.models.knowledge import KnowledgeArticle
from app.models.server import Server
from app.models.tool_config import ToolConfig
from app.models.user import User

ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SQL = ROOT / "deploy" / "sql"
DEPLOY_KB = ROOT / "deploy" / "knowledge"


def _is_sqlite() -> bool:
    return "sqlite" in settings.database_url


def _sqlite_db_path() -> Path:
    url = settings.database_url
    # sqlite+aiosqlite:///D:/path/db or sqlite+aiosqlite:////app/...
    path = url.split("sqlite+aiosqlite:///")[-1]
    return Path(path)


def parse_pg_string(text: str, i: int) -> Tuple[str, int]:
    if text[i] != "'":
        raise ValueError(f"expected quote at {i}")
    i += 1
    chars: List[str] = []
    while i < len(text):
        ch = text[i]
        if ch == "'":
            if i + 1 < len(text) and text[i + 1] == "'":
                chars.append("'")
                i += 2
                continue
            return "".join(chars), i + 1
        chars.append(ch)
        i += 1
    raise ValueError("unterminated SQL string")


def parse_pg_value(text: str, i: int) -> Tuple[Any, int]:
    while i < len(text) and text[i] in " \t\r\n,":
        i += 1
    if i >= len(text):
        raise ValueError("unexpected end while parsing value")
    ch = text[i]
    if ch == "'":
        return parse_pg_string(text, i)
    if ch == "(":
        raise ValueError("nested tuple not supported")
    j = i
    while j < len(text) and text[j] not in ",)":
        j += 1
    raw = text[i:j].strip()
    if raw.lower() in ("null",):
        return None, j
    if re.fullmatch(r"-?\d+", raw):
        return int(raw), j
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw), j
    return raw, j


def parse_pg_tuple(text: str, i: int) -> Tuple[List[Any], int]:
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if i >= len(text) or text[i] != "(":
        raise ValueError("expected '('")
    i += 1
    values: List[Any] = []
    while i < len(text):
        while i < len(text) and text[i] in " \t\r\n":
            i += 1
        if i < len(text) and text[i] == ")":
            return values, i + 1
        val, i = parse_pg_value(text, i)
        values.append(val)
    raise ValueError("unterminated tuple")


def extract_knowledge_rows(sql_text: str) -> List[List[Any]]:
    marker = 'INSERT INTO "public"."knowledge_articles" VALUES'
    alt_marker = "INSERT INTO knowledge_articles VALUES"
    rows: List[List[Any]] = []
    pos = 0
    while True:
        idx = sql_text.find(marker, pos)
        alt_idx = sql_text.find(alt_marker, pos) if idx < 0 else -1
        if idx < 0 and alt_idx < 0:
            break
        if idx < 0:
            idx = alt_idx
            start = idx + len(alt_marker)
        else:
            start = idx + len(marker)
        while start < len(sql_text) and sql_text[start] in " \t\r\n(":
            if sql_text[start] == "(":
                break
            start += 1
        if start >= len(sql_text) or sql_text[start] != "(":
            pos = idx + 1
            continue
        try:
            values, end = parse_pg_tuple(sql_text, start)
            if len(values) >= 7:
                rows.append(values)
            pos = end
        except ValueError:
            pos = idx + 1
    return rows


def parse_users_sql(sql_text: str) -> List[dict]:
    pattern = re.compile(
        r"INSERT INTO \"users\" .*?VALUES \('([^']+)', '([^']+)', '([^']+)', '([^']+)'\);",
        re.I,
    )
    users = []
    for m in pattern.finditer(sql_text):
        users.append({
            "id": m.group(1),
            "username": m.group(2),
            "password_hash": m.group(3),
            "role": m.group(4),
        })
    return users


def parse_servers_sql(sql_text: str) -> List[dict]:
    pattern = re.compile(
        r"INSERT INTO \"servers\" .*?VALUES \('([^']+)', '([^']+)', '([^']+)', (\d+), '([^']+)', '([^']*)', '([^']*)', '([^']*)', '([tf])', '([^']*)', '([^']*)', '([^']*)', '([^']*)'\);",
        re.I,
    )
    servers = []
    for m in pattern.finditer(sql_text):
        servers.append({
            "id": m.group(1),
            "name": m.group(2),
            "host": m.group(3),
            "port": int(m.group(4)),
            "username": m.group(5),
            "key_path": m.group(6) or "~/.ssh/id_rsa",
            "description": m.group(7),
            "tags": m.group(8),
            "is_default": m.group(9).lower() == "t",
            "status": m.group(10) or "unknown",
            "last_checked": m.group(11),
            "created_at": m.group(12),
            "updated_at": m.group(13),
        })
    return servers


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


async def import_tool_configs(db: AsyncSession) -> int:
    if _is_sqlite():
        sql_file = DEPLOY_SQL / "tool_configs.sqlite.sql"
        db_path = _sqlite_db_path()
        if not sql_file.is_file():
            print(f"[skip] 未找到 {sql_file}")
            return 0
        raw = sql_file.read_text(encoding="utf-8")
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript(raw)
            conn.commit()
        finally:
            conn.close()
        total = len((await db.execute(select(ToolConfig))).scalars().all())
        print(f"[tools] SQLite 导入完成，当前共 {total} 条")
        return total

    sql_file = DEPLOY_SQL / "tool_configs.postgresql.sql"
    if not sql_file.is_file():
        print(f"[skip] 未找到 {sql_file}")
        return 0
    raw = sql_file.read_text(encoding="utf-8")
    statements = [s.strip() for s in raw.split(";") if "INSERT" in s.upper()]
    n = 0
    for stmt in statements:
        if not stmt or "tool_configs" not in stmt:
            continue
        try:
            await db.execute(text(stmt))
            n += 1
        except Exception as e:
            if "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                print(f"[warn] tool SQL: {e}")
    await db.commit()
    total = len((await db.execute(select(ToolConfig))).scalars().all())
    print(f"[tools] PostgreSQL 导入完成，当前共 {total} 条")
    return total


async def import_knowledge_sql(db: AsyncSession) -> Tuple[int, int]:
    sql_file = DEPLOY_SQL / "knowledge_articles.sql"
    if not sql_file.is_file():
        print(f"[skip] 未找到 {sql_file}")
        return 0, 0
    rows = extract_knowledge_rows(sql_file.read_text(encoding="utf-8"))
    print(f"[knowledge/sql] 解析到 {len(rows)} 篇文章")
    inserted = updated = 0
    for row in rows:
        kid, title, category, tags, content, source, severity = row[:7]
        view_count = int(row[7]) if len(row) > 7 and row[7] is not None else 0
        created_at = _parse_dt(row[8]) if len(row) > 8 else None
        updated_at = _parse_dt(row[9]) if len(row) > 9 else None
        result = await db.execute(
            select(KnowledgeArticle).where(
                (KnowledgeArticle.id == kid) | (KnowledgeArticle.title == title)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.title = title
            existing.category = category
            existing.tags = tags or ""
            existing.content = content or ""
            existing.source = source or "imported"
            existing.severity = severity or "info"
            existing.view_count = view_count
            if created_at:
                existing.created_at = created_at
            if updated_at:
                existing.updated_at = updated_at
            updated += 1
        else:
            article = KnowledgeArticle(
                id=kid,
                title=title,
                category=category,
                tags=tags or "",
                content=content or "",
                source=source or "imported",
                severity=severity or "info",
                view_count=view_count,
            )
            if created_at:
                article.created_at = created_at
            if updated_at:
                article.updated_at = updated_at
            db.add(article)
            inserted += 1
    await db.commit()
    print(f"[knowledge/sql] 新增 {inserted}，更新 {updated}")
    return inserted, updated


async def import_knowledge_markdown(db: AsyncSession) -> Tuple[int, int]:
    scripts_dir = Path(__file__).parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from import_linux_command_risk import KB_PATH, parse_articles, _tags

    if not os.path.exists(KB_PATH):
        print(f"[skip] 未找到 Markdown: {KB_PATH}")
        return 0, 0
    text = Path(KB_PATH).read_text(encoding="utf-8")
    articles = parse_articles(text)
    inserted = updated = 0
    for a in articles:
        a["tags"] = _tags(a["title"], a["content"])
        result = await db.execute(
            select(KnowledgeArticle).where(KnowledgeArticle.title == a["title"])
        )
        existing = result.scalar_one_or_none()
        sev = "warning" if "L4" in a["content"] or "L5" in a["content"] else "info"
        if existing:
            existing.content = a["content"]
            existing.category = a["category"]
            existing.tags = a["tags"]
            existing.source = "imported_csdn_risk"
            existing.severity = sev
            updated += 1
        else:
            db.add(KnowledgeArticle(
                title=a["title"],
                category=a["category"],
                tags=a["tags"],
                content=a["content"],
                source="imported_csdn_risk",
                severity=sev,
            ))
            inserted += 1
    await db.commit()
    print(f"[knowledge/md] 新增 {inserted}，更新 {updated}（{Path(KB_PATH).name}）")
    return inserted, updated


async def import_users(db: AsyncSession) -> int:
    sql_file = DEPLOY_SQL / "users.sql"
    if not sql_file.is_file():
        return 0
    users = parse_users_sql(sql_file.read_text(encoding="utf-8"))
    n = 0
    for u in users:
        result = await db.execute(select(User).where(User.username == u["username"]))
        existing = result.scalar_one_or_none()
        if existing:
            existing.password_hash = u["password_hash"]
            existing.role = u["role"]
        else:
            db.add(User(**u))
        n += 1
    await db.commit()
    print(f"[users] 同步 {n} 个演示账号（admin / ty）")
    return n


async def import_servers(db: AsyncSession) -> int:
    sql_file = DEPLOY_SQL / "servers.sql"
    if not sql_file.is_file():
        return 0
    servers = parse_servers_sql(sql_file.read_text(encoding="utf-8"))
    n = 0
    for s in servers:
        host = settings.ssh_host or s["host"]
        username = settings.ssh_user or s["username"]
        key_path = settings.ssh_key_path or s["key_path"]
        result = await db.execute(
            select(Server).where((Server.id == s["id"]) | (Server.name == s["name"]))
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.host = host
            existing.port = s["port"]
            existing.username = username
            existing.key_path = key_path
            existing.description = s["description"]
            existing.tags = s["tags"]
            existing.is_default = s["is_default"]
        else:
            db.add(Server(
                id=s["id"],
                name=s["name"],
                host=host,
                port=s["port"],
                username=username,
                key_path=key_path,
                description=s["description"],
                tags=s["tags"],
                is_default=s["is_default"],
                status="unknown",
            ))
        n += 1
    await db.commit()
    print(f"[servers] 同步 {n} 条服务器配置（host 已对齐 .env）")
    return n


async def rebuild_rag(db: AsyncSession) -> None:
    try:
        from app.services.knowledge_rag import knowledge_rag
        result = await db.execute(select(KnowledgeArticle))
        articles = [
            {
                "id": row.id,
                "title": row.title,
                "content": row.content,
                "category": row.category,
                "tags": row.tags,
            }
            for row in result.scalars().all()
        ]
        if articles:
            knowledge_rag.build_index(articles)
            print(f"[rag] 索引已重建，共 {len(articles)} 篇")
    except Exception as e:
        print(f"[warn] RAG 索引重建跳过: {e}")


async def main() -> None:
    print("=" * 60)
    print("KylinOps deploy 数据导入")
    print(f"数据库: {settings.database_url}")
    print("=" * 60)

    await init_db()

    async with async_session() as db:
        await import_tool_configs(db)
        await import_knowledge_sql(db)
        await import_knowledge_markdown(db)
        await import_users(db)
        await import_servers(db)
        await rebuild_rag(db)

        k_count = (await db.execute(select(KnowledgeArticle))).scalars().all()
        t_count = (await db.execute(select(ToolConfig))).scalars().all()
        print("-" * 60)
        print(f"完成：知识库 {len(k_count)} 篇，工具 {len(t_count)} 个")
        print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
