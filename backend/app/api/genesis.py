from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
from app.models.persona import PersonaCreate, PersonaCard, PersonaResponse
from app.services import genesis_service

router = APIRouter()

@router.post("/analyze-appearance")
async def analyze_appearance(
    images: List[UploadFile] = File(...),
):
    """T2: 視覺反推 — 分析上傳圖片，輸出外觀描述 Prompt"""
    if len(images) > 3:
        raise HTTPException(400, "最多上傳 3 張圖片")
    return await genesis_service.analyze_appearance(images)

@router.post("/create-persona")
async def create_persona(
    description: str = Form(...),
):
    """T3: 人設稜鏡 — 一句話描述生成完整人設 JSON"""
    return await genesis_service.create_persona(description)

@router.post("/confirm-persona")
async def confirm_persona(persona: PersonaCard):
    """T4: 確認並鎖定人設"""
    return await genesis_service.confirm_persona(persona)
