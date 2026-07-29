"""Regression tests for the deep multimodal answer contract."""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

from app.services.multimodal_agent.service import (
    _asks_for_answer_only,
    _answer_media,
    _build_plan,
    _compose_with_llm_stream,
    _ensure_answer_table,
    _has_markdown_table,
    _prepend_user_visuals,
    _strip_unmanaged_markdown_images,
    process_multimodal_message,
)
from app.services.multimodal_assets import (
    _modelscope_image_model,
    _write_flowchart_svg,
    generate_drawio_flowchart,
    generated_asset_dir,
)
from app.services.multimodal_rag import _rerank_text_results


VISUAL_QUERY = (
    "如果麒麟虚拟机出现了上图问题，给我分析原因，进行图文结合的回答，"
    "添加表格并给出一个解决步骤的流程图，回答通俗易懂"
)


def test_visual_request_is_a_professional_answer_intent():
    assert _asks_for_answer_only(VISUAL_QUERY)


def test_virtual_machine_visual_request_builds_a_plan():
    plan = asyncio.run(_build_plan(VISUAL_QUERY, {"text_results": [], "image_results": []}, []))
    assert plan
    assert plan["steps"]
    assert "虚拟机" in plan["title"]


def test_answer_contract_adds_markdown_table():
    answer = _ensure_answer_table(
        "## 综合判断\n\n需要继续排查。",
        {"steps": [{"order": 1, "action": "检查磁盘空间", "expected": "空间充足", "risk": "L1"}]},
    )
    assert _has_markdown_table(answer)
    assert "检查磁盘空间" in answer


def test_user_upload_is_embedded_in_answer():
    answer = _prepend_user_visuals(
        "## 综合判断\n\n测试正文",
        [{"name": "login-loop.png", "url": "/api/v1/chat/files/login-loop.png", "summary": "登录循环", "detail": "登录循环"}],
    )
    assert "用户提供的问题截图" in answer
    assert "![login-loop.png](/api/v1/chat/files/login-loop.png)" in answer


def test_model_supplied_remote_images_are_removed_before_system_assets():
    answer = _strip_unmanaged_markdown_images(
        "## 图文说明\n\n![未经审核图片](https://example.com/not-an-image)\n\n保留文字说明。"
    )
    assert "![" not in answer
    assert "保留文字说明" in answer


def test_reranker_rejects_domain_only_false_positive():
    results = [
        {"title": "如何安装麒麟系统", "snippet": "从 U 盘进入系统安装界面", "score": 0.95},
        {"title": "麒麟虚拟机登录循环排查", "snippet": "虚拟机登录后返回登录界面", "score": 0.7},
    ]
    accepted, rejected = _rerank_text_results("麒麟虚拟机登录循环", results, 5)
    assert [item["title"] for item in accepted] == ["麒麟虚拟机登录循环排查"]
    assert any(item["title"] == "如何安装麒麟系统" for item in rejected)


def test_modelscope_display_name_is_normalized():
    assert _modelscope_image_model("Z-Image-Turbo") == "Tongyi-MAI/Z-Image-Turbo"


def test_local_flowchart_is_a_displayable_svg():
    url = _write_flowchart_svg(
        "登录循环排查",
        [{"action": "关闭 3D 加速"}, {"action": "检查磁盘空间"}, {"action": "重启验证"}],
        note="test",
    )
    path = generated_asset_dir() / Path(url).name
    try:
        content = path.read_text(encoding="utf-8")
        assert url.startswith("/api/v1/chat/generated/")
        assert content.lstrip().startswith("<svg")
        assert "关闭 3D 加速" in content
    finally:
        path.unlink(missing_ok=True)


def test_zimage_draft_is_quality_gated_by_exact_svg_labels():
    import app.services.multimodal_assets as assets

    original = assets.generate_zimage_flowchart

    async def fake_zimage(title, steps):
        return {"status": "ok", "url": "/api/v1/chat/generated/model-draft.png", "format": "image"}

    assets.generate_zimage_flowchart = fake_zimage
    try:
        result = asyncio.run(generate_drawio_flowchart("精确流程", [{"action": "步骤文字必须正确"}]))
        path = generated_asset_dir() / Path(result["url"]).name
        try:
            assert result["provider"] == "modelscope_zimage+verified_svg"
            assert result["format"] == "svg"
            assert result["generatedUrl"].endswith("model-draft.png")
            assert "步骤文字必须正确" in path.read_text(encoding="utf-8")
        finally:
            path.unlink(missing_ok=True)
    finally:
        assets.generate_zimage_flowchart = original


def test_answer_media_event_has_stable_display_contract():
    event = _answer_media(
        "solution-flowchart",
        "diagram",
        "ready",
        "处理流程图",
        url="/api/v1/chat/generated/flow.svg",
    )
    payload = json.loads(event["data"])
    assert event["event"] == "answer_media"
    assert payload["id"] == "solution-flowchart"
    assert payload["status"] == "ready"
    assert payload["url"].endswith("flow.svg")


def test_answer_composer_exposes_real_async_chunks():
    from app.services import chat_service

    original = chat_service.call_deepseek

    async def fake_call(*_args, **_kwargs):
        yield {"choices": [{"delta": {"content": "第一段"}}]}
        await asyncio.sleep(0)
        yield {"choices": [{"delta": {"content": "第二段"}}]}

    async def collect():
        return [
            chunk
            async for chunk in _compose_with_llm_stream(
                "测试问题",
                [],
                {"text_results": [], "image_results": []},
                None,
            )
        ]

    chat_service.call_deepseek = fake_call
    try:
        assert asyncio.run(collect()) == ["第一段", "第二段"]
    finally:
        chat_service.call_deepseek = original


def test_deep_answer_no_longer_uses_three_character_fake_streaming():
    source = inspect.getsource(process_multimodal_message)
    assert "len(response), 3" not in source
    assert "len(full_response), 3" not in source
    assert inspect.isasyncgenfunction(_compose_with_llm_stream)
