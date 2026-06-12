"""知识库标题扫描与意图校正回归测试。"""
from pathlib import Path

from app.services.intent_classifier import classify_sync
from app.services.ops_scope import assess_ops_scope

SQL_PATH = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "sql"
    / "knowledge_articles.sql"
)


def test_install_duration_title_is_knowledge_qa():
    title = "装系统一般需要要多久时间"
    scope, _ = assess_ops_scope(title)
    assert scope == "in_scope"
    result = classify_sync(title)
    assert result["intent"] == "knowledge_qa"
    assert not result.get("out_of_scope")


def test_kb_sql_titles_pass_scope_scan():
    from scripts.scan_kb_scope import load_articles, scan_articles

    assert SQL_PATH.is_file(), f"missing KB dump: {SQL_PATH}"
    articles = load_articles(SQL_PATH)
    issues = scan_articles(articles)
    assert not issues, issues[:5]
