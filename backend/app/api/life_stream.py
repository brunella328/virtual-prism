from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from typing import Optional
import anthropic
import logging
from app.services import life_stream_service, users_storage
from app.api.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

POST_QUOTA = 3  # 每帳號生成圖文總上限

class GenerateScheduleRequest(BaseModel):
    # persona 已移除：後端直接從 persona_storage 讀取，前端不需傳入
    appearance_prompt: Optional[str] = ""

class GeneratePostRequest(BaseModel):
    date: str  # ISO format: "2026-03-15"
    appearance_prompt: Optional[str] = ""

class RegenerateRequest(BaseModel):
    scene_prompt: str           # 原始場景描述（Claude 生成的 scene_prompt）
    instruction: Optional[str] = ""
    persona_id: Optional[str] = None

@router.post("/generate-schedule/{persona_id}")
async def generate_schedule(
    persona_id: str,
    req: GenerateScheduleRequest,
    current_user: dict = Depends(get_current_user),
):
    _verify_persona(persona_id)
    """T6: 根據人設自動規劃 3 天圖文內容（含生圖）"""
    generated = current_user.get("posts_generated", 0)
    if generated >= POST_QUOTA:
        raise HTTPException(
            status_code=403,
            detail=f"已達生成上限（{POST_QUOTA} 篇）。感謝使用 Virtual Prism！",
        )
    try:
        result = await life_stream_service.generate_weekly_schedule(
            persona_id=persona_id,
            appearance_prompt=req.appearance_prompt or "",
        )
        # 計算本次實際生成篇數並更新配額
        post_count = len(result.get("posts", [])) if isinstance(result, dict) else 1
        users_storage.increment_posts_generated(current_user["uuid"], post_count)
        return result
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
    """確認 persona_id 合法（非空字串即可）。
    新流程：persona_id 為 UUID，不需要 IG token 才能使用排程功能。
    IG token 只有在發布到 IG 時才需要（由 instagram.py 的 publish endpoint 檢查）。
    """
    if not persona_id or persona_id.strip() == "":
        raise HTTPException(status_code=400, detail="persona_id is required")


@router.post("/generate-post/{persona_id}")
async def generate_post(
    persona_id: str,
    date: str = Form(...),
    appearance_prompt: str = Form(""),
    user_hint: str = Form(""),
    reference_image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    """月曆模式：為指定日期生成單篇貼文（append，不覆蓋現有排程）"""
    _verify_persona(persona_id)
    generated = current_user.get("posts_generated", 0)
    if generated >= POST_QUOTA:
        raise HTTPException(
            status_code=403,
            detail=f"已達生成上限（{POST_QUOTA} 篇）。感謝使用 Virtual Prism！",
        )
    from datetime import date as date_type
    # 驗證日期格式
    try:
        date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"日期格式錯誤，請使用 YYYY-MM-DD：{date}")
    # 驗證每日上限（3 篇）
    from app.services.schedule_storage import load_schedule
    existing = load_schedule(persona_id)
    day_count = sum(1 for p in existing if p.get("date") == date)
    if day_count >= 3:
        raise HTTPException(status_code=422, detail=f"{date} 已達每日上限（3 篇）")
    ref_url = ""
    if reference_image:
        from app.services.cloudinary_service import upload_file_bytes
        data = await reference_image.read()
        ref_url = await upload_file_bytes(data, folder="virtual_prism/refs")
    try:
        post = await life_stream_service.generate_single_post(
            persona_id=persona_id,
            date=date,
            appearance_prompt=appearance_prompt or "",
            user_hint=user_hint or "",
            reference_image_url=ref_url,
        )
        users_storage.increment_posts_generated(current_user["uuid"], 1)
        return post
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_post error: {e}")
        raise HTTPException(status_code=500, detail=f"生成失敗：{str(e)}")


@router.get("/schedule/{persona_id}")
async def get_schedule(persona_id: str):
    """讀取排程（schedule_storage 為 source of truth）
    status / scheduled_at / job_id 均持久化在 JSON，不需 runtime cross-reference。
    """
    _verify_persona(persona_id)
    from app.services.schedule_storage import load_schedule
    posts = load_schedule(persona_id)
    return {"persona_id": persona_id, "posts": posts}


class UpdatePostStatusRequest(BaseModel):
    status: str  # draft / approved / rejected


class UpdatePostContentRequest(BaseModel):
    caption: str
    scene_prompt: str


class UpdatePostImageRequest(BaseModel):
    image_url: str
    image_prompt: str


class UpdatePostScheduledAtRequest(BaseModel):
    scheduled_at: str  # ISO 8601


@router.patch("/schedule/{persona_id}/{post_id}/status")
async def update_post_status(persona_id: str, post_id: str, req: UpdatePostStatusRequest):
    """更新單篇貼文狀態"""
    from app.services.schedule_storage import update_post_status
    ok = update_post_status(persona_id, post_id, req.status)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Post post_id={post_id} not found for persona {persona_id}")
    return {"ok": True, "post_id": post_id, "status": req.status}


@router.patch("/schedule/{persona_id}/{post_id}/content")
async def update_post_content(persona_id: str, post_id: str, req: UpdatePostContentRequest):
    """更新單篇貼文的文案與重繪方向（scene_prompt）"""
    _verify_persona(persona_id)
    from app.services.schedule_storage import update_post_content
    ok = update_post_content(persona_id, post_id, req.caption, req.scene_prompt)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Post post_id={post_id} not found for persona {persona_id}")
    return {"ok": True, "post_id": post_id}


@router.patch("/schedule/{persona_id}/{post_id}/scheduled-at")
async def update_post_scheduled_at(persona_id: str, post_id: str, req: UpdatePostScheduledAtRequest):
    """手動覆寫排程時間（一般由 schedule_post 自動處理）"""
    from app.services.schedule_storage import update_post_scheduled_at
    ok = update_post_scheduled_at(persona_id, post_id, req.scheduled_at)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Post post_id={post_id} not found for persona {persona_id}")
    return {"ok": True, "post_id": post_id, "scheduled_at": req.scheduled_at}


@router.patch("/schedule/{persona_id}/{post_id}/image")
async def update_post_image(persona_id: str, post_id: str, req: UpdatePostImageRequest):
    """套用重繪結果：持久化新的 image_url 與 image_prompt"""
    _verify_persona(persona_id)
    from app.services.schedule_storage import update_post_image
    ok = update_post_image(persona_id, post_id, req.image_url, req.image_prompt)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Post post_id={post_id} not found for persona {persona_id}")
    return {"ok": True, "post_id": post_id}


@router.post("/regenerate/{content_id}")
async def regenerate(
    content_id: str,
    scene_prompt: str = Form(...),
    instruction: str = Form(""),
    persona_id: str = Form(""),
    reference_image: Optional[UploadFile] = File(None),
):
    """一鍵重繪：用正確的 scene_prompt + face_image_url 重新生圖"""
    ref_url = ""
    if reference_image:
        from app.services.cloudinary_service import upload_file_bytes
        data = await reference_image.read()
        ref_url = await upload_file_bytes(data, folder="virtual_prism/refs")
    return await life_stream_service.regenerate_content(
        content_id=content_id,
        scene_prompt=scene_prompt,
        instruction=instruction,
        persona_id=persona_id,
        reference_image_url=ref_url,
    )
