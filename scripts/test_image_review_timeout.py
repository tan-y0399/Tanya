"""Smoke test for multimodal image review timeout/fallback behavior."""
from __future__ import annotations

import asyncio
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

fake_config = types.ModuleType("app.core.config")
fake_config.settings = SimpleNamespace(
    paddleocr_vl_model_dir="models/PaddleOCR-VL-1.6",
    image_review_min_score=0.18,
    image_review_soft_min_score=0.06,
    image_review_keep_min=1,
    image_review_max_candidates=4,
    image_review_total_timeout_sec=1.0,
    image_review_ocr_timeout_sec=0.5,
)
sys.modules["app.core.config"] = fake_config
fake_httpx = types.ModuleType("httpx")


class _UnusedAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


fake_httpx.AsyncClient = _UnusedAsyncClient
sys.modules["httpx"] = fake_httpx

from app.services import multimodal_assets as assets  # noqa: E402


async def slow_ocr(_image):
    await asyncio.sleep(10)
    return {"status": "ok", "text": "should not be returned"}


async def main() -> None:
    assets._ocr_image = slow_ocr
    images = [
        {
            "title": "kylin vmware virtual machine boot failed screenshot",
            "description": "vmware 3d acceleration display issue",
            "url": "https://example.com/kylin-vmware.png",
            "source": "external",
            "score": 0.2,
        }
        for _ in range(4)
    ]
    started = time.perf_counter()
    result = await assets.review_image_candidates(
        "kylin vmware virtual machine boot failed 3d acceleration display issue",
        images,
    )
    elapsed = time.perf_counter() - started
    print(f"elapsed={elapsed:.2f}s")
    print(result["summary"])
    print(f"accepted={len(result['accepted'])}")
    print(f"first_ocr_status={result['samples'][0]['ocrStatus']}")
    assert elapsed < 2.5, "image review did not respect total timeout"
    assert result["samples"][0]["ocrStatus"] == "timeout"
    assert len(result["accepted"]) >= 1


if __name__ == "__main__":
    asyncio.run(main())
