import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import genesis, life_stream, interact, image, instagram, fans, poc
from app.services.instagram_service import get_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start APScheduler + register token refresh jobs on startup
    start_scheduler()
    yield
    # Graceful shutdown
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Virtual Prism API",
    description="B2B AI 虛擬網紅自動化營運平台",
    version="0.1.0",
    lifespan=lifespan,
)

_PUBLIC_PATHS = {
    "/health",
    "/api/instagram/auth",
    "/api/instagram/callback",
    "/api/interact/webhook/instagram",
}

# Rate limiting: sliding window per key
_RATE_LIMITS = {
    "/api/genesis/analyze-appearance":     {"max": 5, "window": 60},
    "/api/life-stream/generate-schedule/": {"max": 2, "window": 60},
}
_rate_store: dict = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    for prefix, limits in _RATE_LIMITS.items():
        if path.startswith(prefix):
            # Key: last path segment (persona_id) or client IP
            client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
            key = f"{prefix}:{path.split('/')[-1] or client_ip}"
            now = time.monotonic()
            window = limits["window"]
            _rate_store[key] = [t for t in _rate_store[key] if now - t < window]
            if len(_rate_store[key]) >= limits["max"]:
                return JSONResponse(
                    {"error": "rate_limit_exceeded", "detail": f"最多每 {window} 秒 {limits['max']} 次"},
                    status_code=429,
                    headers={"Retry-After": str(window)},
                )
            _rate_store[key].append(now)
            break
    return await call_next(request)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    expected = os.getenv("API_SECRET_KEY", "")
    if expected and request.headers.get("X-Api-Key", "") != expected:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(genesis.router, prefix="/api/genesis", tags=["Genesis Engine"])
app.include_router(image.router, prefix="/api/image", tags=["Image Generation"])
app.include_router(life_stream.router, prefix="/api/life-stream", tags=["Life Stream"])
app.include_router(interact.router, prefix="/api/interact", tags=["Interaction Hub"])
app.include_router(instagram.router, prefix="/api/instagram", tags=["Instagram (T9)"])
app.include_router(fans.router, prefix="/api/fans", tags=["Fan Memory"])
app.include_router(poc.router, prefix="/api", tags=["POC"])


@app.get("/health")
async def health():
    scheduler = get_scheduler()
    return {
        "status": "ok",
        "service": "virtual-prism-api",
        "version": "0.1.0",
        "scheduler_running": scheduler.running,
    }
