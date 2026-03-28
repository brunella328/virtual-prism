"""
Tests — Admin Quota Adjust Endpoint
POST /api/admin/quota/adjust
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

API_KEY = "test-api-key"


def _mock_user(email: str, posts_generated: int = 3) -> dict:
    return {
        "uuid": "test-uuid-1234",
        "email": email,
        "hashed_password": "hashed",
        "email_verified": True,
        "posts_generated": posts_generated,
    }


class TestAdminQuotaAdjust:

    def test_add_quota_reduces_posts_generated(self):
        """加額度：posts_generated 減少"""
        user = _mock_user("test@example.com", posts_generated=3)

        with patch("app.services.users_storage.get_user_by_email", return_value=user), \
             patch("app.services.users_storage.save_user") as mock_save, \
             patch.dict("os.environ", {"API_SECRET_KEY": API_KEY}):

            res = client.post(
                "/api/admin/quota/adjust",
                json={"email": "test@example.com", "add": 3},
                headers={"X-Api-Key": API_KEY},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["posts_generated_before"] == 3
        assert data["posts_generated_after"] == 0
        mock_save.assert_called_once()

    def test_add_quota_clamps_to_zero(self):
        """add 超過現有量時，歸零而非負數"""
        user = _mock_user("test@example.com", posts_generated=1)

        with patch("app.services.users_storage.get_user_by_email", return_value=user), \
             patch("app.services.users_storage.save_user"), \
             patch.dict("os.environ", {"API_SECRET_KEY": API_KEY}):

            res = client.post(
                "/api/admin/quota/adjust",
                json={"email": "test@example.com", "add": 10},
                headers={"X-Api-Key": API_KEY},
            )

        assert res.status_code == 200
        assert res.json()["posts_generated_after"] == 0

    def test_reset_sets_to_zero(self):
        """reset=true 直接歸零"""
        user = _mock_user("test@example.com", posts_generated=3)

        with patch("app.services.users_storage.get_user_by_email", return_value=user), \
             patch("app.services.users_storage.save_user"), \
             patch.dict("os.environ", {"API_SECRET_KEY": API_KEY}):

            res = client.post(
                "/api/admin/quota/adjust",
                json={"email": "test@example.com", "reset": True},
                headers={"X-Api-Key": API_KEY},
            )

        assert res.status_code == 200
        assert res.json()["posts_generated_after"] == 0

    def test_user_not_found_returns_404(self):
        """email 不存在回傳 404"""
        with patch("app.services.users_storage.get_user_by_email", return_value=None), \
             patch.dict("os.environ", {"API_SECRET_KEY": API_KEY}):

            res = client.post(
                "/api/admin/quota/adjust",
                json={"email": "nobody@example.com", "reset": True},
                headers={"X-Api-Key": API_KEY},
            )

        assert res.status_code == 404

    def test_missing_add_and_reset_returns_400(self):
        """add 和 reset 都未提供回傳 400"""
        with patch.dict("os.environ", {"API_SECRET_KEY": API_KEY}):
            res = client.post(
                "/api/admin/quota/adjust",
                json={"email": "test@example.com"},
                headers={"X-Api-Key": API_KEY},
            )

        assert res.status_code == 400

    def test_missing_api_key_returns_401(self):
        """無 X-Api-Key 回傳 401"""
        with patch.dict("os.environ", {"API_SECRET_KEY": API_KEY}):
            res = client.post(
                "/api/admin/quota/adjust",
                json={"email": "test@example.com", "reset": True},
            )

        assert res.status_code == 401
