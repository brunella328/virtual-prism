"""
Domain: Instagram OAuth Flow (A1-A8)
Tests:
  - get_auth_url() uses Instagram Login endpoint + correct scope
  - exchange_code_for_token() uses IG token URL + ig_exchange_token
  - get_instagram_account_id() IGAA path → graph.instagram.com/me
  - Multi-persona isolation (different ig_user_id → separate token store entries)
  - Token refresh job registered after OAuth
  - Token auto-refresh (refresh_instagram_token) updates store + .env
  - Refresh failure triggers Telegram notification
  - OAuth callback endpoint redirects to /auth/callback with ig_user_id + ig_username
  - DELETE /api/instagram/token/{persona_id} clears token
"""
import os
import pytest
from unittest.mock import patch, MagicMock, call
from starlette.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# get_auth_url()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetAuthUrl:
    def test_uses_instagram_oauth_url(self):
        from app.services import instagram_service as svc
        url = svc.get_auth_url("persona_test")
        assert "api.instagram.com/oauth/authorize" in url

    def test_contains_instagram_business_scope(self):
        from app.services import instagram_service as svc
        url = svc.get_auth_url("persona_test")
        assert "instagram_business_basic" in url
        assert "instagram_business_content_publish" in url

    def test_does_not_use_facebook_oauth(self):
        from app.services import instagram_service as svc
        url = svc.get_auth_url("persona_test")
        assert "facebook.com/dialog/oauth" not in url

    def test_state_contains_persona_id(self):
        from app.services import instagram_service as svc
        url = svc.get_auth_url("my_ig_user_123")
        assert "state=my_ig_user_123" in url

    def test_missing_app_id_raises(self):
        from app.services import instagram_service as svc
        original = svc.INSTAGRAM_APP_ID
        try:
            svc.INSTAGRAM_APP_ID = ""
            with pytest.raises(ValueError, match="INSTAGRAM_APP_ID"):
                svc.get_auth_url("p")
        finally:
            svc.INSTAGRAM_APP_ID = original


# ─────────────────────────────────────────────────────────────────────────────
# exchange_code_for_token()
# ─────────────────────────────────────────────────────────────────────────────

class TestExchangeCodeForToken:
    def _make_mock_responses(self, ig_user_id="27263512706618393", username="kelse_y818"):
        """
        Three HTTP calls in exchange_code_for_token:
          1. POST api.instagram.com/oauth/access_token → short-lived token
          2. GET  graph.instagram.com/access_token      → long-lived token
          3. GET  graph.instagram.com/me               → user_id + username
        """
        def post_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"access_token": "IGAAshort_token_abc"}
            return resp

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.raise_for_status = MagicMock()
            if "access_token" in url and "graph.instagram.com" in url:
                resp.json.return_value = {
                    "access_token": "IGAAlong_lived_token_xyz",
                    "token_type": "bearer",
                    "expires_in": 5183944,
                }
            elif "me" in url:
                resp.json.return_value = {
                    "user_id": ig_user_id,
                    "username": username,
                    "id": ig_user_id,
                }
            else:
                resp.json.return_value = {"data": []}
            return resp

        return post_side_effect, get_side_effect

    def test_uses_instagram_token_endpoint(self):
        from app.services import instagram_service as svc
        post_fn, get_fn = self._make_mock_responses()
        with patch("requests.post", side_effect=post_fn) as mock_post, \
             patch("requests.get", side_effect=get_fn):
            svc.exchange_code_for_token("auth_code_abc", "test_persona")
        # First POST should be to api.instagram.com
        first_call_url = mock_post.call_args_list[0][0][0]
        assert "api.instagram.com/oauth/access_token" in first_call_url

    def test_exchanges_to_long_lived_token(self):
        from app.services import instagram_service as svc
        post_fn, get_fn = self._make_mock_responses()
        with patch("requests.post", side_effect=post_fn), \
             patch("requests.get", side_effect=get_fn):
            info = svc.exchange_code_for_token("auth_code_abc", "test_persona_long")
        assert info["access_token"] == "IGAAlong_lived_token_xyz"
        assert info["expires_in"] == 5183944

    def test_stores_token_under_persona_id(self):
        from app.services import instagram_service as svc
        post_fn, get_fn = self._make_mock_responses(ig_user_id="11122233", username="user_a")
        with patch("requests.post", side_effect=post_fn), \
             patch("requests.get", side_effect=get_fn):
            svc.exchange_code_for_token("code_for_a", "persona_a")
        assert "persona_a" in svc._token_store
        assert svc._token_store["persona_a"]["ig_username"] == "user_a"

    def test_multi_persona_isolation(self):
        """Two different personas must have separate token store entries."""
        from app.services import instagram_service as svc

        def get_fn_a(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "me" in url:
                resp.json.return_value = {"user_id": "AAA111", "username": "user_a", "id": "AAA111"}
            else:
                resp.json.return_value = {"access_token": "IGAAlong_A", "expires_in": 5183944}
            return resp

        def get_fn_b(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "me" in url:
                resp.json.return_value = {"user_id": "BBB222", "username": "user_b", "id": "BBB222"}
            else:
                resp.json.return_value = {"access_token": "IGAAlong_B", "expires_in": 5183944}
            return resp

        post_fn = MagicMock()
        post_fn.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"access_token": "IGAAshort"})
        )

        with patch("requests.post", return_value=post_fn()), \
             patch("requests.get", side_effect=get_fn_a):
            svc.exchange_code_for_token("code_a", "persona_AAA")

        with patch("requests.post", return_value=post_fn()), \
             patch("requests.get", side_effect=get_fn_b):
            svc.exchange_code_for_token("code_b", "persona_BBB")

        assert svc._token_store["persona_AAA"]["ig_username"] == "user_a"
        assert svc._token_store["persona_BBB"]["ig_username"] == "user_b"
        assert svc._token_store["persona_AAA"]["access_token"] != \
               svc._token_store["persona_BBB"]["access_token"]


# ─────────────────────────────────────────────────────────────────────────────
# get_instagram_account_id() — IGAA path
# ─────────────────────────────────────────────────────────────────────────────

class TestGetInstagramAccountId:
    def test_igaa_token_uses_instagram_graph_me(self):
        from app.services import instagram_service as svc
        me_resp = MagicMock()
        me_resp.raise_for_status = MagicMock()
        me_resp.json.return_value = {"user_id": "27263512706618393", "username": "kelse_y818"}

        with patch("requests.get", return_value=me_resp) as mock_get:
            uid, username = svc.get_instagram_account_id("IGAAtest_token")

        call_url = mock_get.call_args[0][0]
        assert "graph.instagram.com" in call_url
        assert uid == "27263512706618393"
        assert username == "kelse_y818"

    def test_igaa_token_uses_me_id_field_fallback(self):
        """If user_id not present, falls back to id field."""
        from app.services import instagram_service as svc
        me_resp = MagicMock()
        me_resp.raise_for_status = MagicMock()
        me_resp.json.return_value = {"id": "12345678", "username": "test_creator"}

        with patch("requests.get", return_value=me_resp):
            uid, username = svc.get_instagram_account_id("IGAAtest_token_2")

        assert uid == "12345678"
        assert username == "test_creator"


# ─────────────────────────────────────────────────────────────────────────────
# refresh_instagram_token()
# ─────────────────────────────────────────────────────────────────────────────

class TestRefreshInstagramToken:
    def test_refresh_success_updates_token_store(self, tmp_path):
        from app.services import instagram_service as svc

        # Seed a test persona
        svc._token_store["refresh_test"] = {
            "access_token": "IGAAold_token",
            "ig_account_id": "999",
            "ig_username": "refresh_user",
        }

        refresh_resp = MagicMock()
        refresh_resp.raise_for_status = MagicMock()
        refresh_resp.json.return_value = {
            "access_token": "IGAAnew_refreshed_token",
            "expires_in": 5183944,
        }

        with patch("requests.get", return_value=refresh_resp), \
             patch("app.services.instagram_service._send_telegram") as mock_tg, \
             patch("os.path.exists", return_value=False):  # skip .env write
            svc.refresh_instagram_token("refresh_test")

        assert svc._token_store["refresh_test"]["access_token"] == "IGAAnew_refreshed_token"
        # Should send success Telegram notification
        mock_tg.assert_called_once()
        assert "成功" in mock_tg.call_args[0][0]

    def test_refresh_failure_sends_telegram_alert(self):
        from app.services import instagram_service as svc

        svc._token_store["fail_test"] = {
            "access_token": "IGAAexpired_token",
            "ig_account_id": "888",
            "ig_username": "fail_user",
        }

        with patch("requests.get", side_effect=Exception("Token expired")), \
             patch("app.services.instagram_service._send_telegram") as mock_tg:
            svc.refresh_instagram_token("fail_test")

        mock_tg.assert_called_once()
        notification = mock_tg.call_args[0][0]
        assert "失敗" in notification
        assert "fail_test" in notification

    def test_refresh_missing_persona_skips_gracefully(self):
        from app.services import instagram_service as svc
        # Should not raise, just log warning
        with patch("app.services.instagram_service._send_telegram") as mock_tg:
            svc.refresh_instagram_token("nonexistent_persona_999")
        mock_tg.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# OAuth Callback endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestOAuthCallback:
    @pytest.fixture
    def client(self):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def _mock_token_exchange(self, ig_user_id="27263512706618393", username="kelse_y818"):
        info = {
            "access_token": "IGAAlong_token",
            "ig_account_id": ig_user_id,
            "ig_username": username,
            "expires_in": 5183944,
            "connected_at": "2026-02-19T00:00:00+00:00",
        }
        return patch("app.services.instagram_service.exchange_code_for_token", return_value=info)

    def test_callback_redirects_to_auth_callback(self, client):
        with self._mock_token_exchange():
            resp = client.get(
                "/api/instagram/callback",
                params={"code": "auth_code_123", "state": "27263512706618393"},
                follow_redirects=False,
            )
        assert resp.status_code in (302, 307)
        location = resp.headers.get("location", "")
        assert "/auth/callback" in location

    def test_callback_includes_ig_user_id_in_redirect(self, client):
        with self._mock_token_exchange(ig_user_id="27263512706618393", username="kelse_y818"):
            resp = client.get(
                "/api/instagram/callback",
                params={"code": "auth_code_123", "state": "27263512706618393"},
                follow_redirects=False,
            )
        location = resp.headers.get("location", "")
        assert "ig_user_id=27263512706618393" in location
        assert "ig_username=kelse_y818" in location

    def test_callback_error_redirects_with_error_param(self, client):
        resp = client.get(
            "/api/instagram/callback",
            params={
                "code": "irrelevant",
                "state": "some_persona",
                "error": "access_denied",
                "error_description": "User denied access",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        location = resp.headers.get("location", "")
        assert "/auth/callback" in location
        assert "error=access_denied" in location

    def test_delete_token_clears_persona(self, client):
        from app.services import instagram_service as svc
        svc._token_store["del_test"] = {
            "access_token": "IGAAtoken",
            "ig_account_id": "777",
            "ig_username": "del_user",
        }
        resp = client.delete("/api/instagram/token/del_test")
        assert resp.status_code == 200
        assert resp.json()["disconnected"] is True
        assert "del_test" not in svc._token_store
