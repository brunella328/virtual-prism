"""
Security tests for #92 — API Key middleware + Webhook signature verification.

1. test_no_api_key_returns_401          — no X-Api-Key header → 401
2. test_wrong_api_key_returns_401       — wrong key → 401
3. test_correct_api_key_returns_200     — correct key → 200
4. test_public_paths_bypass_auth        — /health and webhook GET skip auth
5. test_webhook_invalid_sig_returns_403 — POST /webhook with bad sig → 403
6. test_webhook_valid_sig_passes        — POST /webhook with correct sig → 200
"""
import hashlib
import hmac
import json
import os

import pytest
from starlette.testclient import TestClient

_API_KEY = "test-api-secret-key"
_APP_SECRET = "test-app-secret"


@pytest.fixture(scope="module")
def set_security_env():
    """Set API_SECRET_KEY and INSTAGRAM_APP_SECRET, restore on teardown."""
    prev_key = os.environ.get("API_SECRET_KEY")
    prev_secret = os.environ.get("INSTAGRAM_APP_SECRET")
    os.environ["API_SECRET_KEY"] = _API_KEY
    os.environ["INSTAGRAM_APP_SECRET"] = _APP_SECRET
    yield
    if prev_key is None:
        os.environ.pop("API_SECRET_KEY", None)
    else:
        os.environ["API_SECRET_KEY"] = prev_key
    if prev_secret is None:
        os.environ.pop("INSTAGRAM_APP_SECRET", None)
    else:
        os.environ["INSTAGRAM_APP_SECRET"] = prev_secret


@pytest.fixture(scope="module")
def client(set_security_env):
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# API Key middleware
# ─────────────────────────────────────────────────────────────────────────────

class TestApiKeyMiddleware:
    def test_no_api_key_returns_401(self, client):
        resp = client.get("/api/instagram/status?persona_id=default")
        assert resp.status_code == 401

    def test_wrong_api_key_returns_401(self, client):
        resp = client.get(
            "/api/instagram/status?persona_id=default",
            headers={"X-Api-Key": "totally-wrong-key"},
        )
        assert resp.status_code == 401

    def test_correct_api_key_returns_200(self, client):
        resp = client.get(
            "/api/instagram/status?persona_id=default",
            headers={"X-Api-Key": _API_KEY},
        )
        assert resp.status_code == 200

    def test_public_paths_bypass_auth(self, client):
        # /health — no key needed
        resp = client.get("/health")
        assert resp.status_code == 200

        # GET /api/interact/webhook/instagram — hub verification (public)
        resp = client.get(
            "/api/interact/webhook/instagram",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "",
                "hub.challenge": "test123",
            },
        )
        # Not 401 — middleware bypassed for this path
        assert resp.status_code != 401


# ─────────────────────────────────────────────────────────────────────────────
# Webhook signature verification
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookSignature:
    def _make_sig(self, body: bytes, secret: str) -> str:
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_webhook_invalid_sig_returns_403(self, client):
        body = json.dumps({"entry": []}).encode()
        resp = client.post(
            "/api/interact/webhook/instagram",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalidsignature",
            },
        )
        assert resp.status_code == 403

    def test_webhook_valid_sig_passes(self, client):
        body = json.dumps({"entry": []}).encode()
        sig = self._make_sig(body, _APP_SECRET)
        resp = client.post(
            "/api/interact/webhook/instagram",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
        )
        assert resp.status_code == 200
