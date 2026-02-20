from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
