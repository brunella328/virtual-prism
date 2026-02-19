"""
Integration tests for /api/instagram/* endpoints.

Tests:
  - GET  /api/instagram/status          → connected:true (env pre-seeded)
  - POST /api/instagram/publish-now     → media_id (mock graph API)
  - POST /api/instagram/schedule        → 201 future, 400 past
  - DELETE /api/instagram/schedule/{id} → 200
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/instagram/status
# ─────────────────────────────────────────────────────────────────────────────

class TestInstagramStatus:
    def test_default_persona_connected(self, client):
        """Env pre-seeds persona_id='default'. Should return connected:true."""
        resp = client.get("/api/instagram/status", params={"persona_id": "default"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data.get("ig_account_id") == "999000111"
        assert data.get("ig_username") == "test_ig_user"

    def test_unknown_persona_not_connected(self, client):
        resp = client.get("/api/instagram/status", params={"persona_id": "unknown_xyz"})
        assert resp.status_code == 200
        assert resp.json()["connected"] is False


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/instagram/publish-now
# ─────────────────────────────────────────────────────────────────────────────

class TestPublishNow:
    def _mock_graph_calls(self):
        """
        Mock the two HTTP calls instagram_service makes:
          1. POST /{ig_account_id}/media  → {"id": "creation_123"}
          2. GET  /{creation_id}          → {"status_code": "FINISHED"}
          3. POST /{ig_account_id}/media_publish → {"id": "media_456"}
        """
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.raise_for_status = MagicMock()
            if "/media_publish" in url:
                resp.json.return_value = {"id": "media_456"}
            elif "/media" in url:
                resp.json.return_value = {"id": "creation_123"}
            else:
                resp.json.return_value = {"status_code": "FINISHED"}
            return resp
        return side_effect

    def test_publish_now_success(self, client):
        with patch("requests.head") as mock_head, \
             patch("requests.post", side_effect=self._mock_graph_calls()), \
             patch("requests.get") as mock_get:

            # HEAD request for _ensure_jpeg_url
            head_resp = MagicMock()
            head_resp.headers = {"Content-Type": "image/jpeg"}
            mock_head.return_value = head_resp

            # GET for wait_for_container
            get_resp = MagicMock()
            get_resp.raise_for_status = MagicMock()
            get_resp.json.return_value = {"status_code": "FINISHED"}
            mock_get.return_value = get_resp

            resp = client.post("/api/instagram/publish-now", json={
                "persona_id": "default",
                "image_url": "https://example.com/photo.jpg",
                "caption": "Test caption #test",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["media_id"] == "media_456"

    def test_publish_now_not_connected_returns_400(self, client):
        resp = client.post("/api/instagram/publish-now", json={
            "persona_id": "disconnected_persona",
            "image_url": "https://example.com/photo.jpg",
            "caption": "Test",
        })
        assert resp.status_code == 400

    def test_publish_now_webp_returns_500(self, client):
        head_resp = MagicMock()
        head_resp.headers = {"Content-Type": "image/webp"}

        get_resp = MagicMock()
        get_resp.raise_for_status = MagicMock()
        get_resp.content = b"webp-bytes"

        # Mock PIL so conversion path succeeds and raises RuntimeError("WebP...")
        fake_img = MagicMock()
        fake_img.convert.return_value = fake_img
        fake_img.save = MagicMock()

        with patch("requests.head", return_value=head_resp), \
             patch("requests.get", return_value=get_resp), \
             patch("PIL.Image.open", return_value=fake_img):

            resp = client.post("/api/instagram/publish-now", json={
                "persona_id": "default",
                "image_url": "https://example.com/photo.webp",
                "caption": "Test",
            })

        assert resp.status_code == 500
        assert "WebP" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/instagram/schedule
# ─────────────────────────────────────────────────────────────────────────────

class TestScheduleCreate:
    def _future_iso(self, minutes: int = 10) -> str:
        dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return dt.isoformat()

    def _past_iso(self, minutes: int = 10) -> str:
        dt = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return dt.isoformat()

    def test_schedule_future_returns_201(self, client):
        resp = client.post("/api/instagram/schedule", json={
            "persona_id": "default",
            "posts": [
                {
                    "image_url": "https://example.com/photo.jpg",
                    "caption": "Tomorrow post",
                    "publish_at": self._future_iso(60),
                }
            ]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["count"] == 1
        assert len(data["scheduled"]) == 1
        assert "job_id" in data["scheduled"][0]

    def test_schedule_past_returns_400(self, client):
        resp = client.post("/api/instagram/schedule", json={
            "persona_id": "default",
            "posts": [
                {
                    "image_url": "https://example.com/photo.jpg",
                    "caption": "Old post",
                    "publish_at": self._past_iso(60),
                }
            ]
        })
        assert resp.status_code == 400
        assert "未來" in resp.json()["detail"]

    def test_schedule_not_connected_returns_400(self, client):
        resp = client.post("/api/instagram/schedule", json={
            "persona_id": "no_ig_persona",
            "posts": [
                {
                    "image_url": "https://example.com/photo.jpg",
                    "caption": "Post",
                    "publish_at": self._future_iso(60),
                }
            ]
        })
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/instagram/schedule
# ─────────────────────────────────────────────────────────────────────────────

class TestScheduleList:
    def test_list_schedule(self, client):
        resp = client.get("/api/instagram/schedule", params={"persona_id": "default"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["persona_id"] == "default"
        assert "scheduled_posts" in data
        assert isinstance(data["scheduled_posts"], list)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/instagram/schedule/{job_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestScheduleDelete:
    def _schedule_one(self, client) -> str:
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        resp = client.post("/api/instagram/schedule", json={
            "persona_id": "default",
            "posts": [{"image_url": "https://example.com/p.jpg", "caption": "c", "publish_at": future}]
        })
        assert resp.status_code == 201
        return resp.json()["scheduled"][0]["job_id"]

    def test_cancel_existing_job_returns_200(self, client):
        job_id = self._schedule_one(client)
        resp = client.delete(f"/api/instagram/schedule/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["cancelled"] is True

    def test_cancel_nonexistent_job_returns_404(self, client):
        resp = client.delete("/api/instagram/schedule/nonexistent-job-id-xxx")
        assert resp.status_code == 404
