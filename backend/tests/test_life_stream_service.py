"""
test_life_stream_service.py
---------------------------
重點驗收：generate_weekly_schedule 不再依賴前端傳入的 persona dict，
改為自己從 persona_storage 讀取。
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.persona import PersonaCard, AppearanceFeatures


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_persona_card(persona_id: str = "test123") -> PersonaCard:
    return PersonaCard(
        id=persona_id,
        name="Test User",
        occupation="Designer",
        personality_tags=["creative", "calm"],
        speech_pattern="喜歡說「其實」",
        values=["authenticity"],
        weekly_lifestyle="在咖啡廳工作",
        appearance=AppearanceFeatures(
            facial_features="oval face",
            skin_tone="medium",
            hair="black, shoulder-length",
            body="slim",
            style="casual chic",
            image_prompt="young woman, oval face, medium skin tone, black hair",
        ),
        reference_face_url="https://res.cloudinary.com/test/image/upload/face.jpg",
    )


# --------------------------------------------------------------------------- #
# Test: persona loaded from storage (no persona arg)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_generate_schedule_loads_persona_from_storage():
    """generate_weekly_schedule 必須自行呼叫 load_persona，不靠前端傳入。"""
    persona_card = _make_persona_card("user_001")

    fake_schedule = [
        {"day": 1, "scene": "咖啡廳", "caption": "早安", "scene_prompt": "cafe scene", "hashtags": []},
        {"day": 2, "scene": "公園", "caption": "散步", "scene_prompt": "park scene", "hashtags": []},
        {"day": 3, "scene": "夜市", "caption": "宵夜", "scene_prompt": "night market scene", "hashtags": []},
    ]

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(fake_schedule))]

    with (
        patch("app.services.life_stream_service.load_persona", return_value=persona_card) as mock_load,
        patch("app.services.life_stream_service.client.messages.create", new=AsyncMock(return_value=mock_message)),
        patch("app.services.comfyui_service.generate_image", new=AsyncMock(return_value="https://replicate.delivery/test.jpg")),
        patch("app.services.comfyui_service.build_realism_prompt", return_value="full prompt"),
        patch("app.services.life_stream_service.upload_from_url", new=AsyncMock(return_value="https://cloudinary.com/test.jpg")),
        patch("app.services.life_stream_service.save_schedule"),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        from app.services.life_stream_service import generate_weekly_schedule
        result = await generate_weekly_schedule(persona_id="user_001")

    # load_persona 必須被呼叫，且只用 persona_id
    mock_load.assert_called_once_with("user_001")
    assert result["persona_id"] == "user_001"
    assert len(result["schedule"]) == 3


@pytest.mark.asyncio
async def test_generate_schedule_raises_if_persona_not_found():
    """persona 不存在時應該拋出 ValueError，不是靜默失敗。"""
    with patch("app.services.life_stream_service.load_persona", return_value=None):
        from app.services.life_stream_service import generate_weekly_schedule
        with pytest.raises(ValueError, match="不存在"):
            await generate_weekly_schedule(persona_id="nonexistent")


@pytest.mark.asyncio
async def test_generate_schedule_uses_appearance_prompt_fallback():
    """
    appearance_prompt 優先順序：
    1. 前端傳入（appearance_prompt 參數）
    2. persona.appearance.image_prompt
    3. 預設值
    """
    persona_card = _make_persona_card()
    fake_schedule = [
        {"day": i, "scene": "s", "caption": "c", "scene_prompt": "sp", "hashtags": []}
        for i in range(1, 4)
    ]
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(fake_schedule))]

    captured_prompts = []

    def capture_build_prompt(character_desc, scene_prompt, camera_style):
        captured_prompts.append(character_desc)
        return f"full: {character_desc}"

    with (
        patch("app.services.life_stream_service.load_persona", return_value=persona_card),
        patch("app.services.life_stream_service.client.messages.create", new=AsyncMock(return_value=mock_message)),
        patch("app.services.comfyui_service.generate_image", new=AsyncMock(return_value=None)),
        patch("app.services.comfyui_service.build_realism_prompt", side_effect=capture_build_prompt),
        patch("app.services.life_stream_service.save_schedule"),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        from app.services.life_stream_service import generate_weekly_schedule

        # Case 1：前端傳入 appearance_prompt → 應該使用它
        await generate_weekly_schedule(persona_id="test123", appearance_prompt="custom prompt")
        assert all("custom prompt" in p for p in captured_prompts)

        # Case 2：沒傳 appearance_prompt → fallback 到 persona.appearance.image_prompt
        captured_prompts.clear()
        await generate_weekly_schedule(persona_id="test123")
        assert all("young woman" in p for p in captured_prompts)
