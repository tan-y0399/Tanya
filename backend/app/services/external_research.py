"""External research providers for the multimodal expert chain.

The service intentionally reads credentials only from environment-backed
settings. API keys must not be hard-coded in source or sent to the frontend.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"


def _tokens(text: str) -> set[str]:
    text = (text or "").lower()
    words = set(re.findall(r"[a-zA-Z0-9_.@/-]{2,}", text))
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        words.update(seg[i:i + 2] for i in range(max(len(seg) - 1, 0)))
        words.update(seg[i:i + 3] for i in range(max(len(seg) - 2, 0)))
    return {w for w in words if w}


def relevance_score(query: str, text: str) -> float:
    q = _tokens(query)
    d = _tokens(text)
    if not q or not d:
        return 0.0
    overlap = len(q & d) / max(len(q), 1)
    phrase_bonus = 0.0
    lowered = (text or "").lower()
    for phrase in ("麒麟", "虚拟机", "启动失败", "无法启动", "boot", "startup failure", "libvirt", "kylin"):
        if phrase in (query or "").lower() and phrase in lowered:
            phrase_bonus += 0.08
    return round(min(1.0, overlap + phrase_bonus), 4)


def _extract_url(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("url", "imageUrl", "image_url", "src", "link", "thumb", "thumbnail"):
            found = _extract_url(value.get(key))
            if found:
                return found
        return ""
    if isinstance(value, list):
        for item in value:
            found = _extract_url(item)
            if found:
                return found
        return ""
    text = str(value or "").strip()
    if text.startswith("http://") or text.startswith("https://") or text.startswith("data:image/"):
        return text
    return ""


def _normalize_items(data: Any, query: str, source: str) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        raw_items = (
            data.get("items")
            or data.get("results")
            or data.get("references")
            or data.get("search_results")
            or data.get("data", {}).get("items")
            or data.get("data", {}).get("results")
            or data.get("data", {}).get("references")
            or data.get("result", {}).get("items")
            or data.get("result", {}).get("results")
            or data.get("result", {}).get("references")
            or []
        )
        # 千帆 AI 搜索偶发把网页/图片拆在不同字段
        if not raw_items:
            for key in ("web", "image", "images", "aladdin"):
                nested = data.get(key) or data.get("data", {}).get(key) or []
                if isinstance(nested, list):
                    raw_items = nested
                    break
    elif isinstance(data, list):
        raw_items = data
    else:
        raw_items = []

    items: List[Dict[str, Any]] = []
    for i, item in enumerate(raw_items[:12]):
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or item.get("headline") or f"外部资料 {i + 1}"
        snippet = (
            item.get("snippet")
            or item.get("summary")
            or item.get("description")
            or item.get("content")
            or item.get("abstract")
            or ""
        )
        url = _extract_url(item.get("url") or item.get("link") or item.get("source_url") or item.get("sourceUrl"))
        image_url = _extract_url(
            item.get("image")
            or item.get("imageUrl")
            or item.get("image_url")
            or item.get("thumbnail")
            or item.get("thumb")
            or item.get("cover")
            or item.get("pic")
            or item.get("pictures")
        )
        if not image_url and any(k in item for k in ("height", "width", "image")):
            image_url = url
        # Some web-search records expose the article URL under an `image` object.
        # Treating that HTML page as an image produces broken Markdown images.
        if image_url and image_url == url and not re.search(
            r"\.(?:png|jpe?g|webp|gif|bmp|svg)(?:[?#]|$)", image_url, re.I
        ):
            image_url = ""
        score = relevance_score(query, f"{title}\n{snippet}\n{url}")
        if score < 0.05:
            continue
        items.append({
            "title": str(title)[:180],
            "snippet": str(snippet)[:600],
            "url": url,
            "imageUrl": image_url,
            "source": source,
            "score": score,
            "trusted": source in {"baidu", "generic_configured"},
        })
    items.sort(key=lambda x: x["score"], reverse=True)
    return items


def _pack_search_result(items: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
    return {
        "status": "ok",
        "provider": source,
        "items": items,
        "findings": [i for i in items if not i.get("imageUrl")][:8],
        "images": [i for i in items if i.get("imageUrl")][:8],
    }


async def _call_baidu_qianfan(
    *,
    api_url: str,
    api_key: str,
    query: str,
    need_image: bool,
) -> Dict[str, Any]:
    """百度千帆 AI 搜索（POST /v2/ai_search/web_search）。"""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    resource_filter: List[Dict[str, Any]] = [{"type": "web", "top_k": 10}]
    if need_image:
        resource_filter.append({"type": "image", "top_k": 8})
    payload = {
        "messages": [{"role": "user", "content": query}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": resource_filter,
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.post(api_url, json=payload, headers=headers)
        resp.raise_for_status()
        items = _normalize_items(resp.json(), query, "baidu")
        return _pack_search_result(items, "baidu")


async def _call_search_api(
    *,
    api_url: str,
    api_key: str,
    secret_key: str,
    query: str,
    need_image: bool,
    source: str,
) -> Dict[str, Any]:
    try:
        # 千帆官方接口：必须用 messages + search_source，不能走通用 q/query GET
        if source == "baidu" and "qianfan.baidubce.com" in (api_url or ""):
            return await _call_baidu_qianfan(
                api_url=api_url,
                api_key=api_key,
                query=query,
                need_image=need_image,
            )

        headers: Dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["X-API-Key"] = api_key
        if secret_key:
            headers["X-Secret-Key"] = secret_key
        params = {"q": query, "query": query, "type": "image" if need_image else "text"}
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.get(api_url, params=params, headers=headers)
            if resp.status_code in (400, 405):
                resp = await client.post(api_url, json=params, headers=headers)
            resp.raise_for_status()
            items = _normalize_items(resp.json(), query, source)
            return _pack_search_result(items, source)
    except Exception as exc:
        logger.warning(
            "external research failed provider=%s key=%s err=%s",
            source,
            _mask_secret(api_key),
            str(exc)[:160],
        )
        return {
            "status": "failed",
            "provider": source,
            "note": f"外部资料检索失败：{str(exc)[:120]}",
            "items": [],
            "findings": [],
            "images": [],
        }


async def search_external_knowledge(query: str, *, need_image: bool = False) -> Dict[str, Any]:
    if not getattr(settings, "enable_web_research", False):
        return {
            "status": "not_configured",
            "provider": "disabled",
            "note": "外部资料专家未启用；请配置 ENABLE_WEB_RESEARCH=true 以及搜索 API。",
            "needImage": need_image,
            "items": [],
            "findings": [],
            "images": [],
        }

    provider = (getattr(settings, "web_search_provider", "generic") or "generic").lower()
    if provider == "baidu":
        api_url = getattr(settings, "baidu_search_api_url", "") or getattr(settings, "web_search_api_url", "")
        api_key = getattr(settings, "baidu_search_api_key", "") or getattr(settings, "web_search_api_key", "")
        secret_key = getattr(settings, "baidu_search_secret_key", "") or getattr(settings, "web_search_secret_key", "")
        source = "baidu"
    else:
        api_url = getattr(settings, "web_search_api_url", "")
        api_key = getattr(settings, "web_search_api_key", "")
        secret_key = getattr(settings, "web_search_secret_key", "")
        source = "generic_configured"

    if not api_url:
        return {
            "status": "not_configured",
            "provider": provider,
            "note": "已启用外部资料专家，但尚未配置搜索 API URL。",
            "needImage": need_image,
            "items": [],
            "findings": [],
            "images": [],
        }

    return await _call_search_api(
        api_url=api_url,
        api_key=api_key,
        secret_key=secret_key,
        query=query,
        need_image=need_image,
        source=source,
    )
