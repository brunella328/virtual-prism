"""
Tests for #146: Auth system — rate limiting, email verification, post quota
"""
import pytest
import uuid
from unittest.mock import patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _register(client, email=None, password="testpass1"):
    email = email or f"user_{uuid.uuid4().hex[:8]}@test.com"
    with patch("app.api.auth._send_verification_email"):
        res = client.post("/api/auth/register", json={"email": email, "password": password})
    return res, email


def _verify(client, email):
    """Manually mark a user as verified and return their JWT."""
    from app.services import users_storage
    user = users_storage.get_user_by_email(email)
    user["email_verified"] = True
    user["verification_token"] = None
    users_storage.save_user(user)
    res = client.post("/api/auth/login", json={"email": email, "password": "testpass1"})
    return res.json()["token"]


def _cleanup(email):
    from app.services import users_storage
    import os
    user = users_storage.get_user_by_email(email)
    if user:
        path = users_storage._path(user["uuid"])
        if path.exists():
            os.remove(path)


# ── AC3: 未驗證帳號無法登入 ───────────────────────────────────────────────────

def test_unverified_cannot_login(client):
    res, email = _register(client)
    assert res.status_code == 201

    login = client.post("/api/auth/login", json={"email": email, "password": "testpass1"})
    assert login.status_code == 403
    assert "驗證" in login.json()["detail"]
    _cleanup(email)


# ── AC4: verify-email token 驗證後可登入 ─────────────────────────────────────

def test_verify_email_token_flow(client):
    res, email = _register(client)
    assert res.status_code == 201

    from app.services import users_storage
    user = users_storage.get_user_by_email(email)
    token = user["verification_token"]

    verify = client.get(f"/api/auth/verify-email?token={token}")
    assert verify.status_code == 200
    data = verify.json()
    assert "token" in data
    assert data["email"] == email

    # 驗證後可正常登入
    login = client.post("/api/auth/login", json={"email": email, "password": "testpass1"})
    assert login.status_code == 200
    _cleanup(email)


def test_invalid_verify_token_returns_400(client):
    res = client.get("/api/auth/verify-email?token=invalid-token-xxx")
    assert res.status_code == 400


# ── resend-verification ───────────────────────────────────────────────────────

def test_resend_verification(client):
    res, email = _register(client)
    assert res.status_code == 201

    with patch("app.api.auth._send_verification_email") as mock_send:
        resend = client.post("/api/auth/resend-verification",
                             json={"email": email, "password": ""})
    assert resend.status_code == 200
    assert mock_send.called
    _cleanup(email)


def test_resend_already_verified_returns_400(client):
    res, email = _register(client)
    _verify(client, email)

    resend = client.post("/api/auth/resend-verification",
                         json={"email": email, "password": ""})
    assert resend.status_code == 400
    _cleanup(email)


# ── AC5: 生成配額 3 篇 ────────────────────────────────────────────────────────

def test_posts_generated_quota(client):
    from app.services import users_storage

    res, email = _register(client)
    token = _verify(client, email)
    user = users_storage.get_user_by_email(email)

    # 手動設定已生成 3 篇
    user["posts_generated"] = 3
    users_storage.save_user(user)

    # generate-post 應回 403
    import io
    form_data = {"date": "2026-03-15", "appearance_prompt": ""}
    res = client.post(
        f"/api/life-stream/generate-post/{user['uuid']}",
        data=form_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "上限" in res.json()["detail"]
    _cleanup(email)


def test_posts_generated_increments(client):
    from app.services import users_storage
    from unittest.mock import AsyncMock

    res, email = _register(client)
    token = _verify(client, email)
    user = users_storage.get_user_by_email(email)
    assert user.get("posts_generated", 0) == 0

    # 模擬生成成功，確認計數 +1
    users_storage.increment_posts_generated(user["uuid"], 1)
    user = users_storage.get_user_by_email(email)
    assert user["posts_generated"] == 1
    _cleanup(email)


# ── AC6: generate-post 需 JWT ─────────────────────────────────────────────────

def test_generate_post_requires_jwt(client):
    fake_id = str(uuid.uuid4())
    import io
    res = client.post(
        f"/api/life-stream/generate-post/{fake_id}",
        data={"date": "2026-03-15", "appearance_prompt": ""},
    )
    # 無 JWT → 401
    assert res.status_code == 403 or res.status_code == 401


# ── dev reset-verification ───────────────────────────────────────────────────

def test_dev_reset_verification(client):
    res, email = _register(client)
    _verify(client, email)

    reset = client.post("/api/auth/dev/reset-verification",
                        json={"email": email, "password": ""})
    assert reset.status_code == 200
    assert "dev_verify_url" in reset.json()

    from app.services import users_storage
    user = users_storage.get_user_by_email(email)
    assert user["email_verified"] is False
    _cleanup(email)
