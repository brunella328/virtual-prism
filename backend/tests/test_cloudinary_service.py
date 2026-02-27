"""
Unit tests for cloudinary_service.py
Mocks httpx — no real Cloudinary calls.
"""
import os
import pytest
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure env vars are set before importing the module
os.environ.setdefault("CLOUDINARY_CLOUD_NAME", "test_cloud")
os.environ.setdefault("CLOUDINARY_API_KEY", "test_api_key")
os.environ.setdefault("CLOUDINARY_API_SECRET", "test_api_secret")


def _make_mock_response(status_code: int, json_body: dict):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_body
    mock.text = str(json_body)
    return mock


class TestUploadFromUrl:
    @pytest.mark.asyncio
    async def test_success_returns_secure_url(self):
        from app.services.cloudinary_service import upload_from_url
        mock_resp = _make_mock_response(200, {"secure_url": "https://res.cloudinary.com/test_cloud/image/upload/v1/test/img.jpg"})
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await upload_from_url("https://replicate.delivery/test.jpg", folder="virtual_prism/123")

        assert result == "https://res.cloudinary.com/test_cloud/image/upload/v1/test/img.jpg"

    @pytest.mark.asyncio
    async def test_request_uses_file_param_not_url(self):
        """Critical: Cloudinary URL upload requires 'file' field, not 'url'."""
        from app.services.cloudinary_service import upload_from_url
        mock_resp = _make_mock_response(200, {"secure_url": "https://res.cloudinary.com/x.jpg"})
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            await upload_from_url("https://replicate.delivery/test.jpg")

            _, kwargs = mock_client.post.call_args
            data = kwargs.get("data", {})
            assert "file" in data, "Must use 'file' param for Cloudinary URL upload"
            assert "url" not in data, "'url' param is wrong — Cloudinary ignores it"
            assert data["file"] == "https://replicate.delivery/test.jpg"

    @pytest.mark.asyncio
    async def test_request_includes_required_fields(self):
        from app.services.cloudinary_service import upload_from_url
        mock_resp = _make_mock_response(200, {"secure_url": "https://res.cloudinary.com/x.jpg"})
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            await upload_from_url("https://example.com/img.jpg", folder="vp/abc")

            _, kwargs = mock_client.post.call_args
            data = kwargs["data"]
            assert "api_key" in data
            assert "signature" in data
            assert "timestamp" in data
            assert data["folder"] == "vp/abc"

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        from app.services.cloudinary_service import upload_from_url
        mock_resp = _make_mock_response(400, {"error": {"message": "Bad request"}})
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Cloudinary 上傳失敗"):
                await upload_from_url("https://example.com/img.jpg")

    @pytest.mark.asyncio
    async def test_raises_when_env_vars_missing(self, monkeypatch):
        monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "")
        monkeypatch.setenv("CLOUDINARY_API_KEY", "")
        monkeypatch.setenv("CLOUDINARY_API_SECRET", "")
        # Re-import to pick up empty env vars
        import importlib
        import app.services.cloudinary_service as cs
        monkeypatch.setattr(cs, "CLOUDINARY_CLOUD_NAME", "")
        monkeypatch.setattr(cs, "CLOUDINARY_API_KEY", "")
        monkeypatch.setattr(cs, "CLOUDINARY_API_SECRET", "")

        with pytest.raises(ValueError, match="環境變數未設定"):
            await cs.upload_from_url("https://example.com/img.jpg")


class TestMakeSignature:
    def test_signature_is_sha1_of_sorted_params_plus_secret(self):
        from app.services.cloudinary_service import _make_signature
        params = {"folder": "test", "timestamp": "1000000"}
        secret = "mysecret"
        expected = hashlib.sha1(
            f"folder=test&timestamp=1000000{secret}".encode()
        ).hexdigest()
        assert _make_signature(params, secret) == expected

    def test_params_are_sorted(self):
        from app.services.cloudinary_service import _make_signature
        params_ab = {"a": "1", "b": "2"}
        params_ba = {"b": "2", "a": "1"}
        assert _make_signature(params_ab, "s") == _make_signature(params_ba, "s")
