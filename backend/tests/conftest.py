"""
Shared fixtures for Virtual Prism backend tests.
"""
import os
import pytest

# ── Set test env vars BEFORE any app import ──────────────────────────────────
os.environ.setdefault("ANTHROPIC_API_KEY",        "test-anthropic-key")
os.environ.setdefault("REPLICATE_API_TOKEN",      "test-replicate-token")
os.environ.setdefault("INSTAGRAM_APP_ID",         "test-app-id")
os.environ.setdefault("INSTAGRAM_APP_SECRET",     "test-app-secret")
os.environ.setdefault("INSTAGRAM_REDIRECT_URI",   "http://localhost:8000/api/instagram/callback")
os.environ.setdefault("INSTAGRAM_ACCESS_TOKEN",   "EAAtest_access_token")
os.environ.setdefault("INSTAGRAM_USER_ID",        "999000111")
os.environ.setdefault("INSTAGRAM_USERNAME",       "test_ig_user")
os.environ.setdefault("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000")
# Disable real DB connections
os.environ.setdefault("DATABASE_URL",             "sqlite:///./test.db")


@pytest.fixture(scope="session")
def app():
    """Create FastAPI test app once per session."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """Sync Starlette TestClient (wraps httpx with ASGI)."""
    from starlette.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_token_store():
    """Ensure token store starts clean (except the env-seeded default) for each test."""
    from app.services import instagram_service as svc
    # Save state, yield, restore
    saved = dict(svc._token_store)
    yield
    svc._token_store.clear()
    svc._token_store.update(saved)
