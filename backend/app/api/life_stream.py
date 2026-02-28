from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import anthropic
import logging
from app.services import life_stream_service

router = APIRouter()
logger = logging.getLogger(__name__)

class GenerateScheduleRequest(BaseModel):
    # persona 已移除：後端直接從 persona_storage 讀取，前端不需傳入
    appearance_prompt: Optional[str] = ""

class RegenerateRequest(BaseModel):
    scene_prompt: str           # 原始場景描述（Claude 生成的 scene_prompt）
    instruction: Optional[str] = ""
    persona_id: Optional[str] = None

@router.post("/generate-schedule/{persona_id}")
async def generate_schedule(persona_id: str, req: GenerateScheduleRequest):
    _verify_persona(persona_id)
    """T6: 根據人設自動規劃 3 天圖文內容（含生圖）
    
    人臉參考圖自動從存儲的 persona 讀取，無需前端傳入。
    """
    try:
        return await life_stream_service.generate_weekly_schedule(
            persona_id=persona_id,
            appearance_prompt=req.appearance_prompt or "",
        )
    except ValueError as e:
        # Persona 不存在或 JSON 格式錯誤
        logger.error(f"ValueError in generate_schedule: {e}")
        raise HTTPException(status_code=400, detail=f"❌ 人設資料錯誤：{str(e)}")
    except anthropic.RateLimitError as e:
        # Claude API rate limit
        logger.error(f"Claude RateLimitError: {e}")
        raise HTTPException(
            status_code=429, 
            detail="⏳ Claude API 達到使用上限（每分鐘 50,000 tokens）。請等待 1-2 分鐘後重試。"
        )
    except anthropic.APIError as e:
        # 其他 Claude API 錯誤
        logger.error(f"Claude APIError: {e}")
        raise HTTPException(status_code=500, detail=f"❌ Claude API 錯誤：{str(e)}")
    except RuntimeError as e:
        # Replicate API 錯誤或其他運行時錯誤
        error_msg = str(e)
        if "Rate limited" in error_msg or "429" in error_msg:
            logger.error(f"Replicate rate limit: {e}")
            raise HTTPException(
                status_code=429,
                detail="⏳ Replicate API 達到使用上限。請等待 1-2 分鐘後重試。"
            )
        else:
            logger.error(f"RuntimeError in generate_schedule: {e}")
            raise HTTPException(status_code=500, detail=f"❌ 生圖失敗：{error_msg}")
    except Exception as e:
        # 未預期的錯誤
        logger.exception(f"Unexpected error in generate_schedule: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"❌ 系統錯誤：{str(e)}。請檢查後端日誌或聯繫開發者。"
        )

def _verify_persona(persona_id: str):
    """確認 persona_id 在 token store 中存在，否則 403。'default' 跳過驗證（開發用）。"""
    if persona_id == "default":
        return
    from app.services.instagram_service import get_connection_status
    status = get_connection_status(persona_id)
    if not status.get("connected"):
        raise HTTPException(status_code=403, detail=f"Unauthorized persona_id: {persona_id}")


@router.get("/schedule/{persona_id}")
async def get_schedule(persona_id: str):
    """T5: 讀取排程（後端為 source of truth）"""
    _verify_persona(persona_id)
    from app.services.schedule_storage import load_schedule
    posts = load_schedule(persona_id)
    return {"persona_id": persona_id, "posts": posts}


class UpdatePostStatusRequest(BaseModel):
    status: str  # draft / approved / rejected


class UpdatePostContentRequest(BaseModel):
    caption: str
    scene_prompt: str


@router.patch("/schedule/{persona_id}/{day}/status")
async def update_post_status(persona_id: str, day: int, req: UpdatePostStatusRequest):
    """更新單篇貼文狀態"""
    from app.services.schedule_storage import update_post_status
    ok = update_post_status(persona_id, day, req.status)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Post day={day} not found for persona {persona_id}")
    return {"ok": True, "day": day, "status": req.status}


@router.patch("/schedule/{persona_id}/{day}/content")
async def update_post_content(persona_id: str, day: int, req: UpdatePostContentRequest):
    """更新單篇貼文的文案與重繪方向（scene_prompt）"""
    _verify_persona(persona_id)
    from app.services.schedule_storage import update_post_content
    ok = update_post_content(persona_id, day, req.caption, req.scene_prompt)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Post day={day} not found for persona {persona_id}")
    return {"ok": True, "day": day}


@router.post("/regenerate/{content_id}")
async def regenerate(content_id: str, req: RegenerateRequest):
    """一鍵重繪：用正確的 scene_prompt + face_image_url 重新生圖"""
    return await life_stream_service.regenerate_content(
        content_id=content_id,
        scene_prompt=req.scene_prompt,
        instruction=req.instruction or "",
        persona_id=req.persona_id or ""
    )
