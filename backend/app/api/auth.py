"""
Auth API
--------
POST /api/auth/register  — 註冊（email + password）
POST /api/auth/login     — 登入，回傳 JWT
GET  /api/auth/me        — 當前用戶資訊（需 JWT）
POST /api/auth/connect-ig    — 綁定 IG token
DELETE /api/auth/disconnect-ig — 解除 IG 綁定
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from app.services import users_storage, instagram_service

router = APIRouter()

# ── 設定 ────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

bearer_scheme = HTTPBearer()


# ── 工具函式 ─────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(user_uuid: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_uuid, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_uuid: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = users_storage.get_user_by_uuid(user_uuid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ── Schema ───────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ConnectIGRequest(BaseModel):
    ig_token: str
    ig_user_id: str


# ── Endpoints ────────────────────────────────────────────────
@router.post("/register", status_code=201)
def register(body: RegisterRequest):
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if users_storage.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = users_storage.create_user(body.email, _hash_password(body.password))
    token = _create_token(user["uuid"])
    return {"token": token, "uuid": user["uuid"], "email": user["email"]}


@router.post("/login")
def login(body: LoginRequest):
    user = users_storage.get_user_by_email(body.email)
    if not user or not _verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(user["uuid"])
    return {"token": token, "uuid": user["uuid"], "email": user["email"]}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {
        "uuid": current_user["uuid"],
        "email": current_user["email"],
        "has_ig_token": current_user.get("ig_token") is not None,
        "ig_user_id": current_user.get("ig_user_id"),
    }


@router.post("/connect-ig")
def connect_ig(body: ConnectIGRequest, current_user: dict = Depends(get_current_user)):
    user_uuid = current_user["uuid"]
    updated = users_storage.update_ig_token(user_uuid, body.ig_token, body.ig_user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    # 同步更新 instagram_service token store，讓發布功能可用
    instagram_service._token_store[user_uuid] = {
        "access_token": body.ig_token,
        "ig_account_id": body.ig_user_id,
        "ig_username": "",
        "expires_at": "2099-12-31T00:00:00+00:00",
    }
    instagram_service._save_token_store()
    return {"status": "connected", "ig_user_id": body.ig_user_id}


@router.delete("/disconnect-ig")
def disconnect_ig(current_user: dict = Depends(get_current_user)):
    user_uuid = current_user["uuid"]
    users_storage.update_ig_token(user_uuid, None, None)
    # 同步清除 instagram_service token store
    instagram_service._token_store.pop(user_uuid, None)
    instagram_service._save_token_store()
    return {"status": "disconnected"}
