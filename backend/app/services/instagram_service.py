"""
Instagram Graph API Service (T9)
- OAuth flow (short-lived → long-lived token)
- Media upload & publish
- APScheduler-based scheduling (in-process, MVP)
- In-memory token store (dict; replace with DB in production)
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/instagram/callback")
FRONTEND_URL = os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000")

FB_OAUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
FB_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
FB_LONG_LIVED_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
GRAPH_URL = "https://graph.facebook.com/v19.0"

OAUTH_SCOPE = "instagram_basic,instagram_content_publish,pages_read_engagement"

# ---------------------------------------------------------------------------
# In-memory stores  (replace with DB for production)
# ---------------------------------------------------------------------------
# { persona_id: { "access_token": str, "ig_account_id": str, "ig_username": str, "expires_at": str } }
_token_store: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# APScheduler
# ---------------------------------------------------------------------------
_scheduler = BackgroundScheduler(
    jobstores={"default": MemoryJobStore()},
    timezone="UTC",
)


def get_scheduler() -> BackgroundScheduler:
    return _scheduler


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def get_auth_url(persona_id: str) -> str:
    """Return the Facebook OAuth dialog URL for a given persona."""
    if not INSTAGRAM_APP_ID:
        raise ValueError("INSTAGRAM_APP_ID is not configured")

    params = {
        "client_id": INSTAGRAM_APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "response_type": "code",
        "state": persona_id,  # use persona_id as state for CSRF + routing
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{FB_OAUTH_URL}?{query}"


def exchange_code_for_token(code: str, state: str) -> dict:
    """
    Exchange the OAuth code for a short-lived token, then upgrade to
    a long-lived token (~60 days).  Stores the token and returns info.
    """
    if not INSTAGRAM_APP_ID or not INSTAGRAM_APP_SECRET:
        raise ValueError("INSTAGRAM_APP_ID / INSTAGRAM_APP_SECRET not configured")

    # 1. Short-lived token
    resp = requests.get(FB_TOKEN_URL, params={
        "client_id": INSTAGRAM_APP_ID,
        "client_secret": INSTAGRAM_APP_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=10)
    resp.raise_for_status()
    short_data = resp.json()
    short_token = short_data.get("access_token")
    if not short_token:
        raise RuntimeError(f"Failed to get short-lived token: {short_data}")

    # 2. Long-lived token (60 days)
    resp2 = requests.get(FB_LONG_LIVED_URL, params={
        "grant_type": "fb_exchange_token",
        "client_id": INSTAGRAM_APP_ID,
        "client_secret": INSTAGRAM_APP_SECRET,
        "fb_exchange_token": short_token,
    }, timeout=10)
    resp2.raise_for_status()
    long_data = resp2.json()
    long_token = long_data.get("access_token")
    if not long_token:
        raise RuntimeError(f"Failed to get long-lived token: {long_data}")

    # 3. Fetch IG account info
    ig_account_id, ig_username = get_instagram_account_id(long_token)

    # 4. Store
    persona_id = state
    _token_store[persona_id] = {
        "access_token": long_token,
        "ig_account_id": ig_account_id,
        "ig_username": ig_username,
        "expires_in": long_data.get("expires_in", 5183944),
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Token stored for persona_id=%s ig_account_id=%s", persona_id, ig_account_id)
    return _token_store[persona_id]


def get_instagram_account_id(access_token: str) -> tuple[str, str]:
    """
    Return (ig_account_id, ig_username) for the authenticated user.
    Traverses /me/accounts → pages → instagram_business_account.
    """
    resp = requests.get(f"{GRAPH_URL}/me/accounts", params={
        "access_token": access_token,
        "fields": "id,name,instagram_business_account{id,username}",
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    pages = data.get("data", [])
    if not pages:
        raise RuntimeError("No Facebook Pages found for this account. Please ensure a Facebook Page exists.")

    for page in pages:
        ig_biz = page.get("instagram_business_account")
        if ig_biz:
            return ig_biz["id"], ig_biz.get("username", "")

    raise RuntimeError(
        "No Instagram Business Account found. "
        "Please connect an Instagram Professional account to your Facebook Page."
    )


# ---------------------------------------------------------------------------
# Connection status
# ---------------------------------------------------------------------------

def get_connection_status(persona_id: str) -> dict:
    """Return the stored token info for a persona, or indicate not connected."""
    info = _token_store.get(persona_id)
    if not info:
        return {"connected": False}
    return {
        "connected": True,
        "ig_account_id": info.get("ig_account_id"),
        "ig_username": info.get("ig_username"),
        "connected_at": info.get("connected_at"),
    }


def _require_token(persona_id: str) -> dict:
    info = _token_store.get(persona_id)
    if not info:
        raise RuntimeError(f"Instagram account not connected for persona_id={persona_id}")
    return info


# ---------------------------------------------------------------------------
# Media operations
# ---------------------------------------------------------------------------

def upload_photo(ig_account_id: str, image_url: str, caption: str, access_token: str) -> str:
    """
    Create an IG media container.  Returns creation_id.
    """
    resp = requests.post(f"{GRAPH_URL}/{ig_account_id}/media", params={
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    creation_id = data.get("id")
    if not creation_id:
        raise RuntimeError(f"upload_photo failed: {data}")
    return creation_id


def publish_media(ig_account_id: str, creation_id: str, access_token: str) -> str:
    """
    Publish the media container.  Returns the published media ID.
    """
    resp = requests.post(f"{GRAPH_URL}/{ig_account_id}/media_publish", params={
        "creation_id": creation_id,
        "access_token": access_token,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    media_id = data.get("id")
    if not media_id:
        raise RuntimeError(f"publish_media failed: {data}")
    return media_id


def _execute_publish(persona_id: str, image_url: str, caption: str) -> str:
    """Internal: look up token + upload + publish.  Called by scheduler or directly."""
    info = _require_token(persona_id)
    access_token = info["access_token"]
    ig_account_id = info["ig_account_id"]

    creation_id = upload_photo(ig_account_id, image_url, caption, access_token)
    media_id = publish_media(ig_account_id, creation_id, access_token)
    logger.info("Published media_id=%s for persona_id=%s", media_id, persona_id)
    return media_id


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def schedule_post(
    persona_id: str,
    ig_account_id: str,
    image_url: str,
    caption: str,
    publish_at: datetime,
    access_token: str,  # kept for API consistency; actual token fetched at run time
) -> str:
    """
    Schedule a post via APScheduler.  Returns the job_id.
    IG Graph API doesn't support native scheduling, so we use APScheduler.
    """
    job_id = str(uuid.uuid4())

    # Ensure publish_at is timezone-aware UTC
    if publish_at.tzinfo is None:
        publish_at = publish_at.replace(tzinfo=timezone.utc)

    _scheduler.add_job(
        _execute_publish,
        trigger="date",
        run_date=publish_at,
        args=[persona_id, image_url, caption],
        id=job_id,
        name=f"{persona_id}:{caption[:30]}",
        misfire_grace_time=300,  # 5-minute grace window
    )
    logger.info("Scheduled job_id=%s for persona_id=%s at %s", job_id, persona_id, publish_at)
    return job_id


def get_scheduled_posts(persona_id: str) -> list[dict]:
    """
    Return scheduled jobs for a persona.
    """
    jobs = _scheduler.get_jobs()
    result = []
    for job in jobs:
        if job.name.startswith(f"{persona_id}:"):
            result.append({
                "job_id": job.id,
                "name": job.name,
                "run_date": job.next_run_time.isoformat() if job.next_run_time else None,
                "persona_id": persona_id,
            })
    return result


def cancel_scheduled_post(job_id: str) -> bool:
    """Remove a scheduled job.  Returns True if removed, False if not found."""
    try:
        _scheduler.remove_job(job_id)
        return True
    except Exception:
        return False
