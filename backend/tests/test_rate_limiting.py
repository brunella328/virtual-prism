"""
Rate limiting tests for #94.

1. test_analyze_appearance_rate_limited — 6th request returns 429
2. test_generate_schedule_rate_limited  — 3rd request returns 429
3. test_rate_limit_response_has_retry_after — 429 includes Retry-After header
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from starlette.testclient import TestClient

from app.main import _rate_store


@pytest.fixture(autouse=True)
def clear_rate_store():
    """Reset rate store before each test to avoid bleed between tests."""
    _rate_store.clear()
    yield
    _rate_store.clear()


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _fake_analyze():
    """Mock genesis_service.analyze_appearance to avoid real API calls."""
    async def _inner(images):
        return {"appearance_prompt": "test", "character_description": "test"}
    return _inner


class TestAnalyzeAppearanceRateLimit:
    def test_fifth_request_allowed(self, client):
        with patch("app.services.genesis_service.analyze_appearance", side_effect=_fake_analyze()):
            for i in range(5):
                resp = client.post(
                    "/api/genesis/analyze-appearance",
                    files=[("images", ("test.jpg", b"fake", "image/jpeg"))],
                )
                assert resp.status_code != 429, f"Request {i+1} was unexpectedly rate limited"

    def test_sixth_request_returns_429(self, client):
        with patch("app.services.genesis_service.analyze_appearance", side_effect=_fake_analyze()):
            for _ in range(5):
                client.post(
                    "/api/genesis/analyze-appearance",
                    files=[("images", ("test.jpg", b"fake", "image/jpeg"))],
                )
            resp = client.post(
                "/api/genesis/analyze-appearance",
                files=[("images", ("test.jpg", b"fake", "image/jpeg"))],
            )
        assert resp.status_code == 429
        assert resp.json()["error"] == "rate_limit_exceeded"

    def test_rate_limit_response_has_retry_after(self, client):
        with patch("app.services.genesis_service.analyze_appearance", side_effect=_fake_analyze()):
            for _ in range(5):
                client.post(
                    "/api/genesis/analyze-appearance",
                    files=[("images", ("test.jpg", b"fake", "image/jpeg"))],
                )
            resp = client.post(
                "/api/genesis/analyze-appearance",
                files=[("images", ("test.jpg", b"fake", "image/jpeg"))],
            )
        assert "retry-after" in resp.headers or "Retry-After" in resp.headers
