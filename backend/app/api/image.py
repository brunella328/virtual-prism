from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services import comfyui_service
from app.services.ai_detector_service import detect_ai_image

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str
    seed: int = 42
    face_image_url: str = ""
    camera_style: str = "lifestyle"


class RetestRequest(BaseModel):
    """T5: 回測 — 生圖 + 立即跑 Hive 檢測，回傳圖片 URL 與 AI 分數"""
    prompt: str
    seed: int = 42
    face_image_url: str = ""
    camera_style: str = "lifestyle"


@router.post("/generate")
async def generate(req: GenerateRequest):
    """生成圖片（Mode A: kontext-max，Mode B: flux-dev-realism）"""
    image_url = await comfyui_service.generate_image(
        prompt=req.prompt,
        seed=req.seed,
        face_image_url=req.face_image_url,
        camera_style=req.camera_style,
    )
    return {"image_url": image_url}


@router.post("/retest")
async def retest(req: RetestRequest):
    """T5: 回測 endpoint — 生圖 + Hive AI 分數"""
    image_url = await comfyui_service.generate_image(
        prompt=req.prompt,
        seed=req.seed,
        face_image_url=req.face_image_url,
        camera_style=req.camera_style,
    )
    hive_score = await detect_ai_image(image_url) if image_url else -1.0
    return {
        "image_url": image_url,
        "hive_score": hive_score,
        "pass": hive_score != -1.0 and hive_score < 0.3,
    }
