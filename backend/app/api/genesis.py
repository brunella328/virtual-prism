from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
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
    
    try:
        return await genesis_service.analyze_appearance(images)
    except Exception as e:
        import anthropic
        # 特殊处理 Claude API Rate Limit
        if isinstance(e, anthropic.RateLimitError):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "API_RATE_LIMIT",
                    "message": "⏳ Claude API 達到速率限制，請稍後再試（約 1-2 分鐘）",
                    "tip": "圖片分析需要較多 API 配額，建議等待片刻後重新上傳",
                    "technical": str(e)
                }
            )
        # 其他错误
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ANALYSIS_FAILED",
                "message": f"❌ 圖片分析失敗：{str(e)}",
                "tip": "請檢查圖片格式是否正確，或稍後再試"
            }
        )

@router.post("/create-persona")
async def create_persona(
    description: str = Form(...),
    persona_id: Optional[str] = Form(None),
    ig_user_id: Optional[str] = Form(None),
    reference_image: Optional[UploadFile] = File(None),
):
    """T3: 人設稜鏡 — 一句話描述生成完整人設 JSON
    
    persona_id: optional, 自定義 persona ID
    ig_user_id: optional, Instagram 用戶 ID（用於綁定）
    reference_image: optional, 參考人臉圖片（用於 InstantID）
    
    ⚠️ 此 API 會自動保存 persona 到存儲系統
    """
    # 處理參考圖片 — 上傳到 Cloudinary 取得永久公開 URL
    reference_face_url = None
    if reference_image:
        from app.services.cloudinary_service import upload_face_image
        content = await reference_image.read()
        content_type = reference_image.content_type or "image/jpeg"
        try:
            reference_face_url = await upload_face_image(content, content_type)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Cloudinary upload failed, skipping face reference: {e}")
            reference_face_url = None
    
    result = await genesis_service.create_persona(
        description=description,
        persona_id=persona_id,
        ig_user_id=ig_user_id or persona_id  # ig_user_id 可能與 persona_id 相同
    )
    
    # 自動保存到存儲系統（T0-3 新增）
    persona = result["persona"]
    await genesis_service.confirm_persona(persona, reference_face_url=reference_face_url)
    
    return result

@router.get("/persona/{persona_id}")
async def get_persona(persona_id: str):
    """讀取已存儲的人設"""
    from app.services.persona_storage import load_persona
    persona = load_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")
    return {"persona_id": persona_id, "persona": persona}


@router.post("/confirm-persona")
async def confirm_persona(persona: PersonaCard):
    """T4: 確認並鎖定人設"""
    return await genesis_service.confirm_persona(persona)
