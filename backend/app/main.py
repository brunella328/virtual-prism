import asyncio
import logging
import os
import time
import uuid as _uuid
from collections import defaultdict
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api import genesis, life_stream, image, poc, auth, chat_sessions
from app.services import backup_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start periodic backup scheduler as a background task
    task = asyncio.create_task(backup_service.backup_scheduler())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Virtual Prism API",
    description="B2B AI 虛擬網紅自動化營運平台",
    version="0.1.0",
    lifespan=lifespan,
)

_PUBLIC_PATHS = {
    "/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/verify-email",
    "/api/auth/resend-verification",
    "/api/auth/dev/reset-verification",
    "/api/auth/dev/force-verify",
    "/api/auth/dev/reset-quota",
    "/api/auth/logout",
}

# ---------------------------------------------------------------------------
# Rate limiting — Redis (preferred) with in-memory fallback
# ---------------------------------------------------------------------------
# key_by: "persona" = last URL path segment, "ip" = client IP
_RATE_LIMITS = {
    "/api/genesis/analyze-appearance":     {"max": 5,  "window": 60,   "key_by": "persona"},
    "/api/life-stream/generate-schedule/": {"max": 2,  "window": 60,   "key_by": "persona"},
    "/api/auth/register":                  {"max": 10, "window": 3600, "key_by": "ip"},
    "/api/auth/login":                     {"max": 10, "window": 900,  "key_by": "ip"},
}

# Try to connect to Redis; fall back to in-memory if REDIS_URL is absent or unreachable.
_redis = None
_redis_url = os.getenv("REDIS_URL", "")
if _redis_url:
    try:
        import redis as _redis_module
        _redis = _redis_module.from_url(_redis_url, decode_responses=True, socket_connect_timeout=2)
        _redis.ping()
        logger.info("Rate limiter: connected to Redis at %s", _redis_url.split("@")[-1])
    except Exception as exc:
        logger.warning("Rate limiter: Redis unavailable (%s) — falling back to in-memory", exc)
        _redis = None
else:
    logger.info("Rate limiter: REDIS_URL not set — using in-memory store")

# In-memory fallback store (single-process only)
_rate_store: dict = defaultdict(list)


def _is_rate_limited(key: str, max_req: int, window: int) -> bool:
    """
    Sliding-window rate check.
    Returns True if the request should be rejected (limit exceeded).
    Uses Redis sorted-set when available, in-memory list otherwise.
    """
    if _redis is not None:
        now = time.time()
        pipe = _redis.pipeline()
        pipe.zremrangebyscore(key, "-inf", now - window)   # evict stale entries
        pipe.zcard(key)                                     # count remaining
        _, count = pipe.execute()
        if count >= max_req:
            return True
        # Allow — record this request
        _redis.zadd(key, {str(_uuid.uuid4()): now})
        _redis.expire(key, window + 1)
        return False
    else:
        now = time.monotonic()
        _rate_store[key] = [t for t in _rate_store[key] if now - t < window]
        if len(_rate_store[key]) >= max_req:
            return True
        _rate_store[key].append(now)
        return False


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    for prefix, limits in _RATE_LIMITS.items():
        if path.startswith(prefix):
            client_ip = (
                request.headers
                .get("X-Forwarded-For", request.client.host if request.client else "unknown")
                .split(",")[0]
                .strip()
            )
            segment = path.split("/")[-1]
            key = f"rl:{prefix}:{client_ip if limits['key_by'] == 'ip' else (segment or client_ip)}"
            if _is_rate_limited(key, limits["max"], limits["window"]):
                return JSONResponse(
                    {"error": "rate_limit_exceeded", "detail": "請求過於頻繁，請稍後再試"},
                    status_code=429,
                    headers={"Retry-After": str(limits["window"])},
                )
            break
    return await call_next(request)


# ---------------------------------------------------------------------------
# API key guard
# ---------------------------------------------------------------------------

_IS_PRODUCTION = os.getenv("ENV", "development") == "production"


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    expected = os.getenv("API_SECRET_KEY", "")
    if not expected:
        if _IS_PRODUCTION:
            return JSONResponse({"detail": "Server misconfiguration"}, status_code=500)
        return await call_next(request)
    if request.headers.get("X-Api-Key", "") != expected:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
]
_allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", ",".join(_default_origins)).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Api-Key"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(genesis.router,     prefix="/api/genesis",      tags=["Genesis Engine"])
app.include_router(image.router,       prefix="/api/image",        tags=["Image Generation"])
app.include_router(life_stream.router, prefix="/api/life-stream",  tags=["Life Stream"])
app.include_router(poc.router,         prefix="/api",              tags=["POC"])
app.include_router(auth.router,        prefix="/api/auth",         tags=["Auth"])
app.include_router(chat_sessions.router, prefix="/api",             tags=["Chat Sessions"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "virtual-prism-api",
        "version": "0.1.0",
        "rate_limiter": "redis" if _redis is not None else "memory",
        "backup": backup_service.get_status(),
    }


@app.post("/api/admin/backup")
async def trigger_backup():
    """Manual on-demand backup (requires X-Api-Key header)."""
    result = backup_service.run_backup()
    if result == "ok":
        return {"status": "ok", **backup_service.get_status()}
    return JSONResponse({"status": "error", "detail": result}, status_code=500)


class QuotaAdjustRequest(BaseModel):
    email: str
    add: int = 0        # 加額度：posts_generated -= add（最低為 0）
    reset: bool = False # 歸零：posts_generated = 0


class ForceVerifyRequest(BaseModel):
    email: str


@app.post("/api/admin/force-verify")
def admin_force_verify(body: ForceVerifyRequest, response: Response):
    """Admin：強制驗證帳號並回傳 JWT（需要 X-Api-Key header）"""
    from app.services import users_storage
    from app.api.auth import _create_token, _set_auth_cookie
    user = users_storage.get_user_by_email(body.email)
    if not user:
        return JSONResponse({"detail": f"User not found: {body.email}"}, status_code=404)
    user["email_verified"] = True
    user["verification_token"] = None
    users_storage.save_user(user)
    token = _create_token(user["uuid"])
    _set_auth_cookie(response, token)
    return {"message": f"{body.email} 已強制驗證", "uuid": user["uuid"]}

@app.post("/api/admin/quota/adjust")
def admin_quota_adjust(body: QuotaAdjustRequest):
    """Admin：調整用戶 quota（需要 X-Api-Key header）"""
    from app.services import users_storage
    if not body.add and not body.reset:
        return JSONResponse({"detail": "add 或 reset 至少提供一個"}, status_code=400)
    user = users_storage.get_user_by_email(body.email)
    if not user:
        return JSONResponse({"detail": f"User not found: {body.email}"}, status_code=404)
    before = user.get("posts_generated", 0)
    if body.reset:
        user["posts_generated"] = 0
    elif body.add:
        user["posts_generated"] = max(0, before - body.add)
    users_storage.save_user(user)
    return {
        "email": body.email,
        "posts_generated_before": before,
        "posts_generated_after": user["posts_generated"],
    }
