"""
Security tests — API Key middleware, UUID path traversal, password complexity,
dev-endpoint production guards.
"""
import os
import uuid
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

_API_KEY = "test-api-secret-key"


@pytest.fixture(scope="module")
def set_api_key_env():
    """Set API_SECRET_KEY; restore on teardown."""
    prev = os.environ.get("API_SECRET_KEY")
    os.environ["API_SECRET_KEY"] = _API_KEY
    yield
    if prev is None:
        os.environ.pop("API_SECRET_KEY", None)
    else:
        os.environ["API_SECRET_KEY"] = prev


@pytest.fixture(scope="module")
def secured_client(set_api_key_env):
    """Client that connects to an app instance with API_SECRET_KEY set."""
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# API Key middleware
# ─────────────────────────────────────────────────────────────────────────────

class TestApiKeyMiddleware:
    """
    Uses GET /api/auth/me as a protected route.
    With a valid API key but no JWT the downstream HTTPBearer returns 403,
    which proves the middleware passed the request through (not 401).
    """

    def test_no_api_key_returns_401(self, secured_client):
        resp = secured_client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_wrong_api_key_returns_401(self, secured_client):
        resp = secured_client.get(
            "/api/auth/me",
            headers={"X-Api-Key": "totally-wrong-key"},
        )
        assert resp.status_code == 401

    def test_correct_api_key_passes_middleware(self, secured_client):
        # Correct key passes middleware; cookie-based auth guard rejects missing
        # cookie with detail "Not authenticated" — distinct from the middleware's
        # "Unauthorized" rejection.
        resp = secured_client.get(
            "/api/auth/me",
            headers={"X-Api-Key": _API_KEY},
        )
        # Middleware rejection would say "Unauthorized"; auth guard says "Not authenticated"
        assert resp.json().get("detail") != "Unauthorized"

    def test_public_health_bypasses_auth(self, secured_client):
        resp = secured_client.get("/health")
        assert resp.status_code == 200

    def test_public_auth_register_bypasses_key(self, secured_client):
        """Register is in _PUBLIC_PATHS — API key should not be required."""
        with patch("app.api.auth._send_verification_email"):
            resp = secured_client.post(
                "/api/auth/register",
                json={"email": f"sec_{uuid.uuid4().hex[:6]}@test.com", "password": "Testpass1"},
            )
        assert resp.status_code != 401


# ─────────────────────────────────────────────────────────────────────────────
# UUID / path traversal prevention
# ─────────────────────────────────────────────────────────────────────────────

class TestPathTraversalPrevention:
    """persona_storage and users_storage both validate IDs against UUID regex."""

    def test_invalid_persona_id_raises(self):
        from app.services.persona_storage import load_persona
        with pytest.raises(ValueError, match="Invalid persona_id"):
            load_persona("../etc/passwd")

    def test_non_uuid_persona_id_raises(self):
        from app.services.persona_storage import load_persona
        with pytest.raises(ValueError, match="Invalid persona_id"):
            load_persona("not-a-uuid")

    def test_invalid_user_uuid_raises(self):
        from app.services.users_storage import get_user_by_uuid
        with pytest.raises(ValueError, match="Invalid user UUID"):
            get_user_by_uuid("../../secrets")

    def test_valid_uuid_does_not_raise(self):
        from app.services.persona_storage import load_persona
        # A well-formed UUID should not raise (returns None if not found)
        result = load_persona(str(uuid.uuid4()))
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Password complexity
# ─────────────────────────────────────────────────────────────────────────────

class TestPasswordComplexity:
    def test_too_short_password_rejected(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"email": "pw@test.com", "password": "Ab1"},
        )
        assert resp.status_code == 400
        assert "8" in resp.json()["detail"]

    def test_no_uppercase_rejected(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"email": "pw@test.com", "password": "testpass1"},
        )
        assert resp.status_code == 400
        assert "大寫" in resp.json()["detail"]

    def test_no_digit_rejected(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"email": "pw@test.com", "password": "Testpassword"},
        )
        assert resp.status_code == 400
        assert "數字" in resp.json()["detail"]

    def test_valid_password_accepted(self, client):
        with patch("app.api.auth._send_verification_email"):
            resp = client.post(
                "/api/auth/register",
                json={
                    "email": f"pw_{uuid.uuid4().hex[:6]}@test.com",
                    "password": "Testpass1",
                },
            )
        assert resp.status_code == 201


# ─────────────────────────────────────────────────────────────────────────────
# Dev endpoint production guards
# ─────────────────────────────────────────────────────────────────────────────

class TestDevEndpointGuards:
    """Dev endpoints must return 404 when ENV=production."""

    @pytest.fixture(autouse=True)
    def set_production(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        # Patch the module-level flag used by auth.py
        import app.api.auth as auth_module
        monkeypatch.setattr(auth_module, "_IS_PRODUCTION", True)

    def test_reset_verification_hidden_in_prod(self, client):
        resp = client.post(
            "/api/auth/dev/reset-verification",
            json={"email": "any@test.com", "password": ""},
        )
        assert resp.status_code == 404

    def test_force_verify_hidden_in_prod(self, client):
        resp = client.post(
            "/api/auth/dev/force-verify",
            json={"email": "any@test.com", "password": ""},
        )
        assert resp.status_code == 404

    def test_reset_quota_hidden_in_prod(self, client):
        resp = client.post(
            "/api/auth/dev/reset-quota",
            json={"email": "any@test.com", "password": ""},
        )
        assert resp.status_code == 404
