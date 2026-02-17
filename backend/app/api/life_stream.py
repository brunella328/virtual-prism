from fastapi import APIRouter
from app.services import life_stream_service

router = APIRouter()

@router.post("/generate-schedule/{persona_id}")
async def generate_schedule(persona_id: str):
    """T6: 根據人設自動規劃 7 天圖文內容"""
    return await life_stream_service.generate_weekly_schedule(persona_id)

@router.post("/regenerate/{content_id}")
async def regenerate(content_id: str, instruction: str = ""):
    """T8: 一鍵重繪"""
    return await life_stream_service.regenerate(content_id, instruction)
