"""反馈附图上传"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import UploadFile

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_BYTES = 2 * 1024 * 1024

_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "feedback_uploads"


def feedback_upload_dir() -> Path:
    d = _DATA_ROOT
    d.mkdir(parents=True, exist_ok=True)
    return d


async def save_feedback_image(file: UploadFile, user_id: str) -> dict:
    if not file.content_type or file.content_type not in ALLOWED_TYPES:
        raise ValueError("仅支持 JPG / PNG / GIF / WebP 图片")

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise ValueError("单张图片不能超过 2MB")
    if len(raw) < 64:
        raise ValueError("图片文件无效")

    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(file.content_type, ".png")

    name = f"{user_id[:8]}_{uuid.uuid4().hex[:12]}{ext}"
    path = feedback_upload_dir() / name
    path.write_bytes(raw)

    url = f"/api/v1/feedback/files/{name}"
    return {"url": url, "name": file.filename or name}
