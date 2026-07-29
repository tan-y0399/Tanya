"""多模态 RAG 的轻量实现：文本 RAG + 图片资产候选 + 相关性评分。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeArticle
from app.models.multimodal import KnowledgeAsset
from app.services.knowledge_rag import knowledge_rag


def _tokens(text: str) -> set[str]:
    text = (text or "").lower()
    words = set(re.findall(r"[a-zA-Z0-9_-]{2,}", text))
    zh = re.findall(r"[\u4e00-\u9fff]+", text)
    for seg in zh:
        words.update(seg[i:i + 2] for i in range(max(len(seg) - 1, 0)))
    return {w for w in words if w}


def _score(query: str, text: str) -> float:
    q = _tokens(query)
    d = _tokens(text)
    if not q or not d:
        return 0.0
    return len(q & d) / max(len(q), 1)


def _concept_groups(query: str) -> List[set[str]]:
    q = (query or "").lower()
    groups: List[set[str]] = []
    if any(k in q for k in ("麒麟", "kylin")):
        groups.append({"麒麟", "kylin", "uos", "linux"})
    if any(k in q for k in ("虚拟机", "vm", "virtual machine", "libvirt", "virsh")):
        groups.append({"虚拟机", "vm", "virtual", "machine", "libvirt", "virsh", "qemu", "kvm"})
    if any(k in q for k in ("启动", "开机", "boot", "start", "startup")):
        groups.append({"启动", "开机", "boot", "start", "startup", "引导"})
    if any(k in q for k in ("失败", "无法", "fail", "failed", "failure", "error")):
        groups.append({"失败", "无法", "异常", "报错", "fail", "failed", "failure", "error"})
    if any(k in q for k in ("登录循环", "反复登录", "跳回登录", "login loop", "lightdm", "gdm")):
        groups.append({"登录循环", "反复登录", "跳回登录", "login", "lightdm", "gdm", "xauthority", "会话"})
    if any(k in q for k in ("黑屏", "闪一下", "图形界面", "3d加速", "显示", "xorg", "ukui")):
        groups.append({"黑屏", "闪退", "图形界面", "3d", "显示", "xorg", "ukui", "显卡", "桌面"})
    return groups


def _concept_score(query: str, text: str) -> float:
    groups = _concept_groups(query)
    if not groups:
        return 0.5
    lowered = (text or "").lower()
    matched = 0
    for group in groups:
        if any(term in lowered for term in group):
            matched += 1
    return matched / max(len(groups), 1)


def _rerank_text_results(query: str, results: List[Dict[str, Any]], top_k: int) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    concept_group_count = len(_concept_groups(query))
    # A broad domain hit such as only "麒麟" is not enough for a query that also
    # explicitly mentions a virtual machine or a concrete failure symptom.
    min_concept = 0.5 if concept_group_count == 0 else (1.0 if concept_group_count <= 2 else 0.66)
    for item in results or []:
        haystack = "\n".join([
            str(item.get("title") or ""),
            str(item.get("category") or ""),
            str(item.get("snippet") or ""),
        ])
        lexical = _score(query, haystack)
        concept = _concept_score(query, haystack)
        original = float(item.get("score") or 0)
        final_score = round(original * 0.45 + lexical * 0.3 + concept * 0.25, 4)
        enriched = {
            **item,
            "rerank_score": final_score,
            "lexical_score": round(lexical, 4),
            "concept_score": round(concept, 4),
        }
        if final_score >= 0.14 and concept >= min_concept:
            accepted.append(enriched)
        else:
            enriched["reject_reason"] = (
                f"相关性不足（概念覆盖 {concept:.2f}，要求 {min_concept:.2f}），未进入回答上下文"
            )
            rejected.append(enriched)
    accepted.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    rejected.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return accepted[:top_k], rejected[:top_k]


def _context_from_results(results: List[Dict[str, Any]]) -> str:
    if not results:
        return ""
    lines = ["## 相关知识库内容\n"]
    for i, r in enumerate(results[:3], 1):
        lines.append(
            f"### [{i}] {r.get('title', '')}\n"
            f"> 分类: {r.get('category', '')} | 重排相关度: {r.get('rerank_score', r.get('score', 0))}\n\n"
            f"{r.get('snippet', '')}\n"
        )
    return "\n".join(lines)


async def ensure_text_index(db: AsyncSession) -> None:
    if knowledge_rag._initialized:
        return
    result = await db.execute(select(KnowledgeArticle))
    articles = [
        {
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "category": a.category,
            "tags": a.tags,
        }
        for a in result.scalars().all()
    ]
    if articles:
        knowledge_rag.build_index(articles)


async def search_multimodal_knowledge(
    db: AsyncSession,
    query: str,
    vision_summaries: List[Dict[str, Any]] | None = None,
    *,
    top_k: int = 5,
) -> Dict[str, Any]:
    await ensure_text_index(db)
    vision_text = "\n".join(v.get("summary", "") for v in (vision_summaries or []))
    mixed_query = f"{query}\n{vision_text}".strip()

    raw_text_results = knowledge_rag.search(mixed_query, top_k=max(top_k * 3, 10)) if knowledge_rag._initialized else []
    text_results, rejected_text_results = _rerank_text_results(mixed_query, raw_text_results, top_k)
    context = _context_from_results(text_results)

    asset_rows = (await db.execute(select(KnowledgeAsset))).scalars().all()
    image_results = []
    for asset in asset_rows:
        haystack = " ".join([
            asset.title or "",
            asset.description or "",
            asset.tags or "",
            str(asset.meta_json or ""),
        ])
        concept = _concept_score(mixed_query, haystack)
        s = _score(mixed_query, haystack) * 0.65 + concept * 0.25 + float(asset.score_hint or 0)
        if s >= 0.08 and concept >= 0.25:
            image_results.append({
                "id": asset.id,
                "title": asset.title or asset.filename,
                "description": asset.description or "",
                "url": asset.public_url or asset.source_url,
                "score": round(s, 4),
                "source": "knowledge_asset",
            })
    image_results.sort(key=lambda x: x["score"], reverse=True)

    # 兼容项目已有 docs/tupian 图片：作为低置信候选，避免完全没有配图来源。
    if not image_results:
        docs_img = Path(__file__).resolve().parents[3] / "docs" / "tupian"
        if docs_img.exists():
            for path in list(docs_img.glob("*.*"))[:6]:
                image_results.append({
                    "id": path.stem,
                    "title": path.name,
                    "description": "项目文档图片候选，未建立语义标签，需人工确认相关性",
                    "url": "",
                    "localPath": str(path),
                    "score": 0.05,
                    "source": "docs_image_fallback",
                })

    return {
        "query": mixed_query,
        "context": context,
        "text_results": text_results,
        "rejected_text_results": rejected_text_results,
        "image_results": image_results[:top_k],
        "has_high_confidence_text": any(r.get("rerank_score", 0) >= 0.25 for r in text_results),
        "has_high_confidence_image": any(r.get("score", 0) >= 0.25 for r in image_results),
        "low_confidence_reason": "" if text_results else "知识库召回内容与用户问题相关性不足，已建议外部资料专家补充。",
    }
