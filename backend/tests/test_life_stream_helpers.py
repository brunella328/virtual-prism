"""
TDD — life_stream_service helpers

測試三個即將被提取的 helper 函式，以及 prompt 共用常數的正確性。
在 helper 實作之前這些測試全部 fail（Red phase）。
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.life_stream_service import (
    _infer_camera_style,
    _extract_json_from_claude,
    _generate_and_upload_image,
    SCENE_PROMPT_QUALITY_GUIDE,
    SINGLE_POST_PROMPT,
    SCHEDULE_PROMPT,
)


# ---------------------------------------------------------------------------
# _infer_camera_style — pure function
# ---------------------------------------------------------------------------

class TestInferCameraStyle:
    def test_night_keyword(self):
        assert _infer_camera_style("standing at night market") == "night"

    def test_neon_maps_to_night(self):
        assert _infer_camera_style("neon lights reflecting off puddles") == "night"

    def test_beach_maps_to_outdoor(self):
        assert _infer_camera_style("walking on beach at sunset") == "outdoor"

    def test_cafe_maps_to_indoor(self):
        assert _infer_camera_style("sitting at cafe reading a book") == "indoor"

    def test_portrait_keyword(self):
        assert _infer_camera_style("portrait style close-up shot") == "portrait"

    def test_unknown_scene_defaults_to_lifestyle(self):
        assert _infer_camera_style("doing something completely random") == "lifestyle"

    def test_case_insensitive(self):
        assert _infer_camera_style("NIGHT scene outdoor BEACH") == "night"

    def test_first_match_wins(self):
        # "bar" → night, "cafe" → indoor; night should win because it comes first
        assert _infer_camera_style("bar with cafe vibes") == "night"


# ---------------------------------------------------------------------------
# _extract_json_from_claude — pure function
# ---------------------------------------------------------------------------

class TestExtractJsonFromClaude:
    def test_plain_json_object(self):
        raw = '{"scene": "test", "caption": "hi"}'
        result = _extract_json_from_claude(raw, start_char="{")
        assert result["scene"] == "test"

    def test_plain_json_array(self):
        raw = '[{"day": 1}, {"day": 2}]'
        result = _extract_json_from_claude(raw, start_char="[")
        assert len(result) == 2

    def test_strips_markdown_code_block(self):
        raw = '```json\n{"scene": "test"}\n```'
        result = _extract_json_from_claude(raw, start_char="{")
        assert result["scene"] == "test"

    def test_strips_leading_prose(self):
        raw = 'Here is the JSON output:\n{"scene": "test"}'
        result = _extract_json_from_claude(raw, start_char="{")
        assert result["scene"] == "test"

    def test_raises_on_missing_start_char(self):
        with pytest.raises(ValueError, match="找不到"):
            _extract_json_from_claude("no json here at all", start_char="{")

    def test_raises_on_invalid_json(self):
        with pytest.raises(ValueError):
            _extract_json_from_claude("{invalid: json}", start_char="{")


# ---------------------------------------------------------------------------
# SCENE_PROMPT_QUALITY_GUIDE — shared constant
# ---------------------------------------------------------------------------

class TestScenePromptQualityGuide:
    REQUIRED_ELEMENTS = ["真實瑕疵", "動態瞬間", "光線缺陷", "背景雜亂", "手機感"]

    def test_quality_guide_contains_all_five_elements(self):
        for element in self.REQUIRED_ELEMENTS:
            assert element in SCENE_PROMPT_QUALITY_GUIDE, \
                f"SCENE_PROMPT_QUALITY_GUIDE missing: {element}"

    def test_schedule_prompt_embeds_quality_guide(self):
        for element in self.REQUIRED_ELEMENTS:
            assert element in SCHEDULE_PROMPT, \
                f"SCHEDULE_PROMPT missing quality element: {element}"

    def test_single_post_prompt_embeds_quality_guide(self):
        # This test would have caught the original bug
        for element in self.REQUIRED_ELEMENTS:
            assert element in SINGLE_POST_PROMPT, \
                f"SINGLE_POST_PROMPT missing quality element: {element}"


# ---------------------------------------------------------------------------
# _generate_and_upload_image — async, external deps mocked
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGenerateAndUploadImage:
    async def test_returns_cloudinary_url_on_success(self):
        with patch("app.services.life_stream_service.comfyui_service") as mock_comfy, \
             patch("app.services.life_stream_service.upload_from_url",
                   new_callable=AsyncMock) as mock_upload:
            mock_comfy.generate_image = AsyncMock(return_value="https://replicate.com/img.png")
            mock_upload.return_value = "https://cloudinary.com/img.png"

            result = await _generate_and_upload_image(
                full_prompt="test prompt",
                face_image_url="https://face.jpg",
                persona_id="user_123",
                camera_style="indoor",
            )

            assert result == "https://cloudinary.com/img.png"

    async def test_falls_back_to_replicate_when_cloudinary_fails(self):
        with patch("app.services.life_stream_service.comfyui_service") as mock_comfy, \
             patch("app.services.life_stream_service.upload_from_url",
                   new_callable=AsyncMock) as mock_upload:
            mock_comfy.generate_image = AsyncMock(return_value="https://replicate.com/img.png")
            mock_upload.side_effect = Exception("Cloudinary unavailable")

            result = await _generate_and_upload_image(
                full_prompt="test prompt",
                face_image_url="https://face.jpg",
                persona_id="user_123",
                camera_style="indoor",
            )

            assert result == "https://replicate.com/img.png"

    async def test_returns_none_when_replicate_fails(self):
        with patch("app.services.life_stream_service.comfyui_service") as mock_comfy:
            mock_comfy.generate_image = AsyncMock(
                side_effect=RuntimeError("Replicate API error")
            )

            result = await _generate_and_upload_image(
                full_prompt="test prompt",
                face_image_url="https://face.jpg",
                persona_id="user_123",
                camera_style="indoor",
            )

            assert result is None

    async def test_upload_uses_correct_cloudinary_folder(self):
        with patch("app.services.life_stream_service.comfyui_service") as mock_comfy, \
             patch("app.services.life_stream_service.upload_from_url",
                   new_callable=AsyncMock) as mock_upload:
            mock_comfy.generate_image = AsyncMock(return_value="https://replicate.com/img.png")
            mock_upload.return_value = "https://cloudinary.com/img.png"

            await _generate_and_upload_image(
                full_prompt="test",
                face_image_url="",
                persona_id="user_abc",
                camera_style="outdoor",
            )

            mock_upload.assert_called_once_with(
                "https://replicate.com/img.png",
                folder="virtual_prism/user_abc",
            )
