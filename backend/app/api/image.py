from fastapi import APIRouter
from pydantic import BaseModel
from app.services import comfyui_service

router = APIRouter()

class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = "ugly, blurry, low quality, deformed"
    seed: int = -1
    width: int = 1024
    height: int = 1024

class RegenerateRequest(BaseModel):
    original_prompt: str
    instruction: str = ""
    seed: int = -1

@router.get("/health")
async def comfyui_health():
    """檢查 ComfyUI 連線狀態"""
    ok = await comfyui_service.health_check()
    return {"comfyui_available": ok, "mock_mode": comfyui_service.MOCK_MODE}

@router.post("/generate")
async def generate(req: GenerateRequest):
    """T5: 生成圖片"""
    result = await comfyui_service.generate_image(
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        seed=req.seed,
        width=req.width,
        height=req.height,
    )
    return result

@router.post("/regenerate")
async def regenerate(req: RegenerateRequest):
    """T8: 一鍵重繪（附加指令）"""
    enhanced_prompt = f"{req.original_prompt}, {req.instruction}" if req.instruction else req.original_prompt
    result = await comfyui_service.generate_image(
        prompt=enhanced_prompt,
        seed=req.seed,
    )
    return result
