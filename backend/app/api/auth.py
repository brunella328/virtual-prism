"""
Auth API
--------
POST /api/auth/register          — 註冊（email + password），寄驗證信
POST /api/auth/login             — 登入，回傳 JWT（需已驗證 email）
GET  /api/auth/verify-email      — 驗證 email（?token=xxx），回傳 JWT
GET  /api/auth/me                — 當前用戶資訊（需 JWT）
"""
import os
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import resend
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from app.services import users_storage

router = APIRouter()
logger = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY", "")
# Resend 免費版需先驗證 domain 才能用自訂寄件人
# 未驗證時 fallback 到 onboarding@resend.dev（只能寄到 Resend 帳號的 email）
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ── 設定 ────────────────────────────────────────────────────
_IS_PRODUCTION = os.getenv("ENV", "development") == "production"

_raw_secret = os.getenv("JWT_SECRET_KEY", "")
if not _raw_secret:
    if _IS_PRODUCTION:
        raise RuntimeError("JWT_SECRET_KEY must be set in production")
    import logging as _logging
    _logging.getLogger(__name__).critical(
        "⚠️  JWT_SECRET_KEY not set — using insecure default. DO NOT use in production!"
    )
    _raw_secret = "dev-insecure-secret-do-not-use-in-production"
SECRET_KEY = _raw_secret

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 14


# ── 工具函式 ─────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(user_uuid: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_uuid, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _set_auth_cookie(response: Response, token: str) -> None:
    """Attach HttpOnly auth cookie to a response."""
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        secure=_IS_PRODUCTION,           # HTTPS-only in production
        samesite="none" if _IS_PRODUCTION else "lax",  # cross-origin in prod
        max_age=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )


def get_current_user(request: Request) -> dict:
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_uuid: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = users_storage.get_user_by_uuid(user_uuid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ── Email helper ─────────────────────────────────────────────
def _send_verification_email(email: str, token: str) -> None:
    verify_url = f"{FRONTEND_URL}/verify-email?token={token}"
    try:
        resend.Emails.send({
            "from": RESEND_FROM,
            "to": email,
            "subject": "驗證你的 Virtual Prism 帳號",
            "html": f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
  <h2 style="margin-bottom:8px">歡迎加入 Virtual Prism 🌈</h2>
  <p style="color:#555">點擊下方按鈕驗證你的 Email，即可開始使用。</p>
  <a href="{verify_url}"
     style="display:inline-block;margin-top:16px;padding:12px 24px;background:#000;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold">
    驗證 Email
  </a>
  <p style="margin-top:24px;color:#999;font-size:12px">或複製此連結：{verify_url}</p>
</div>""",
        })
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")


# ── Schema ───────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Endpoints ────────────────────────────────────────────────
def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密碼至少需要 8 個字元")
    if not any(c.isupper() for c in password):
        raise HTTPException(status_code=400, detail="密碼需包含至少 1 個大寫字母")
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="密碼需包含至少 1 個數字")


@router.post("/register", status_code=201)
def register(body: RegisterRequest):
    _validate_password(body.password)
    if users_storage.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="此 Email 已被註冊")

    user = users_storage.create_user(body.email, _hash_password(body.password))
    _send_verification_email(user["email"], user["verification_token"])
    verify_url = f"{FRONTEND_URL}/verify-email?token={user['verification_token']}"
    resp = {"message": "註冊成功！請前往信箱點擊驗證連結後即可登入。", "email": user["email"]}
    # Dev mode：FRONTEND_URL 為 localhost 時順便回傳驗證連結，方便測試
    if "localhost" in FRONTEND_URL:
        resp["dev_verify_url"] = verify_url
    return resp


@router.post("/dev/reset-verification")
def dev_reset_verification(body: LoginRequest):
    """DEV：重設帳號為未驗證狀態（方便測試 email 驗證流程）"""
    if _IS_PRODUCTION:
        raise HTTPException(status_code=404, detail="Not found")
    import uuid as _uuid
    user = users_storage.get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["email_verified"] = False
    user["verification_token"] = str(_uuid.uuid4())
    users_storage.save_user(user)
    verify_url = f"{FRONTEND_URL}/verify-email?token={user['verification_token']}"
    return {"message": f"{body.email} 已重設為未驗證", "dev_verify_url": verify_url}


@router.post("/dev/force-verify")
def dev_force_verify(body: LoginRequest, response: Response):
    """DEV：直接驗證帳號，回傳 JWT（跳過 email 流程）"""
    if _IS_PRODUCTION:
        raise HTTPException(status_code=404, detail="Not found")
    user = users_storage.get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["email_verified"] = True
    user["verification_token"] = None
    users_storage.save_user(user)
    token = _create_token(user["uuid"])
    _set_auth_cookie(response, token)
    return {"message": f"{body.email} 已強制驗證", "uuid": user["uuid"]}


@router.post("/dev/reset-quota")
def dev_reset_quota(body: LoginRequest):
    """DEV：重設生成次數為 0"""
    if _IS_PRODUCTION:
        raise HTTPException(status_code=404, detail="Not found")
    user = users_storage.get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["posts_generated"] = 0
    users_storage.save_user(user)
    return {"message": f"{body.email} 生成次數已重設為 0"}


@router.post("/resend-verification")
def resend_verification(body: LoginRequest):
    """重送驗證信（只需 email，不需密碼正確）"""
    user = users_storage.get_user_by_email(body.email)
    if not user:
        # 不洩漏帳號是否存在，一律回成功
        return {"message": "若此 Email 已註冊且尚未驗證，驗證信將會寄出。"}
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="此帳號已完成驗證，請直接登入。")
    # 若沒有 token（舊帳號）就重新產生一個
    if not user.get("verification_token"):
        import uuid as _uuid
        user["verification_token"] = str(_uuid.uuid4())
        users_storage.save_user(user)
    _send_verification_email(user["email"], user["verification_token"])
    resp = {"message": "驗證信已重新寄出，請前往信箱確認。"}
    if "localhost" in FRONTEND_URL:
        resp["dev_verify_url"] = f"{FRONTEND_URL}/verify-email?token={user['verification_token']}"
    return resp


@router.get("/verify-email")
def verify_email(token: str, response: Response):
    user = users_storage.verify_email(token)
    if not user:
        raise HTTPException(status_code=400, detail="驗證連結無效或已過期")
    jwt_token = _create_token(user["uuid"])
    _set_auth_cookie(response, jwt_token)
    return {"uuid": user["uuid"], "email": user["email"]}


@router.post("/login")
def login(body: LoginRequest, response: Response):
    user = users_storage.get_user_by_email(body.email)
    if not user or not _verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Email 或密碼錯誤")
    if not user.get("email_verified", False):
        raise HTTPException(status_code=403, detail="請先驗證 Email，再回來登入。驗證信已寄至你的信箱。")

    token = _create_token(user["uuid"])
    _set_auth_cookie(response, token)
    return {"uuid": user["uuid"], "email": user["email"]}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="token", path="/", samesite="none" if _IS_PRODUCTION else "lax")
    return {"message": "Logged out"}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {
        "uuid": current_user["uuid"],
        "email": current_user["email"],
    }
