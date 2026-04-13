from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging
from app.models.persona import PersonaCreate, PersonaCard, PersonaResponse
from app.services import genesis_service

router = APIRouter()
logger = logging.getLogger(__name__)

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
                }
            )
        # 其他错误
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ANALYSIS_FAILED",
                "message": "❌ 圖片分析失敗，請檢查圖片格式是否正確，或稍後再試",
            }
        )

@router.post("/create-persona")
async def create_persona(
    description: str = Form(...),
    persona_id: Optional[str] = Form(None),
    reference_image: Optional[UploadFile] = File(None),
    content_types: Optional[str] = Form(None),
):
    """T3: 人設稜鏡 — 一句話描述生成完整人設 JSON

    persona_id: optional, 自定義 persona ID
    reference_image: optional, 參考人臉圖片（用於 InstantID）
    content_types: optional, 預設內容類型（JSON array string，例如：["educational","entertainment"]）

    ⚠️ 此 API 會自動保存 persona 到存儲系統
    """
    # 解析 content_types（若提供）- 在 try 外處理以正確返回 400
    content_types_list = None
    if content_types:
        try:
            import json as json_module
            content_types_list = json_module.loads(content_types)
            # 驗證是否為 list
            if not isinstance(content_types_list, list):
                raise HTTPException(400, "content_types must be a JSON array")
        except json_module.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON format for content_types")
    
    try:
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
            content_types=content_types_list,
        )

        # 自動保存到存儲系統（T0-3 新增）
        persona = result["persona"]
        await genesis_service.confirm_persona(persona, reference_face_url=reference_face_url)

        return result
    except Exception as e:
        import anthropic
        logger.error(f"create_persona failed: {type(e).__name__}: {str(e)}")

        # Re-raise HTTPException (including validation errors)
        if isinstance(e, HTTPException):
            raise
        
        # 特殊處理 Claude API 錯誤
        if isinstance(e, anthropic.RateLimitError):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "API_RATE_LIMIT",
                    "message": "⏳ Claude API 達到速率限制，請稍後再試（約 1-2 分鐘）",
                }
            )
        elif isinstance(e, anthropic.AuthenticationError):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "API_AUTH_ERROR",
                    "message": "❌ Anthropic API 認證失敗，請聯絡管理員",
                }
            )
        elif isinstance(e, anthropic.APIError):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "API_ERROR",
                    "message": "❌ AI 服務暫時無法使用，請稍後再試",
                }
            )

        # 其他錯誤
        raise HTTPException(
            status_code=500,
            detail={
                "error": "PERSONA_CREATION_FAILED",
                "message": "❌ 人設生成失敗，請稍後再試",
            }
        )

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


class PersonaUpdateRequest(BaseModel):
    name: Optional[str] = None
    occupation: Optional[str] = None
    personality_tags: Optional[List[str]] = None
    speech_pattern: Optional[str] = None
    values: Optional[List[str]] = None
    weekly_lifestyle: Optional[str] = None
    content_types: Optional[List[str]] = None


@router.patch("/persona/{persona_id}")
async def update_persona(persona_id: str, req: PersonaUpdateRequest):
    """更新人設欄位（部分更新）"""
    from app.services.persona_storage import load_persona, save_persona
    persona = load_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    updated = persona.model_copy(update=req.model_dump(exclude_none=True))
    save_persona(persona_id, updated)
    return {"persona_id": persona_id, "persona": updated}


class ChatStyleUpdate(BaseModel):
    chat_style_prompt: Optional[str] = None
    chat_style_image: Optional[str] = None


@router.patch("/persona/{persona_id}/chat-style")
async def update_chat_style(persona_id: str, body: ChatStyleUpdate):
    """T4：更新 Persona 的聊天發文風格設定（prompt + 參考圖 URL）"""
    from app.services.persona_storage import load_persona, save_persona
    persona = load_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    updated = persona.model_copy(update=body.model_dump(exclude_none=True))
    save_persona(persona_id, updated)
    return {"persona_id": persona_id, "persona": updated}
