#!/usr/bin/env python3
"""
扫描知识库标题，确保 assess_ops_scope 与 classify_sync 不会误拒运维问题。

用法:
  cd backend && .venv_linux/bin/python scripts/scan_kb_scope.py
  cd backend && .venv_linux/bin/python scripts/scan_kb_scope.py --sql ../deploy/sql/knowledge_articles.sql
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.intent_classifier import classify_sync  # noqa: E402
from app.services.ops_scope import assess_ops_scope  # noqa: E402

ALLOWED_INTENTS = frozenset({"knowledge_qa", "fault_analysis", "ops_query", "high_risk"})

INSERT_RE = re.compile(
    r'INSERT INTO "public"\."knowledge_articles" VALUES \('
    r"'([^']+)',\s*'((?:[^'\\]|\\.)*)',\s*'((?:[^'\\]|\\.)*)'"
)


def _unescape_sql(value: str) -> str:
    return value.replace("\\'", "'")


def load_articles(sql_path: Path) -> list[dict[str, str]]:
    text = sql_path.read_text(encoding="utf-8", errors="ignore")
    articles: list[dict[str, str]] = []
    for match in INSERT_RE.finditer(text):
        articles.append(
            {
                "id": match.group(1),
                "title": _unescape_sql(match.group(2)),
                "category": _unescape_sql(match.group(3)),
            }
        )
    return articles


def scan_articles(articles: list[dict[str, str]]) -> list[tuple[str, dict, str, str]]:
    issues: list[tuple[str, dict, str, str]] = []
    for article in articles:
        title = article["title"]
        scope, reason = assess_ops_scope(title)
        result = classify_sync(title)
        intent = result.get("intent", "")

        if scope == "out_of_scope" or result.get("out_of_scope"):
            issues.append(("out_of_scope", article, reason, intent))
        elif intent not in ALLOWED_INTENTS:
            issues.append(("wrong_intent", article, scope, intent))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan KB titles against ops scope and intent rules")
    parser.add_argument(
        "--sql",
        type=Path,
        default=BACKEND_ROOT.parent / "deploy" / "sql" / "knowledge_articles.sql",
        help="Path to knowledge_articles.sql dump",
    )
    args = parser.parse_args()

    if not args.sql.is_file():
        print(f"ERROR: SQL file not found: {args.sql}", file=sys.stderr)
        return 2

    articles = load_articles(args.sql)
    issues = scan_articles(articles)

    print(f"Scanned {len(articles)} articles from {args.sql}")
    print(f"Issues: {len(issues)}")
    for kind, article, detail, intent in issues:
        print(
            f"{kind} | [{article['category']}] {article['title'][:100]} | {detail} | {intent}"
        )

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
