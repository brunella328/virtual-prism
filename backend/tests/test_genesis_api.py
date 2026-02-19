"""
Tests for /api/genesis/* endpoints.

Tests:
  - POST /api/genesis/analyze-appearance  (mock Anthropic)
  - POST /api/genesis/create-persona      (mock Anthropic)
  - POST /api/genesis/confirm-persona
"""
import io
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Fixtures: fake Anthropic responses ───────────────────────────────────────

FAKE_APPEARANCE_JSON = json.dumps({
    "facial_features": "oval face, almond eyes, high cheekbones",
    "skin_tone": "warm olive skin tone",
    "hair": "long straight black hair",
    "body": "slender, tall",
    "style": "casual chic",
    "image_prompt": (
        "young asian woman, oval face, almond eyes, warm olive skin tone, "
        "long straight black hair, slender tall, casual chic style, "
        "ultra detailed face, consistent character, photorealistic"
    ),
})

FAKE_PERSONA_JSON = json.dumps({
    "name": "林小晴 Clara Lin",
    "occupation": "自由攝影師 / 旅遊 Youtuber",
    "personality_tags": ["冒險", "創意", "真實"],
    "speech_pattern": "句尾喜歡加「欸」，愛用 🌿 emoji",
    "values": ["探索世界", "真實生活"],
    "weekly_lifestyle": "週間外拍咖啡廳，週末爬山或衝浪，晚上剪片直播。",
})


def _make_anthropic_message(text: str):
    """Build a minimal fake Anthropic Message object."""
    content_block = MagicMock()
    content_block.text = text
    msg = MagicMock()
    msg.content = [content_block]
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/genesis/analyze-appearance
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeAppearance:
    def test_analyze_appearance_success(self, client):
        """Mock Anthropic; expect AppearanceFeatures JSON returned."""
        fake_msg = _make_anthropic_message(FAKE_APPEARANCE_JSON)

        with patch(
            "app.services.genesis_service.client_anthropic.messages.create",
            new=AsyncMock(return_value=fake_msg),
        ):
            # Upload a minimal JPEG-like file
            fake_image = io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100)
            resp = client.post(
                "/api/genesis/analyze-appearance",
                files=[("images", ("test.jpg", fake_image, "image/jpeg"))],
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "appearance" in data
        appearance = data["appearance"]
        assert appearance["skin_tone"] == "warm olive skin tone"
        assert "image_prompt" in appearance

    def test_analyze_appearance_too_many_images_returns_400(self, client):
        """More than 3 images → 400."""
        fake_image = io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 10)
        files = [
            ("images", (f"img{i}.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg"))
            for i in range(4)
        ]
        resp = client.post("/api/genesis/analyze-appearance", files=files)
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/genesis/create-persona
# ─────────────────────────────────────────────────────────────────────────────

class TestCreatePersona:
    def test_create_persona_success(self, client):
        fake_msg = _make_anthropic_message(FAKE_PERSONA_JSON)

        with patch(
            "app.services.genesis_service.client_anthropic.messages.create",
            new=AsyncMock(return_value=fake_msg),
        ):
            resp = client.post(
                "/api/genesis/create-persona",
                data={"description": "一個熱愛旅遊攝影的台灣女生，個性開朗真實"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "persona_id" in data
        assert "persona" in data
        persona = data["persona"]
        assert persona["name"] == "林小晴 Clara Lin"
        assert "personality_tags" in persona
        assert isinstance(persona["personality_tags"], list)

    def test_create_persona_missing_description_returns_422(self, client):
        """Missing form field → FastAPI validation 422."""
        resp = client.post("/api/genesis/create-persona", data={})
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/genesis/confirm-persona
# ─────────────────────────────────────────────────────────────────────────────

class TestConfirmPersona:
    VALID_PERSONA = {
        "name": "林小晴 Clara Lin",
        "occupation": "攝影師",
        "personality_tags": ["冒險", "創意"],
        "speech_pattern": "句尾加欸",
        "values": ["探索"],
        "weekly_lifestyle": "週間外拍。",
    }

    def test_confirm_persona_success(self, client):
        resp = client.post("/api/genesis/confirm-persona", json=self.VALID_PERSONA)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "locked"
        assert "persona_id" in data
        assert data["persona"]["name"] == self.VALID_PERSONA["name"]

    def test_confirm_persona_missing_field_returns_422(self, client):
        bad_persona = {k: v for k, v in self.VALID_PERSONA.items() if k != "name"}
        resp = client.post("/api/genesis/confirm-persona", json=bad_persona)
        assert resp.status_code == 422
