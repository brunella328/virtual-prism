"""
Tests for APScheduler persistence and token refresh reliability.

1. test_scheduler_jobstore_is_sqlalchemy   — jobstore is SQLAlchemyJobStore
2. test_token_refresh_does_not_write_env   — refresh_instagram_token() never writes .env
3. test_init_env_token_does_not_overwrite_existing — _init_env_token() skips if "default" already set
"""
import pytest
from unittest.mock import patch, MagicMock, call


def _svc():
    from app.services import instagram_service as svc
    return svc


# ─────────────────────────────────────────────────────────────────────────────
# T1 — APScheduler jobstore
# ─────────────────────────────────────────────────────────────────────────────

class TestSchedulerJobstore:
    def test_scheduler_jobstore_is_sqlalchemy(self):
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        svc = _svc()
        jobstores = svc._scheduler._jobstores
        assert "default" in jobstores, "_scheduler has no 'default' jobstore"
        assert isinstance(jobstores["default"], SQLAlchemyJobStore), (
            f"Expected SQLAlchemyJobStore, got {type(jobstores['default'])}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T2 — Token refresh 不寫 .env
# ─────────────────────────────────────────────────────────────────────────────

class TestTokenRefreshNoEnvWrite:
    def test_token_refresh_does_not_write_env(self):
        svc = _svc()

        # Seed token store so refresh has something to work with
        svc._token_store["test_persona"] = {
            "access_token": "IGAAtest_old_token",
            "ig_account_id": "111",
            "ig_username": "test_user",
        }

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "access_token": "IGAAtest_new_token",
            "expires_in": 5183944,
        }
        mock_resp.raise_for_status = MagicMock()

        opened_paths = []

        real_open = open

        def tracking_open(path, *args, **kwargs):
            opened_paths.append(str(path))
            return real_open(path, *args, **kwargs)

        with patch("app.services.instagram_service.requests.get", return_value=mock_resp), \
             patch("app.services.instagram_service._save_token_store") as mock_save, \
             patch("app.services.instagram_service._send_telegram"), \
             patch("builtins.open", side_effect=tracking_open):
            svc.refresh_instagram_token("test_persona")

        # Verify token was refreshed in memory
        assert svc._token_store["test_persona"]["access_token"] == "IGAAtest_new_token"

        # Verify _save_token_store was called (JSON persistence)
        mock_save.assert_called_once()

        # Verify .env was never opened
        env_paths = [p for p in opened_paths if p.endswith(".env")]
        assert len(env_paths) == 0, (
            f"refresh_instagram_token() wrote to .env: {env_paths}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T3 — _init_env_token 不覆蓋已有 token
# ─────────────────────────────────────────────────────────────────────────────

class TestInitEnvTokenNoOverwrite:
    def test_init_env_token_does_not_overwrite_existing(self):
        svc = _svc()

        existing_token = "IGAA_existing_token_from_json"
        svc._token_store["default"] = {
            "access_token": existing_token,
            "ig_account_id": "777",
            "ig_username": "real_user",
        }

        # _ENV_ACCESS_TOKEN and _ENV_USER_ID are set by conftest.py
        # Call _init_env_token() — should be a no-op because "default" already exists
        svc._init_env_token()

        assert svc._token_store["default"]["access_token"] == existing_token, (
            "_init_env_token() overwrote existing token with env value"
        )
