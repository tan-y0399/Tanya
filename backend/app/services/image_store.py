"""聊天图片附件存储与轻量校验。"""
from __future__ import annotations

import base64
import binascii
import imghdr
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.multimodal import MessageAttachment


BACKEND_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = BACKEND_ROOT / "data" / "chat_uploads"
PUBLIC_PREFIX = "/api/v1/chat/files"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


def chat_upload_dir() -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOAD_ROOT


def _safe_filename(name: str) -> str:
    stem = Path(name or "image").stem
    suffix = Path(name or "").suffix.lower()
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("._") or "image"
    if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        suffix = ".png"
    return f"{stem[:60]}{suffix}"


def _decode_data_url(data_url: str) -> tuple[str, bytes]:
    if not data_url:
        raise ValueError("图片内容为空")
    content_type = "image/png"
    payload = data_url
    if data_url.startswith("data:"):
        header, _, payload = data_url.partition(",")
        match = re.match(r"data:([^;]+);base64", header)
        if match:
            content_type = match.group(1).lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"不支持的图片类型: {content_type}")
    try:
        raw = base64.b64decode(payload, validate=True)
    except binascii.Error as exc:
        raise ValueError("图片 base64 内容无效") from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("单张图片不能超过 8MB")
    detected = imghdr.what(None, raw)
    if detected == "jpeg":
        detected = "jpg"
    if detected and detected not in {"png", "jpg", "webp", "gif"}:
        raise ValueError("图片格式校验失败")
    return content_type, raw


async def save_message_attachments(
    db: AsyncSession,
    session_id: str,
    attachments: Iterable[Dict[str, Any]],
    *,
    message_id: Optional[str] = None,
    role: str = "user",
) -> List[Dict[str, Any]]:
    saved: List[Dict[str, Any]] = []
    for item in attachments or []:
        kind = item.get("kind") or item.get("type") or "image"
        if kind != "image":
            continue
        content_type, raw = _decode_data_url(item.get("dataUrl") or item.get("data_url") or item.get("base64") or "")
        original = _safe_filename(item.get("name") or item.get("filename") or "image.png")
        filename = f"{uuid.uuid4().hex[:16]}_{original}"
        path = chat_upload_dir() / filename
        path.write_bytes(raw)
        row = MessageAttachment(
            session_id=session_id,
            message_id=message_id,
            role=role,
            kind="image",
            filename=original,
            content_type=content_type,
            storage_path=str(path),
            public_url=f"{PUBLIC_PREFIX}/{filename}",
            size_bytes=len(raw),
            meta_json={
                "client_id": item.get("id"),
                "width": item.get("width"),
                "height": item.get("height"),
            },
        )
        db.add(row)
        await db.flush()
        saved.append(attachment_to_dict(row))
    await db.commit()
    return saved


async def list_message_attachments(db: AsyncSession, message_ids: Iterable[str]) -> Dict[str, List[Dict[str, Any]]]:
    ids = [mid for mid in message_ids if mid]
    if not ids:
        return {}
    result = await db.execute(select(MessageAttachment).where(MessageAttachment.message_id.in_(ids)))
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in result.scalars().all():
        grouped.setdefault(row.message_id, []).append(attachment_to_dict(row))
    return grouped


def attachment_to_dict(row: MessageAttachment) -> Dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "name": row.filename,
        "contentType": row.content_type,
        "url": row.public_url,
        "size": row.size_bytes,
        "meta": row.meta_json or {},
    }
