from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services import life_stream_service

router = APIRouter()

class GenerateScheduleRequest(BaseModel):
    persona: dict
    appearance_prompt: Optional[str] = ""

class RegenerateRequest(BaseModel):
    original_prompt: str
    instruction: Optional[str] = ""

@router.post("/generate-schedule/{persona_id}")
async def generate_schedule(persona_id: str, req: GenerateScheduleRequest):
    """T6: 根據人設自動規劃 7 天圖文內容（含生圖）"""
    return await life_stream_service.generate_weekly_schedule(
        persona_id=persona_id,
        persona=req.persona,
        appearance_prompt=req.appearance_prompt or ""
    )

@router.post("/regenerate/{content_id}")
async def regenerate(content_id: str, req: RegenerateRequest):
    """T8: 一鍵重繪"""
    return await life_stream_service.regenerate_content(
        content_id=content_id,
        original_prompt=req.original_prompt,
        instruction=req.instruction or ""
    )
