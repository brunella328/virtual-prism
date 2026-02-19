"""
Unit tests for instagram_service.py

Tests:
  - _api_base():  IGAA → graph.instagram.com, EAA → graph.facebook.com
  - wait_for_container(): FINISHED / ERROR / timeout
  - _ensure_jpeg_url(): webp detection + error message
  - disconnect_persona(): clears token store
"""
import time
import pytest
from unittest.mock import patch, MagicMock


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_svc():
    from app.services import instagram_service as svc
    return svc


# ─────────────────────────────────────────────────────────────────────────────
# _api_base()
# ─────────────────────────────────────────────────────────────────────────────

class TestApiBase:
    def test_igaa_token_returns_instagram_graph(self):
        svc = _make_svc()
        base = svc._api_base("IGAAtest_token_xyz")
        assert "graph.instagram.com" in base

    def test_eaa_token_returns_facebook_graph(self):
        svc = _make_svc()
        base = svc._api_base("EAAtest_token_xyz")
        assert "graph.facebook.com" in base

    def test_other_token_returns_facebook_graph(self):
        svc = _make_svc()
        # Any non-IGAA token falls back to graph.facebook.com
        base = svc._api_base("some_other_token")
        assert "graph.facebook.com" in base


# ─────────────────────────────────────────────────────────────────────────────
# wait_for_container()
# ─────────────────────────────────────────────────────────────────────────────

class TestWaitForContainer:
    def _mock_response(self, status_code_val: str) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"status_code": status_code_val}
        return resp

    def test_finished_immediately(self):
        svc = _make_svc()
        finished_resp = self._mock_response("FINISHED")
        with patch("requests.get", return_value=finished_resp) as mock_get:
            # Should return without error
            svc.wait_for_container("cid_123", "EAAtoken", max_wait=9)
        assert mock_get.called

    def test_error_status_raises(self):
        svc = _make_svc()
        error_resp = self._mock_response("ERROR")
        with patch("requests.get", return_value=error_resp):
            with pytest.raises(RuntimeError, match="ERROR"):
                svc.wait_for_container("cid_err", "EAAtoken", max_wait=9)

    def test_timeout_raises(self):
        svc = _make_svc()
        pending_resp = self._mock_response("IN_PROGRESS")

        with patch("requests.get", return_value=pending_resp), \
             patch("time.sleep"):          # skip real sleep
            with pytest.raises(RuntimeError, match="not ready"):
                svc.wait_for_container("cid_timeout", "EAAtoken", max_wait=6)

    def test_finished_after_retries(self):
        svc = _make_svc()
        responses = [
            self._mock_response("IN_PROGRESS"),
            self._mock_response("IN_PROGRESS"),
            self._mock_response("FINISHED"),
        ]
        with patch("requests.get", side_effect=responses), \
             patch("time.sleep"):
            # Should not raise
            svc.wait_for_container("cid_retry", "EAAtoken", max_wait=30)


# ─────────────────────────────────────────────────────────────────────────────
# _ensure_jpeg_url()
# ─────────────────────────────────────────────────────────────────────────────

class TestEnsureJpegUrl:
    def test_jpeg_url_passthrough(self):
        svc = _make_svc()
        jpeg_head = MagicMock()
        jpeg_head.headers = {"Content-Type": "image/jpeg"}
        with patch("requests.head", return_value=jpeg_head):
            result = svc._ensure_jpeg_url("https://example.com/photo.jpg")
        assert result == "https://example.com/photo.jpg"

    def test_webp_content_type_raises(self):
        svc = _make_svc()
        webp_head = MagicMock()
        webp_head.headers = {"Content-Type": "image/webp"}

        get_resp = MagicMock()
        get_resp.raise_for_status = MagicMock()
        get_resp.content = b"fake-webp-content"

        # Mock PIL.Image so the conversion "succeeds" and hits the RuntimeError
        fake_img = MagicMock()
        fake_img.convert.return_value = fake_img
        fake_img.save = MagicMock()

        with patch("requests.head", return_value=webp_head), \
             patch("requests.get", return_value=get_resp), \
             patch("PIL.Image.open", return_value=fake_img):
            with pytest.raises(RuntimeError, match="WebP"):
                svc._ensure_jpeg_url("https://example.com/photo.webp")

    def test_webp_extension_in_url_raises(self):
        svc = _make_svc()
        head_resp = MagicMock()
        head_resp.headers = {"Content-Type": "image/webp"}

        get_resp = MagicMock()
        get_resp.raise_for_status = MagicMock()
        get_resp.content = b"fake-webp"

        fake_img = MagicMock()
        fake_img.convert.return_value = fake_img
        fake_img.save = MagicMock()

        with patch("requests.head", return_value=head_resp), \
             patch("requests.get", return_value=get_resp), \
             patch("PIL.Image.open", return_value=fake_img):
            with pytest.raises(RuntimeError, match="WebP"):
                svc._ensure_jpeg_url("https://example.com/image.webp")

    def test_head_request_failure_passes_through(self):
        svc = _make_svc()
        # If HEAD fails with a non-RuntimeError (e.g., network error), URL is returned as-is
        with patch("requests.head", side_effect=Exception("timeout")):
            result = svc._ensure_jpeg_url("https://example.com/image.jpg")
        assert result == "https://example.com/image.jpg"


# ─────────────────────────────────────────────────────────────────────────────
# disconnect_persona()
# ─────────────────────────────────────────────────────────────────────────────

class TestDisconnectPersona:
    def test_disconnect_existing_persona(self):
        svc = _make_svc()
        # seed a test persona
        svc._token_store["p_test"] = {
            "access_token": "EAAtoken",
            "ig_account_id": "12345",
            "ig_username": "test_user",
        }
        result = svc.disconnect_persona("p_test")
        assert result is True
        assert "p_test" not in svc._token_store

    def test_disconnect_nonexistent_persona_returns_false(self):
        svc = _make_svc()
        result = svc.disconnect_persona("nonexistent_persona_xyz")
        assert result is False

    def test_disconnect_default_persona(self):
        svc = _make_svc()
        # The env-seeded "default" persona should be disconnectable
        assert "default" in svc._token_store
        result = svc.disconnect_persona("default")
        assert result is True
        assert "default" not in svc._token_store
