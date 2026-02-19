"""
Instagram API Router (T9)
Endpoints for OAuth, scheduling, and publishing.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.services import instagram_service as svc

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ScheduledPostItem(BaseModel):
    image_url: str
    caption: str
    publish_at: datetime  # ISO-8601, e.g. "2025-03-01T10:00:00Z"


class ScheduleRequest(BaseModel):
    persona_id: str
    ig_account_id: Optional[str] = None  # optional; looked up from token store if omitted
    posts: List[ScheduledPostItem]


class PublishNowRequest(BaseModel):
    persona_id: str
    image_url: str
    caption: str


# ---------------------------------------------------------------------------
# OAuth endpoints
# ---------------------------------------------------------------------------

@router.get("/auth")
async def get_auth_url(persona_id: str = Query(..., description="Virtual persona identifier")):
    """Return the Facebook OAuth URL to connect an Instagram Business account."""
    try:
        url = svc.get_auth_url(persona_id)
        return {"auth_url": url, "persona_id": persona_id}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(..., description="persona_id passed through OAuth state"),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """
    Facebook redirects here after the user grants permission.
    Exchanges the code for a long-lived token and redirects to the frontend.
    """
    if error:
        logger.warning("OAuth error: %s — %s", error, error_description)
        frontend_url = svc.FRONTEND_URL
        return RedirectResponse(url=f"{frontend_url}/publish?error={error}&persona_id={state}")

    try:
        info = svc.exchange_code_for_token(code, state)
        persona_id = state
        frontend_url = svc.FRONTEND_URL
        return RedirectResponse(
            url=f"{frontend_url}/publish?connected=true&persona_id={persona_id}&ig_username={info.get('ig_username', '')}"
        )
    except Exception as e:
        logger.exception("Token exchange failed")
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {e}")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_status(persona_id: str = Query(...)):
    """Check whether an Instagram account is connected for a persona."""
    return svc.get_connection_status(persona_id)


@router.delete("/token/{persona_id}")
async def disconnect(persona_id: str):
    """Clear stored token for a persona so the user can reconnect via OAuth."""
    removed = svc.disconnect_persona(persona_id)
    return {"disconnected": removed, "persona_id": persona_id}


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

@router.post("/schedule", status_code=201)
async def create_schedule(body: ScheduleRequest):
    """Schedule one or more posts for future publishing."""
    status = svc.get_connection_status(body.persona_id)
    if not status["connected"]:
        raise HTTPException(
            status_code=400,
            detail=f"Instagram account not connected for persona_id={body.persona_id}. "
                   "Call /api/instagram/auth first.",
        )

    ig_account_id = body.ig_account_id or status["ig_account_id"]
    access_token = svc._token_store[body.persona_id]["access_token"]

    job_ids = []
    for post in body.posts:
        publish_at = post.publish_at
        if publish_at.tzinfo is None:
            publish_at = publish_at.replace(tzinfo=timezone.utc)

        if publish_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail=f"publish_at must be in the future. Got: {post.publish_at.isoformat()}",
            )

        job_id = svc.schedule_post(
            persona_id=body.persona_id,
            ig_account_id=ig_account_id,
            image_url=post.image_url,
            caption=post.caption,
            publish_at=publish_at,
            access_token=access_token,
        )
        job_ids.append({"job_id": job_id, "publish_at": publish_at.isoformat()})

    return {"scheduled": job_ids, "count": len(job_ids)}


@router.get("/schedule")
async def list_schedule(persona_id: str = Query(...)):
    """List all pending scheduled posts for a persona."""
    posts = svc.get_scheduled_posts(persona_id)
    return {"persona_id": persona_id, "scheduled_posts": posts, "count": len(posts)}


@router.delete("/schedule/{job_id}")
async def cancel_schedule(job_id: str):
    """Cancel a scheduled post by job ID."""
    removed = svc.cancel_scheduled_post(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or already executed.")
    return {"cancelled": True, "job_id": job_id}


# ---------------------------------------------------------------------------
# Publish now
# ---------------------------------------------------------------------------

@router.post("/publish-now")
async def publish_now(body: PublishNowRequest):
    """Immediately upload and publish a photo to Instagram."""
    status = svc.get_connection_status(body.persona_id)
    if not status["connected"]:
        raise HTTPException(
            status_code=400,
            detail=f"Instagram account not connected for persona_id={body.persona_id}. "
                   "Call /api/instagram/auth first.",
        )

    try:
        media_id = svc._execute_publish(body.persona_id, body.image_url, body.caption)
        return {
            "success": True,
            "media_id": media_id,
            "persona_id": body.persona_id,
        }
    except Exception as e:
        logger.exception("publish-now failed for persona_id=%s", body.persona_id)
        raise HTTPException(status_code=500, detail=str(e))
