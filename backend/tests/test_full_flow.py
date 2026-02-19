"""
End-to-end integration test: Full Virtual Prism user flow (all external APIs mocked).

Flow:
  1. Analyze appearance  (POST /api/genesis/analyze-appearance)
  2. Create persona      (POST /api/genesis/create-persona)
  3. Confirm persona     (POST /api/genesis/confirm-persona)
  4. Generate schedule   (POST /api/life-stream/generate-schedule/{persona_id})
  5. Publish via IG      (POST /api/instagram/publish-now)
"""
import io
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from starlette.testclient import TestClient


# ── Fake data ─────────────────────────────────────────────────────────────────

FAKE_APPEARANCE_DICT = {
    "facial_features": "oval face, dark almond-shaped eyes",
    "skin_tone": "light beige skin tone",
    "hair": "medium-length wavy brown hair",
    "body": "petite, athletic",
    "style": "urban streetwear",
    "image_prompt": (
        "young southeast asian woman, oval face, dark almond-shaped eyes, "
        "light beige skin tone, medium-length wavy brown hair, petite athletic, "
        "urban streetwear, ultra detailed face, photorealistic"
    ),
}

FAKE_PERSONA_DICT = {
    "name": "許小芸 Yuna Xu",
    "occupation": "健身教練 / 生活風格 Influencer",
    "personality_tags": ["陽光", "自律", "有活力"],
    "speech_pattern": "常說「加油！」，句尾喜歡用 💪",
    "values": ["健康生活", "激勵他人"],
    "weekly_lifestyle": "早晨跑步，白天教課，晚上拍短影音記錄生活。",
}

FAKE_SCHEDULE_LIST = [
    {
        "day": i,
        "scene": f"場景 {i}",
        "caption": f"今天的生活 {i} ✨",
        "scene_prompt": f"sunny outdoor cafe scene {i}",
        "hashtags": [f"#day{i}", "#lifestyle"],
    }
    for i in range(1, 8)
]


def _fake_anthropic_msg(obj) -> MagicMock:
    block = MagicMock()
    block.text = json.dumps(obj, ensure_ascii=False)
    msg = MagicMock()
    msg.content = [block]
    return msg


def _fake_image_http_calls(url, **kwargs):
    """Mock requests.post/get for Instagram Graph API calls."""
    resp = MagicMock()
    resp.ok = True
    resp.raise_for_status = MagicMock()
    if "media_publish" in url:
        resp.json.return_value = {"id": "media_final_999"}
    elif "/media" in url:
        resp.json.return_value = {"id": "container_abc"}
    else:
        resp.json.return_value = {"status_code": "FINISHED"}
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Full flow test
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestFullUserFlow:
    """Runs the complete Virtual Prism onboarding → publish pipeline."""

    def test_step1_analyze_appearance(self, client):
        fake_msg = _fake_anthropic_msg(FAKE_APPEARANCE_DICT)
        with patch(
            "app.services.genesis_service.client_anthropic.messages.create",
            new=AsyncMock(return_value=fake_msg),
        ):
            resp = client.post(
                "/api/genesis/analyze-appearance",
                files=[("images", ("selfie.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 50), "image/jpeg"))],
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "appearance" in data
        assert data["appearance"]["image_prompt"] is not None
        # Save for next step
        TestFullUserFlow._appearance_prompt = data["appearance"]["image_prompt"]

    def test_step2_create_persona(self, client):
        fake_msg = _fake_anthropic_msg(FAKE_PERSONA_DICT)
        with patch(
            "app.services.genesis_service.client_anthropic.messages.create",
            new=AsyncMock(return_value=fake_msg),
        ):
            resp = client.post(
                "/api/genesis/create-persona",
                data={"description": "一個熱愛健身、陽光積極的台灣女生"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["persona"]["name"] == FAKE_PERSONA_DICT["name"]
        TestFullUserFlow._persona_data = data["persona"]
        TestFullUserFlow._persona_id = data["persona_id"]

    def test_step3_confirm_persona(self, client):
        resp = client.post("/api/genesis/confirm-persona", json=TestFullUserFlow._persona_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "locked"
        TestFullUserFlow._confirmed_persona_id = data["persona_id"]

    def test_step4_generate_schedule(self, client):
        fake_schedule_msg = _fake_anthropic_msg(FAKE_SCHEDULE_LIST)

        # Mock Anthropic for schedule text AND comfyui_service for image generation
        with patch(
            "app.services.life_stream_service.client.messages.create",
            new=AsyncMock(return_value=fake_schedule_msg),
        ), patch(
            "app.services.comfyui_service.generate_image",
            new=AsyncMock(return_value="https://cdn.example.com/generated.jpg"),
        ), patch(
            "app.services.comfyui_service.build_realism_prompt",
            return_value="fake full prompt",
        ):
            resp = client.post(
                f"/api/life-stream/generate-schedule/{TestFullUserFlow._persona_id}",
                json={
                    "persona": TestFullUserFlow._persona_data,
                    "appearance_prompt": getattr(TestFullUserFlow, "_appearance_prompt", ""),
                    "face_image_url": "",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["persona_id"] == TestFullUserFlow._persona_id
        assert len(data["schedule"]) == 7
        # Each day has an image_url
        for day_item in data["schedule"]:
            assert "image_url" in day_item
            assert day_item["image_url"] is not None

    def test_step5_publish_to_instagram(self, client):
        """Use the env-seeded 'default' persona to publish a generated image."""
        head_resp = MagicMock()
        head_resp.headers = {"Content-Type": "image/jpeg"}

        get_resp = MagicMock()
        get_resp.raise_for_status = MagicMock()
        get_resp.json.return_value = {"status_code": "FINISHED"}

        post_responses = {
            "media_publish": {"id": "media_final_999"},
            "media": {"id": "container_abc"},
        }

        def mock_post(url, **kwargs):
            r = MagicMock()
            r.ok = True
            r.raise_for_status = MagicMock()
            if "media_publish" in url:
                r.json.return_value = post_responses["media_publish"]
            else:
                r.json.return_value = post_responses["media"]
            return r

        with patch("requests.head", return_value=head_resp), \
             patch("requests.get", return_value=get_resp), \
             patch("requests.post", side_effect=mock_post):
            resp = client.post("/api/instagram/publish-now", json={
                "persona_id": "default",
                "image_url": "https://cdn.example.com/generated.jpg",
                "caption": "今天的生活 ✨ #lifestyle #健康",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["media_id"] == "media_final_999"

    def test_step6_schedule_and_cancel(self, client):
        """Schedule a post then cancel it."""
        future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        resp = client.post("/api/instagram/schedule", json={
            "persona_id": "default",
            "posts": [
                {
                    "image_url": "https://cdn.example.com/day1.jpg",
                    "caption": "排程貼文 Day 1",
                    "publish_at": future_time,
                }
            ],
        })
        assert resp.status_code == 201
        job_id = resp.json()["scheduled"][0]["job_id"]

        # Verify it shows up in the list
        list_resp = client.get("/api/instagram/schedule", params={"persona_id": "default"})
        assert list_resp.status_code == 200
        job_ids = [j["job_id"] for j in list_resp.json()["scheduled_posts"]]
        assert job_id in job_ids

        # Cancel it
        del_resp = client.delete(f"/api/instagram/schedule/{job_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["cancelled"] is True
