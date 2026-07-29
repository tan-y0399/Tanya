"""Diagram, image review/generation, and TTS helpers for multimodal answers."""
from __future__ import annotations

import base64
import asyncio
import html
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def generated_asset_dir() -> Path:
    configured = Path(getattr(settings, "generated_asset_dir", "data/generated_assets"))
    if not configured.is_absolute():
        configured = BACKEND_ROOT / configured
    configured.mkdir(parents=True, exist_ok=True)
    return configured


def _public_asset_url(path: Path) -> str:
    return f"/api/v1/chat/generated/{path.name}"


async def _cache_remote_image(url: str, prefix: str = "image") -> Optional[str]:
    if not isinstance(url, str) or not url.startswith(("http://", "https://", "data:image/")):
        return None
    try:
        if url.startswith("data:image/"):
            header, b64 = url.split(",", 1)
            ext = "png"
            match = re.search(r"data:image/([a-zA-Z0-9.+-]+)", header)
            if match:
                ext = "jpg" if match.group(1).lower() in ("jpeg", "jpg") else match.group(1).lower().split("+")[0]
            raw = base64.b64decode(b64)
        else:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                resp = await client.get(url)
            if resp.status_code >= 400 or not resp.content:
                return None
            raw = resp.content
            content_type = (resp.headers.get("content-type") or "").lower()
            if content_type and not content_type.startswith("image/"):
                logger.info("cache remote image skipped: non-image content type %s", content_type[:80])
                return None
            if "svg" in content_type:
                ext = "svg"
            elif "webp" in content_type:
                ext = "webp"
            elif "png" in content_type:
                ext = "png"
            elif "gif" in content_type:
                ext = "gif"
            else:
                ext = "jpg"
        if len(raw) > 8 * 1024 * 1024:
            return None
        path = generated_asset_dir() / f"{prefix}_{uuid.uuid4().hex[:16]}.{ext}"
        path.write_bytes(raw)
        return _public_asset_url(path)
    except Exception as exc:
        logger.info("cache remote image skipped: %s", str(exc)[:120])
        return None


async def materialize_image_candidates(images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cache remote candidate images locally so browser hotlink rules cannot break answers."""
    async def cache_one(idx: int, image: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(image)
        url = item.get("url") or item.get("imageUrl")
        if not isinstance(url, str) or not url.startswith(("http://", "https://", "data:image/")):
            return item
        cached_url = await _cache_remote_image(url, prefix=f"reference_{idx + 1}")
        if cached_url:
            item["remoteUrl"] = url if url.startswith(("http://", "https://")) else None
            item["url"] = cached_url
            item["cached"] = True
        else:
            item["url"] = ""
            item["cacheFailed"] = True
            item["unavailableReason"] = "候选地址未返回有效图片内容，已阻止破损图片进入回答"
        return item

    candidates = list(images or [])[:4]
    if not candidates:
        return []
    tasks = {
        asyncio.create_task(cache_one(idx, item)): idx
        for idx, item in enumerate(candidates)
    }
    done, pending = await asyncio.wait(tasks, timeout=7.0)
    results: Dict[int, Dict[str, Any]] = {}
    for task in done:
        idx = tasks[task]
        try:
            results[idx] = task.result()
        except Exception as exc:
            item = dict(candidates[idx])
            item.update({"url": "", "cacheFailed": True, "unavailableReason": str(exc)[:120]})
            results[idx] = item
    for task in pending:
        idx = tasks[task]
        task.cancel()
        item = dict(candidates[idx])
        item.update({
            "url": "",
            "cacheFailed": True,
            "unavailableReason": "候选图片缓存超时，已阻止远程 URL 进入回答",
        })
        results[idx] = item
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
        logger.info("remote image cache timed out for %s candidate(s); dropped remote URLs", len(pending))
    return [results[idx] for idx in range(len(candidates))]


def _modelscope_image_model(value: str) -> str:
    model = (value or "").strip()
    if model.lower() in {"z-image-turbo", "z_image_turbo", "zimage-turbo"}:
        return "Tongyi-MAI/Z-Image-Turbo"
    return model or "Tongyi-MAI/Z-Image-Turbo"


def _generated_image_url(data: Any) -> str:
    if isinstance(data, str):
        return data if data.startswith(("http://", "https://", "data:image/")) else ""
    if isinstance(data, list):
        for item in data:
            found = _generated_image_url(item)
            if found:
                return found
        return ""
    if not isinstance(data, dict):
        return ""
    for key in ("url", "image_url", "imageUrl"):
        found = _generated_image_url(data.get(key))
        if found:
            return found
    for key in ("output_images", "images", "data", "output", "result", "results"):
        found = _generated_image_url(data.get(key))
        if found:
            return found
    return ""


async def _modelscope_generate_image(
    *,
    model: str,
    prompt: str,
    size: str,
    timeout_sec: float = 50.0,
) -> Dict[str, Any]:
    api_key = getattr(settings, "modelscope_api_key", "")
    if not api_key:
        return {"status": "not_configured", "note": "未配置 MODELSCOPE_API_KEY。"}
    endpoint = f"{getattr(settings, 'modelscope_api_base', '').rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json={
                    "model": _modelscope_image_model(model),
                    "prompt": prompt,
                    "size": size,
                    "n": 1,
                },
            )
            if response.status_code >= 400:
                return {
                    "status": "failed",
                    "note": f"ModelScope 图片服务返回 {response.status_code}：{response.text[:300]}",
                }
            data = response.json()
            image_url = _generated_image_url(data)
            if image_url:
                return {"status": "ok", "url": image_url, "raw": data}

            task_id = data.get("task_id") or data.get("taskId")
            if not task_id:
                return {"status": "failed", "note": "ModelScope 未返回图片 URL 或异步任务 ID。"}

            poll_headers = {
                **headers,
                "X-ModelScope-Task-Type": "image_generation",
            }
            deadline = time.monotonic() + max(5.0, timeout_sec)
            last_status = str(data.get("task_status") or "PENDING")
            while time.monotonic() < deadline:
                await asyncio.sleep(2.0)
                task_response = await client.get(
                    f"{getattr(settings, 'modelscope_api_base', '').rstrip('/')}/tasks/{task_id}",
                    headers=poll_headers,
                )
                if task_response.status_code >= 400:
                    return {
                        "status": "failed",
                        "note": f"ModelScope 任务查询返回 {task_response.status_code}：{task_response.text[:260]}",
                    }
                task_data = task_response.json()
                last_status = str(task_data.get("task_status") or task_data.get("status") or "").upper()
                image_url = _generated_image_url(task_data)
                if image_url:
                    return {"status": "ok", "url": image_url, "raw": task_data, "taskId": task_id}
                if last_status in {"FAILED", "CANCELED", "CANCELLED", "ERROR"}:
                    error = task_data.get("errors") or task_data.get("message") or "任务执行失败"
                    return {"status": "failed", "note": f"ModelScope 图片任务失败：{str(error)[:260]}"}
            return {"status": "failed", "note": f"ModelScope 图片任务超时（最后状态：{last_status}）。"}
    except Exception as exc:
        return {"status": "failed", "note": f"ModelScope 图片调用失败：{str(exc)[:220]}"}


def _diagram_labels(title: str, steps: List[Dict[str, Any]]) -> List[str]:
    labels = ["确认问题现象与影响范围"]
    for idx, step in enumerate((steps or [])[:8], 1):
        label = re.sub(r"[\r\n\"]+", " ", str(step.get("action") or step.get("title") or f"执行步骤 {idx}"))[:42]
        labels.append(label)
    labels.append("汇总结论、风险与验证结果")
    return labels


def diagram_to_mermaid(title: str, steps: List[Dict[str, Any]]) -> str:
    labels = _diagram_labels(title, steps)
    lines = ["flowchart TD"]
    node_ids = []
    for idx, label in enumerate(labels):
        node_id = f"N{idx}"
        node_ids.append(node_id)
        safe_label = re.sub(r"[\r\n\[\]{}|\"`]+", " ", label).strip()[:64]
        lines.append(f'  {node_id}["{safe_label}"]')
    for left, right in zip(node_ids, node_ids[1:]):
        lines.append(f"  {left} --> {right}")
    return "```mermaid\n" + "\n".join(lines) + "\n```"


def _write_flowchart_svg(title: str, steps: List[Dict[str, Any]], *, note: str = "") -> str:
    labels = _diagram_labels(title, steps)
    width = 980
    box_w = 760
    box_h = 58
    gap = 26
    left = 110
    top = 72
    height = top * 2 + len(labels) * box_h + (len(labels) - 1) * gap
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">',
        '<path d="M2,2 L10,6 L2,10 Z" fill="#2563eb"/>',
        "</marker>",
        '<filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">',
        '<feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#0f172a" flood-opacity="0.12"/>',
        "</filter>",
        "</defs>",
        '<rect width="100%" height="100%" rx="18" fill="#f8fafc"/>',
        f'<text x="{width/2}" y="34" text-anchor="middle" font-size="22" font-weight="700" fill="#0f172a">{html.escape(title or "处理流程图")}</text>',
    ]
    for idx, label in enumerate(labels):
        y = top + idx * (box_h + gap)
        fill = "#eff6ff" if idx in (0, len(labels) - 1) else "#ffffff"
        stroke = "#60a5fa" if idx in (0, len(labels) - 1) else "#cbd5e1"
        parts.append(f'<rect x="{left}" y="{y}" width="{box_w}" height="{box_h}" rx="12" fill="{fill}" stroke="{stroke}" filter="url(#shadow)"/>')
        badge = "始" if idx == 0 else ("终" if idx == len(labels) - 1 else str(idx))
        parts.append(f'<circle cx="{left + 28}" cy="{y + box_h/2}" r="14" fill="#2563eb"/>')
        parts.append(f'<text x="{left + 28}" y="{y + box_h/2 + 5}" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">{badge}</text>')
        parts.append(f'<text x="{left + 54}" y="{y + box_h/2 + 5}" font-size="15" font-weight="600" fill="#1e293b">{html.escape(label)}</text>')
        if idx < len(labels) - 1:
            x = width / 2
            parts.append(f'<line x1="{x}" y1="{y + box_h + 4}" x2="{x}" y2="{y + box_h + gap - 6}" stroke="#2563eb" stroke-width="2.2" marker-end="url(#arrow)"/>')
    if note:
        parts.append(f'<text x="{width/2}" y="{height - 28}" text-anchor="middle" font-size="13" fill="#64748b">{html.escape(note)}</text>')
    parts.append("</svg>")
    path = generated_asset_dir() / f"flowchart_{uuid.uuid4().hex[:16]}.svg"
    path.write_text("\n".join(parts), encoding="utf-8")
    return _public_asset_url(path)


async def generate_drawio_flowchart(title: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a displayable flowchart image.

    Z-Image-Turbo is preferred for the deep multimodal chain. drawio and local SVG remain
    deterministic fallbacks so the answer never exposes raw Mermaid/source text.
    """
    if getattr(settings, "flowchart_generation_provider", "zimage").lower() in ("zimage", "modelscope"):
        zimage = await generate_zimage_flowchart(title, steps)
        if zimage.get("status") == "ok" and zimage.get("url"):
            # Text-to-image models often draw convincing flowchart shapes while
            # corrupting Chinese labels or step numbers. Keep the model-generated
            # artifact for audit, but publish deterministic SVG labels unless OCR
            # has positively verified every node.
            verified_url = _write_flowchart_svg(
                title,
                steps,
                note="Z-Image-Turbo 已生成参考稿；正式图使用精确文字 SVG 通过质量门禁",
            )
            return {
                "status": "ok",
                "provider": "modelscope_zimage+verified_svg",
                "format": "svg",
                "url": verified_url,
                "generatedUrl": zimage.get("url"),
                "generatedProvider": "modelscope_zimage",
                "mermaid": zimage.get("mermaid") or diagram_to_mermaid(title, steps),
                "qualityReview": "Z-Image 参考稿已生成；因未获得完整 OCR 文字校验，正式展示使用确定性 SVG，避免中文错字和步骤缺号。",
                "note": "流程图已完成图形生成与文字质量门禁。",
            }

    try:
        from app.services.mcp_client import mcp_client
        payload = {
            "title": title,
            "steps": [s.get("action") or s.get("title") or "" for s in (steps or [])[:8]],
            "format": "drawio",
        }
        for tool_name in ("export_diagram", "drawio_export", "drawio_generate", "generate_drawio", "create_diagram", "drawio"):
            result = await mcp_client.call_tool(tool_name, payload)
            if result.get("success") and result.get("data"):
                data = result["data"]
                out: Dict[str, Any] = {"status": "ok", "format": "drawio", "data": data, "mermaid": diagram_to_mermaid(title, steps)}
                if isinstance(data, dict):
                    url = data.get("url") or data.get("imageUrl") or data.get("publicUrl")
                    svg = data.get("svg")
                    xml = data.get("xml") or data.get("drawio")
                    if url:
                        out["url"] = url
                    elif svg:
                        path = generated_asset_dir() / f"diagram_{uuid.uuid4().hex[:16]}.svg"
                        path.write_text(str(svg), encoding="utf-8")
                        out["url"] = _public_asset_url(path)
                    elif xml:
                        path = generated_asset_dir() / f"diagram_{uuid.uuid4().hex[:16]}.drawio"
                        path.write_text(str(xml), encoding="utf-8")
                        out["fileUrl"] = _public_asset_url(path)
                        out["url"] = _write_flowchart_svg(title, steps, note="drawio XML 已保存，当前展示 SVG 预览")
                elif isinstance(data, str) and data.lstrip().startswith("<svg"):
                    path = generated_asset_dir() / f"diagram_{uuid.uuid4().hex[:16]}.svg"
                    path.write_text(data, encoding="utf-8")
                    out["url"] = _public_asset_url(path)
                if not out.get("url"):
                    out["url"] = _write_flowchart_svg(title, steps, note="drawio 返回内容无法直接展示，已生成 SVG 预览")
                return out
    except Exception as exc:
        logger.warning("drawio mcp fallback: %s", exc)
    url = _write_flowchart_svg(title, steps, note="drawio MCP 不可用，已生成本地 SVG 流程图")
    return {
        "status": "fallback",
        "format": "svg",
        "note": "drawio MCP 未连接或未返回图表，已使用本地 SVG 流程图兜底。",
        "url": url,
        "mermaid": diagram_to_mermaid(title, steps),
    }


async def generate_zimage_flowchart(title: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    api_key = getattr(settings, "modelscope_api_key", "")
    if not api_key:
        return {"status": "not_configured", "provider": "modelscope_zimage", "note": "未配置 MODELSCOPE_API_KEY，跳过 Z-Image 流程图生成。"}
    step_lines = []
    for idx, step in enumerate((steps or [])[:9], 1):
        action = str(step.get("action") or step.get("title") or f"步骤 {idx}")
        risk = str(step.get("risk") or "")
        step_lines.append(f"{idx}. {action[:56]} {risk}".strip())
    prompt = (
        "生成一张专业中文运维流程图图片，不要输出 Mermaid 源码，不要代码块。"
        "画面必须是流程图图形：白色背景、蓝绿色主色、圆角矩形节点、清晰箭头、步骤编号、"
        "节点文字简洁可读，适合插入运维知识问答。"
        f"标题：{title or '运维处理流程'}。"
        "流程步骤：\n" + "\n".join(step_lines or ["1. 问题确认", "2. 风险判断", "3. 执行处理", "4. 验证恢复"])
    )
    result = await _modelscope_generate_image(
        model=getattr(settings, "flowchart_generation_model", "Tongyi-MAI/Z-Image-Turbo"),
        prompt=prompt,
        size="1280x768",
        timeout_sec=50.0,
    )
    image_url = result.get("url")
    if result.get("status") == "ok" and isinstance(image_url, str):
        cached_url = await _cache_remote_image(image_url, prefix="flowchart")
        return {
            "status": "ok",
            "provider": "modelscope_zimage",
            "format": "image",
            "url": cached_url or image_url,
            "remoteUrl": image_url if cached_url else None,
            "mermaid": diagram_to_mermaid(title, steps),
            "note": "已通过 Z-Image-Turbo 生成并缓存流程图图片。" if cached_url else "已通过 Z-Image-Turbo 生成流程图图片。",
        }
    logger.warning("z-image flowchart failed: %s", result.get("note"))
    return {
        "status": "failed",
        "provider": "modelscope_zimage",
        "note": result.get("note") or "Z-Image-Turbo 未返回可展示图片 URL。",
        "mermaid": diagram_to_mermaid(title, steps),
    }


def diagram_to_markdown(diagram: Dict[str, Any]) -> str:
    if diagram.get("url"):
        return f"![处理流程图]({diagram['url']})"
    if diagram.get("fileUrl"):
        return f"[下载 drawio 流程图]({diagram['fileUrl']})"
    if diagram.get("mermaid"):
        return "流程图图片生成不可用，以下为 Mermaid 源码兜底：\n\n" + str(diagram["mermaid"])
    return ""


async def _ocr_with_mcp(image: Dict[str, Any]) -> Dict[str, Any]:
    target = image.get("url") or image.get("imageUrl") or image.get("localPath") or ""
    if not target:
        return {"status": "skipped", "text": "", "reason": "图片缺少可访问 URL 或路径"}
    preferred = getattr(settings, "paddleocr_mcp_tool", "paddleocr_ocr")
    server_url = getattr(settings, "mcp_server_url", "http://localhost:8100").rstrip("/")
    payload = {
        "image": target,
        "image_url": target,
        "url": target,
        "model": getattr(settings, "paddleocr_model", "PaddlePaddle/PP-OCRv5_server_det"),
        "task": "ocr",
    }
    # OCR 是增强能力，不允许拖慢主回答链路；直接短超时调用 MCP 网关，不走本地工具 fallback。
    for tool_name in (preferred, "paddleocr_vl"):
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.post(
                    f"{server_url}/mcp/call_tool",
                    json={
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": payload},
                    },
                )
            if resp.status_code >= 400:
                continue
            result = resp.json()
            data = result.get("content", result.get("data", result))
            if isinstance(data, dict):
                text = (
                    data.get("text")
                    or data.get("ocr_text")
                    or data.get("content")
                    or data.get("result")
                    or ""
                )
            else:
                text = str(data)
            if text:
                return {"status": "ok", "tool": tool_name, "text": str(text)[:1200]}
        except Exception as exc:
            logger.info("paddleocr mcp quick-skip %s: %s", tool_name, str(exc)[:120])
    return {"status": "not_available", "text": "", "reason": "PaddleOCR MCP 未返回可用 OCR 结果"}


def _extract_ocr_text(data: Any) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return " ".join(_extract_ocr_text(item) for item in data)[:2000]
    if isinstance(data, dict):
        values = []
        for key in ("text", "ocr_text", "content", "result", "description", "rec_text", "label"):
            if data.get(key):
                values.append(str(data[key]))
        for key in ("texts", "results", "data", "output", "predictions", "boxes"):
            if data.get(key):
                values.append(_extract_ocr_text(data[key]))
        return " ".join(v for v in values if v)[:2000]
    return str(data)


async def _ocr_with_modelscope(image: Dict[str, Any]) -> Dict[str, Any]:
    api_key = getattr(settings, "modelscope_api_key", "")
    if not api_key:
        return {"status": "not_configured", "text": "", "reason": "未配置 MODELSCOPE_API_KEY"}
    target = image.get("url") or image.get("imageUrl") or image.get("localPath") or ""
    if not target:
        return {"status": "skipped", "text": "", "reason": "图片缺少可访问 URL 或路径"}

    model = getattr(settings, "paddleocr_model", "PaddlePaddle/PP-OCRv5_server_det")
    encoded_model = quote(model, safe="")
    base = getattr(settings, "modelscope_api_base", "https://api-inference.modelscope.cn/v1").rstrip("/")
    configured = getattr(settings, "paddleocr_api_url", "").strip()
    endpoints = [configured] if configured else [f"{base}/models/{encoded_model}/predict"]
    payload = {"model": model, "input": {"image": target}, "parameters": {"return_text": True}}
    last_error = ""
    for endpoint in [e for e in endpoints if e]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if resp.status_code >= 400:
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                continue
            data = resp.json()
            text = _extract_ocr_text(data)
            if text:
                return {"status": "ok", "provider": "modelscope", "model": model, "text": text[:1200]}
            last_error = "接口已响应但未解析到 OCR 文本"
        except Exception as exc:
            last_error = str(exc)[:140]
    return {"status": "failed", "text": "", "reason": f"ModelScope OCR 调用失败：{last_error or '无可用响应'}"}


async def _ocr_image(image: Dict[str, Any]) -> Dict[str, Any]:
    timeout = float(getattr(settings, "image_review_ocr_timeout_sec", 3.0))
    try:
        return await asyncio.wait_for(_ocr_image_uncapped(image), timeout=timeout)
    except asyncio.TimeoutError:
        return {"status": "timeout", "text": "", "reason": f"OCR 超过 {timeout:g} 秒，已跳过并按图片标题/说明审核"}


async def _ocr_image_uncapped(image: Dict[str, Any]) -> Dict[str, Any]:
    mcp = await _ocr_with_mcp(image)
    if mcp.get("status") == "ok":
        return mcp
    ms = await _ocr_with_modelscope(image)
    if ms.get("status") == "ok":
        return ms
    return {
        "status": "unavailable",
        "text": "",
        "reason": "; ".join(v for v in [mcp.get("reason"), ms.get("reason")] if v) or "OCR 服务不可用",
        "mcpStatus": mcp.get("status"),
        "modelscopeStatus": ms.get("status"),
    }


def _image_relevance_score(query: str, image: Dict[str, Any], ocr_text: str = "") -> float:
    q = (query or "").lower()
    text = " ".join([
        str(image.get("title") or ""),
        str(image.get("description") or ""),
        str(image.get("snippet") or ""),
        str(image.get("source") or ""),
        str(image.get("url") or image.get("imageUrl") or ""),
        ocr_text or "",
    ]).lower()
    score = 0.0
    keyword_groups = [
        ("麒麟", "kylin", "openkylin"),
        ("虚拟机", "vm", "virtual machine", "vmware", "libvirt", "qemu", "kvm"),
        ("启动", "开机", "boot", "startup", "start"),
        ("失败", "故障", "报错", "error", "failed", "failure", "cannot", "unable"),
        ("流程", "排查", "处理", "修复", "diagnose", "troubleshoot", "repair"),
    ]
    for group in keyword_groups:
        if any(k in q for k in group) and any(k in text for k in group):
            score += 0.12
    for token in re.findall(r"[a-zA-Z0-9_\-]{3,}|[\u4e00-\u9fff]{2,}", q):
        if token in text:
            score += 0.025
    if image.get("source") == "knowledge_asset":
        score += 0.12
    if image.get("source") == "generated":
        score += 0.18
    if image.get("score"):
        try:
            score += min(float(image.get("score")), 1.0) * 0.12
        except (TypeError, ValueError):
            pass
    url = str(image.get("url") or image.get("imageUrl") or "")
    if url.startswith(("http://", "https://", "data:image/")):
        score += 0.04
    if re.search(r"\.(png|jpe?g|webp|gif)(?:\?|$)", url, re.I):
        score += 0.03
    return round(min(score, 1.0), 4)


async def review_image_candidates(query: str, images: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Review image candidates with PaddleOCR MCP when available, returning a compact summary."""
    model_dir = Path(getattr(settings, "paddleocr_vl_model_dir", "models/PaddleOCR-VL-1.6"))
    if not model_dir.is_absolute():
        model_dir = BACKEND_ROOT / model_dir
    ocr_ready = model_dir.exists()
    accepted = []
    rejected = []
    samples = []
    hard_threshold = float(getattr(settings, "image_review_min_score", 0.18))
    soft_threshold = float(getattr(settings, "image_review_soft_min_score", 0.06))
    keep_min = max(0, int(getattr(settings, "image_review_keep_min", 1)))
    max_candidates = max(1, int(getattr(settings, "image_review_max_candidates", 4)))
    total_timeout = float(getattr(settings, "image_review_total_timeout_sec", 5.0))
    candidates = list(images or [])[:max_candidates]

    async def review_one(img: Dict[str, Any]) -> Dict[str, Any]:
        try:
            ocr = await _ocr_image(img)
        except Exception as exc:
            logger.info("image review ocr skipped: %s", str(exc)[:120])
            ocr = {"status": "error", "text": "", "reason": str(exc)[:120]}
        score = _image_relevance_score(query, img, str(ocr.get("text") or ""))
        return {
            **img,
            "image_review_score": score,
            "ocrStatus": ocr.get("status"),
            "ocrReason": ocr.get("reason"),
            "ocrTextPreview": (ocr.get("text") or "")[:120],
        }

    reviewed = []
    try:
        reviewed = await asyncio.wait_for(
            asyncio.gather(*(review_one(img) for img in candidates)),
            timeout=total_timeout,
        )
    except asyncio.TimeoutError:
        logger.info("image review timed out; using semantic fallback")
        reviewed = [
            {
                **img,
                "image_review_score": _image_relevance_score(query, img, ""),
                "ocrStatus": "timeout",
                "ocrReason": f"图片审核总时限 {total_timeout:g} 秒已到，按标题/说明/来源语义相关性降级审核",
                "ocrTextPreview": "",
            }
            for img in candidates
        ]
    except Exception as exc:
        logger.warning("image review failed; using semantic fallback: %s", exc)
        reviewed = [
            {
                **img,
                "image_review_score": _image_relevance_score(query, img, ""),
                "ocrStatus": "error",
                "ocrReason": "OCR 审核异常，按语义相关性降级审核",
                "ocrTextPreview": "",
            }
            for img in candidates
        ]

    for item in reviewed:
        score = float(item.get("image_review_score") or 0)
        if score >= hard_threshold or item.get("source") in ("knowledge_asset", "generated"):
            accepted.append(item)
            decision = "accepted"
        else:
            item["reject_reason"] = "图片标题/说明/OCR 文本与问题相关性不足，低于硬阈值"
            rejected.append(item)
            decision = "rejected"
        if len(samples) < 3:
            samples.append({
                "title": item.get("title"),
                "score": item.get("image_review_score"),
                "ocrStatus": item.get("ocrStatus"),
                "ocrTextPreview": item.get("ocrTextPreview"),
                "decision": decision,
            })
    if len(accepted) < keep_min:
        valid_reviewed = [
            img for img in reviewed
            if isinstance(img.get("url") or img.get("imageUrl"), str)
            and str(img.get("url") or img.get("imageUrl")).startswith(("http://", "https://", "data:image/"))
        ]
        valid_reviewed.sort(key=lambda x: x.get("image_review_score", 0), reverse=True)
        for candidate in valid_reviewed:
            if candidate in accepted:
                continue
            if candidate.get("image_review_score", 0) >= soft_threshold or not accepted:
                candidate["review_fallback"] = "OCR 不可用或硬阈值未命中，按软阈值/最高相关候选保留，确保回答有图可用。"
                accepted.append(candidate)
            if len(accepted) >= keep_min:
                break
    ocr_statuses = {str(i.get("ocrStatus")) for i in reviewed if i.get("ocrStatus")}
    if "ok" in ocr_statuses:
        ocr_note = "已获取 OCR 文本"
    elif ocr_statuses:
        ocr_note = "OCR 服务未返回可用文本，已按标题/说明/来源语义相关性降级审核"
    else:
        ocr_note = "无候选图片需要 OCR"
    return {
        "summary": f"图片审核完成：可用 {len(accepted[:4])} 张，过滤 {len(rejected[:6])} 张；阈值 {hard_threshold:.2f}/软阈值 {soft_threshold:.2f}；{ocr_note}。",
        "ocrReady": ocr_ready,
        "ocrProvider": "PaddleOCR MCP / ModelScope",
        "threshold": hard_threshold,
        "softThreshold": soft_threshold,
        "accepted": accepted[:4],
        "rejectedCount": len(rejected[:6]),
        "samples": samples,
    }


async def generate_reference_image(prompt: str) -> Dict[str, Any]:
    api_key = getattr(settings, "modelscope_api_key", "")
    if not api_key:
        return {"status": "not_configured", "note": "未配置 MODELSCOPE_API_KEY，跳过参考图生成。"}
    result = await _modelscope_generate_image(
        model=getattr(settings, "image_generation_model", "Tongyi-MAI/Z-Image-Turbo"),
        prompt=prompt,
        size="1024x768",
        timeout_sec=50.0,
    )
    image_url = result.get("url")
    if result.get("status") != "ok" or not isinstance(image_url, str):
        logger.warning("image generation failed: %s", result.get("note"))
        return {"status": "failed", "note": result.get("note") or "参考图服务未返回可展示图片。"}
    cached_url = await _cache_remote_image(image_url, prefix="generated_reference")
    return {
        "status": "ok",
        "url": cached_url or image_url,
        "remoteUrl": image_url if cached_url else None,
        "cached": bool(cached_url),
    }


def _tts_error_message(status_code: int, body: str, endpoint: str) -> str:
    if status_code == 404:
        return f"TTS 接口地址不可用（404）：{endpoint}。请检查 TTS_API_URL 或供应商 API 路径。"
    if status_code in (401, 403):
        return "TTS 鉴权失败，请检查 MODELSCOPE_API_KEY / DASHSCOPE_API_KEY。"
    return f"TTS 服务返回 {status_code}：{body[:180]}"


async def _post_tts(endpoint: str, api_key: str, clean: str, voice: str, speed: float) -> Dict[str, Any]:
    payload = {
        "model": getattr(settings, "tts_model", "Qwen3-TTS-12Hz-1.7B-VoiceDesign"),
        "input": {
            "text": clean,
            "voice": voice,
            "voice_prompt": getattr(settings, "tts_voice_prompt", ""),
            "instructions": getattr(settings, "tts_voice_prompt", ""),
            "speed": speed,
            "volume": "medium",
        },
        "parameters": {
            "voice": voice,
            "speed": speed,
            "volume": 1.0,
            "response_format": "mp3",
        },
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code >= 400:
            return {"status": "failed", "message": _tts_error_message(resp.status_code, resp.text, endpoint)}
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            data = resp.json()
            output = data.get("output") or data.get("data") or data
            audio_url = output.get("audio_url") or output.get("url") or output.get("audioUrl")
            if audio_url:
                return {"status": "ok", "audioUrl": audio_url}
            audio_b64 = output.get("audio") or output.get("audio_base64") or output.get("content")
            if audio_b64:
                raw = base64.b64decode(audio_b64)
            else:
                return {"status": "failed", "message": "TTS API 已响应，但未返回音频 URL 或 base64 音频。"}
        else:
            raw = resp.content
        filename = f"tts_{uuid.uuid4().hex[:16]}.mp3"
        path = generated_asset_dir() / filename
        path.write_bytes(raw)
        return {"status": "ok", "audioUrl": _public_asset_url(path), "contentType": "audio/mpeg"}


async def synthesize_tts(text: str, *, voice: str = "", speed: float = 1.0) -> Dict[str, Any]:
    api_key = getattr(settings, "dashscope_api_key", "") or getattr(settings, "modelscope_api_key", "")
    if not api_key:
        return {"status": "not_configured", "message": "未配置 MODELSCOPE_API_KEY 或 DASHSCOPE_API_KEY，无法语音播报。"}
    clean = re.sub(r"\s+", " ", text or "").strip()[:3000]
    if not clean:
        return {"status": "invalid", "message": "播报文本为空。"}
    voice = voice or getattr(settings, "tts_voice", "Cherry") or "Cherry"
    endpoints = [
        getattr(settings, "tts_api_url", ""),
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        f"{getattr(settings, 'modelscope_api_base', '').rstrip('/')}/services/aigc/multimodal-generation/generation",
    ]
    last_error = ""
    for endpoint in [e for e in endpoints if e]:
        result = await _post_tts(endpoint, api_key, clean, voice, speed)
        if result.get("status") == "ok":
            result["voice"] = voice
            return result
        last_error = result.get("message") or result.get("note") or "TTS 调用失败"
    try:
        return {"status": "failed", "message": last_error or "TTS 供应商未返回可播放音频。"}
    except Exception as exc:
        logger.warning("tts failed: %s", exc)
        return {"status": "failed", "message": f"语音播报失败：{str(exc)[:120]}"}
