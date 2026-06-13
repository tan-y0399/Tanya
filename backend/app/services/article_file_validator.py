"""知识库文章文件：格式诊断 + 内容解析（拖拽导入前校验）"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

ALLOWED_EXTENSIONS = {".md", ".markdown", ".json", ".txt"}

VALID_SEVERITIES = {"info", "warning", "critical"}


def _normalize_tags(tags: Any) -> str:
    if isinstance(tags, list):
        return ",".join(str(t).strip() for t in tags if str(t).strip())
    if isinstance(tags, str):
        return tags.strip()
    return ""


def _normalize_article(raw: Dict[str, Any], source: str = "file_import") -> Dict[str, Any] | None:
    title = (raw.get("title") or raw.get("name") or "").strip()
    content = (raw.get("content") or raw.get("body") or raw.get("text") or "").strip()
    if not title:
        return None
    if not content:
        content = title
    severity = (raw.get("severity") or "info").strip().lower()
    if severity not in VALID_SEVERITIES:
        severity = "info"
    return {
        "title": title[:500],
        "category": (raw.get("category") or "").strip()[:120],
        "tags": _normalize_tags(raw.get("tags"))[:500],
        "content": content,
        "severity": severity,
        "source": raw.get("source") or source,
    }


def _parse_json_content(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return [], [f"JSON 解析失败: {exc}"]

    items: List[Any]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if isinstance(data.get("articles"), list):
            items = data["articles"]
        else:
            items = [data]
    else:
        return [], ["JSON 根节点必须是对象或数组"]

    articles: List[Dict[str, Any]] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"第 {i + 1} 项不是对象，已跳过")
            continue
        normalized = _normalize_article(item)
        if normalized:
            articles.append(normalized)
        else:
            errors.append(f"第 {i + 1} 项缺少 title")
    return articles, errors


def _parse_frontmatter(text: str) -> List[Dict[str, Any]]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text.strip(), re.DOTALL)
    if not match:
        return []
    meta_raw, body = match.group(1), match.group(2).strip()
    meta: Dict[str, Any] = {}
    for line in meta_raw.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower()
        val = val.strip().strip('"').strip("'")
        if key == "tags" and "," in val:
            meta["tags"] = [t.strip() for t in val.split(",") if t.strip()]
        else:
            meta[key] = val
    if not meta.get("title"):
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if heading:
            meta["title"] = heading.group(1).strip()
    meta["content"] = body
    article = _normalize_article(meta)
    return [article] if article else []


def _parse_simple_markdown(text: str) -> List[Dict[str, Any]]:
    stripped = text.strip()
    if not stripped:
        return []

    heading = re.search(r"^#\s+(.+)$", stripped, re.MULTILINE)
    if heading:
        title = heading.group(1).strip()
        article = _normalize_article({"title": title, "content": stripped, "source": "markdown"})
        return [article] if article else []

    first_line = stripped.splitlines()[0].strip()
    if first_line and not first_line.startswith("#"):
        body = "\n".join(stripped.splitlines()[1:]).strip() or stripped
        article = _normalize_article({"title": first_line[:200], "content": body, "source": "markdown"})
        return [article] if article else []
    return []


def _parse_kylin_markdown(text: str) -> List[Dict[str, Any]]:
    """解析 ## 大类 / ### 条目 格式的运维知识库 Markdown"""
    from app.api.routes.knowledge import _determine_severity, _extract_tags, _normalize_category

    articles: List[Dict[str, Any]] = []
    sections = re.split(r"\n(?=## )", text)
    for section in sections:
        section_match = re.match(r"^##\s+(.+?)(?:\n|$)", section)
        if not section_match:
            continue
        category = _normalize_category(section_match.group(1).strip())
        subsections = re.split(r"\n(?=### )", section)
        for sub in subsections:
            sub_match = re.match(r"^###\s+(.+?)(?:\n|$)", sub)
            if not sub_match:
                continue
            title = sub_match.group(1).strip()
            content = sub.strip()
            if any(skip in title for skip in ["日志系统核心文件说明", "日志分析关键关键字", "kylin-sysassist"]):
                continue
            tags = _extract_tags(title, content, category)
            severity = _determine_severity(title, content)
            articles.append({
                "title": title,
                "category": category,
                "tags": ",".join(tags),
                "content": content,
                "source": "markdown_import",
                "severity": severity,
            })
    return articles


def _parse_faq_markdown(text: str) -> List[Dict[str, Any]]:
    """解析 zhishiku FAQ：分类 + 数字. 问题 + A: 答案"""
    from app.api.routes.knowledge import (
        _determine_faq_severity,
        _extract_faq_tags,
    )

    faq_categories = {
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

    lines = text.splitlines()
    articles: List[Dict[str, Any]] = []
    current_category = None
    current_question = ""
    current_answer_lines: List[str] = []
    in_answer = False

    def flush():
        nonlocal current_question, current_answer_lines, in_answer
        if current_question and current_answer_lines:
            answer = "\n".join(current_answer_lines).strip()
            if answer:
                faq_cat = faq_categories.get(current_category, "常见-" + (current_category or "其他"))
                content = f"## {current_question}\n\n**分类**: {current_category}\n\n{answer}"
                tags = _extract_faq_tags(current_category or "", current_question, answer)
                severity = _determine_faq_severity(current_question, answer)
                articles.append({
                    "title": current_question[:200],
                    "category": faq_cat,
                    "tags": ",".join(tags),
                    "content": content,
                    "source": "faq_import",
                    "severity": severity,
                })
        current_question = ""
        current_answer_lines = []
        in_answer = False

    for line_num, line in enumerate(lines):
        stripped = line.strip()
        cat_match = re.match(
            r"^(\d{1,2})\s+(安装问题|启动问题|登录问题|激活问题|权限问题|版本问题|软件安装|外设使用|手册问题|显示问题|网络问题|输入问题|挂卸载问题|应用问题|其他问题)\s*$",
            stripped,
        )
        if cat_match:
            flush()
            current_category = cat_match.group(2)
            continue
        if line_num == 0 and "银河麒麟" in stripped:
            continue
        q_match = re.match(r"^(\d{1,3})\.\s+(.+)", stripped)
        if q_match and current_category:
            flush()
            current_question = q_match.group(2).strip()
            in_answer = False
            continue
        if re.match(r"^A[：:]\s*", stripped):
            in_answer = True
            answer_text = re.sub(r"^A[：:]\s*", "", stripped)
            if answer_text:
                current_answer_lines.append(answer_text)
            continue
        if in_answer and current_question:
            current_answer_lines.append(stripped if stripped else "")

    flush()
    return articles


def parse_article_file(filename: str, content: str) -> List[Dict[str, Any]]:
    """从上传文件内容解析文章列表（多种格式自动识别）"""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    text = content or ""
    if not text.strip():
        return []

    if ext == ".json":
        articles, _ = _parse_json_content(text)
        return articles

    if text.strip().startswith("---"):
        front = _parse_frontmatter(text)
        if front:
            return front

    kylin = _parse_kylin_markdown(text)
    if len(kylin) >= 2:
        return kylin

    faq = _parse_faq_markdown(text)
    if len(faq) >= 2:
        return faq

    if len(kylin) == 1:
        return kylin
    if len(faq) == 1:
        return faq

    simple = _parse_simple_markdown(text)
    if simple:
        return simple

    return kylin or faq or []


def validate_article_file(filename: str, content: str) -> Dict[str, Any]:
    """诊断并解析知识库文件，返回结构化结果供前端展示。"""
    filename = (filename or "").strip()
    content = content or ""
    default_title = (filename.rsplit(".", 1)[0] if filename else "article")[:100]

    if not content.strip():
        return _fail("diagnose", "文件内容为空", default_title)

    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    if ext and ext not in ALLOWED_EXTENSIONS:
        return _fail(
            "diagnose",
            f"不支持的文件类型，请上传 {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            default_title,
        )

    diagnose_msgs = ["文件格式校验通过"]
    warnings: List[str] = []

    if ext == ".json":
        articles, json_errors = _parse_json_content(content)
        if json_errors:
            warnings.extend(json_errors)
    else:
        articles = parse_article_file(filename, content)

    if not articles:
        return _fail("parse", "未能从文件中解析出有效文章（需包含 title 与 content）", default_title, diagnose_msgs)

    diagnose_msgs.append(f"成功解析 {len(articles)} 篇文章")
    if len(articles) > 1:
        diagnose_msgs.append("检测到多篇条目，确认后将批量导入")

    preview = articles[0]
    return {
        "ok": True,
        "stage": "done",
        "mode": "batch" if len(articles) > 1 else "single",
        "articleCount": len(articles),
        "title": preview.get("title") or default_title,
        "category": preview.get("category") or "",
        "tags": preview.get("tags") or "",
        "content": preview.get("content") or "",
        "severity": preview.get("severity") or "info",
        "articles": articles,
        "diagnose": {"ok": True, "messages": diagnose_msgs, "errors": [], "warnings": warnings},
        "parse": {"ok": True, "articleCount": len(articles)},
    }


def _fail(
    stage: str,
    message: str,
    title: str,
    diagnose_msgs: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "stage": stage,
        "title": title,
        "diagnose": {
            "ok": False,
            "messages": diagnose_msgs or [],
            "errors": [message],
            "warnings": [],
        },
        "parse": {"ok": False, "error": message},
    }
