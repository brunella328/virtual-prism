"""
Shared fixtures for Virtual Prism backend tests.
"""
import os
import pytest

# ── Set test env vars BEFORE any app import ──────────────────────────────────
os.environ.setdefault("ANTHROPIC_API_KEY",   "test-anthropic-key")
os.environ.setdefault("REPLICATE_API_TOKEN", "test-replicate-token")
os.environ.setdefault("DATABASE_URL",        "sqlite:///./test.db")


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
def clear_rate_store():
    """Reset in-memory rate-limit store before each test to avoid cross-test pollution."""
    from app.main import _rate_store
    _rate_store.clear()
    yield
    _rate_store.clear()
