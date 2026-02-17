from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Virtual Prism API",
    description="B2B AI 虛擬網紅自動化營運平台",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "virtual-prism-api"}

# Routers (to be implemented)
# from app.api import genesis, life_stream, interact
# app.include_router(genesis.router, prefix="/api/genesis")
# app.include_router(life_stream.router, prefix="/api/life-stream")
# app.include_router(interact.router, prefix="/api/interact")
