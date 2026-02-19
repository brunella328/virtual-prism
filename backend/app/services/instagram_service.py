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
IG_GRAPH_URL = "https://graph.instagram.com/v19.0"  # for IGAA tokens (Basic Display / Creator)

OAUTH_SCOPE = "instagram_basic,instagram_content_publish,pages_read_engagement,pages_show_list"

# ---------------------------------------------------------------------------
# In-memory stores  (replace with DB for production)
# ---------------------------------------------------------------------------
# { persona_id: { "access_token": str, "ig_account_id": str, "ig_username": str, "expires_at": str } }
_token_store: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Pre-seed token store from environment (MVP shortcut - bypass OAuth)
# ---------------------------------------------------------------------------
_ENV_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
_ENV_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")
_ENV_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")

def _init_env_token() -> None:
    """If INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_USER_ID are set in env,
    pre-seed the token store as persona_id='default' so the app works
    immediately without going through the OAuth flow."""
    if _ENV_ACCESS_TOKEN and _ENV_USER_ID:
        _token_store["default"] = {
            "access_token": _ENV_ACCESS_TOKEN,
            "ig_account_id": _ENV_USER_ID,
            "ig_username": _ENV_USERNAME or "ig_user",
            "expires_at": "2099-12-31T00:00:00+00:00",  # long-lived token
        }
        logger.info("Instagram token pre-seeded from environment (persona_id='default')")

_init_env_token()

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
    Strategy 1: /me/accounts → pages → instagram_business_account (Business)
    Strategy 2: /me?fields=instagram_business_account (Creator / direct link)
    """
    # --- Strategy 1: via Facebook Pages ---
    try:
        resp = requests.get(f"{GRAPH_URL}/me/accounts", params={
            "access_token": access_token,
            "fields": "id,name,instagram_business_account{id,username}",
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("data", [])
        logger.info("FB Pages found: %d — %s", len(pages), [p.get("name") for p in pages])

        for page in pages:
            ig_biz = page.get("instagram_business_account")
            if ig_biz:
                logger.info("Found IG Business Account via Page: %s", ig_biz)
                return ig_biz["id"], ig_biz.get("username", "")
    except Exception as e:
        logger.warning("Strategy 1 (via Pages) failed: %s", e)

    # --- Strategy 2: /me → instagram_business_account (Creator accounts) ---
    try:
        resp2 = requests.get(f"{GRAPH_URL}/me", params={
            "access_token": access_token,
            "fields": "id,name,instagram_business_account{id,username}",
        }, timeout=10)
        resp2.raise_for_status()
        me = resp2.json()
        logger.info("/me response: %s", me)
        ig_biz = me.get("instagram_business_account")
        if ig_biz:
            return ig_biz["id"], ig_biz.get("username", "")
    except Exception as e:
        logger.warning("Strategy 2 (/me direct) failed: %s", e)

    # --- Strategy 3: use INSTAGRAM_USER_ID from env as fallback ---
    env_user_id = os.getenv("INSTAGRAM_USER_ID", "")
    if env_user_id:
        logger.warning("Falling back to INSTAGRAM_USER_ID from env: %s", env_user_id)
        # Try to get username via IG user ID using the new OAuth token
        try:
            resp3 = requests.get(f"{GRAPH_URL}/{env_user_id}", params={
                "access_token": access_token,
                "fields": "id,username,name",
            }, timeout=10)
            resp3.raise_for_status()
            ig_data = resp3.json()
            logger.info("Strategy 3 result: %s", ig_data)
            return ig_data["id"], ig_data.get("username") or ig_data.get("name") or "ig_user"
        except Exception as e:
            logger.warning("Strategy 3 (env user_id lookup) failed: %s", e)
        # Last resort: env ID with env username (Creator account typical path)
        return env_user_id, _ENV_USERNAME or "unknown"

    raise RuntimeError(
        "找不到 Instagram 帳號。請確認：\n"
        "1. IG 帳號已切換為「專業帳號」（創作者或商業帳號）\n"
        "2. IG 帳號已在 Facebook 粉絲專頁設定中連結\n"
        "3. Meta App 已設定為「上線」模式（非開發模式）\n"
        "4. OAuth 授權時有選取正確的粉絲專頁"
    )


# ---------------------------------------------------------------------------
# Connection status
# ---------------------------------------------------------------------------

def disconnect_persona(persona_id: str) -> bool:
    """Remove token for a persona so OAuth can be re-run."""
    if persona_id in _token_store:
        del _token_store[persona_id]
        logger.info("Disconnected persona_id=%s", persona_id)
        return True
    return False


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

def _ensure_jpeg_url(image_url: str) -> str:
    """
    Instagram Graph API 只接受 JPEG/PNG。
    若圖片是 WebP，下載後轉換成 JPEG 並回傳 data URI（僅作 debug）。
    實際上需上傳到公開 CDN；這裡先嘗試通過 requests 取 content-type 判斷。
    """
    import io
    try:
        head = requests.head(image_url, timeout=10, allow_redirects=True)
        content_type = head.headers.get("Content-Type", "")
        if "webp" in content_type or image_url.lower().endswith(".webp"):
            logger.warning("WebP detected (%s), attempting JPEG conversion", image_url)
            img_resp = requests.get(image_url, timeout=30)
            img_resp.raise_for_status()
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=92)
                buf.seek(0)
                # TODO: upload buf to CDN and return CDN URL
                # For now, raise with a clear message
                raise RuntimeError(
                    f"圖片為 WebP 格式，Instagram 不支援。"
                    f"請將 Replicate 輸出格式改為 JPEG/PNG，或上傳至公開 CDN 後再發布。"
                    f"原始 URL: {image_url}"
                )
            except ImportError:
                raise RuntimeError(
                    f"圖片為 WebP 格式（Instagram 不支援），且無法轉換（缺少 Pillow）。"
                    f"請將 Replicate 輸出改為 JPEG 格式。URL: {image_url}"
                )
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning("Content-type check failed: %s", e)
    return image_url


def _api_base(access_token: str) -> str:
    """Return correct Graph API base URL depending on token type.
    IGAA tokens → graph.instagram.com (Instagram Basic Display / Creator)
    EAA tokens  → graph.facebook.com  (Facebook Graph API / Business)
    """
    if access_token.startswith("IGAA"):
        return IG_GRAPH_URL
    return GRAPH_URL


def upload_photo(ig_account_id: str, image_url: str, caption: str, access_token: str) -> str:
    """
    Create an IG media container.  Returns creation_id.
    """
    # Validate / convert image format before sending to IG
    image_url = _ensure_jpeg_url(image_url)

    base = _api_base(access_token)
    resp = requests.post(f"{base}/{ig_account_id}/media", params={
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }, timeout=30)

    if not resp.ok:
        try:
            err_body = resp.json()
            logger.error("Meta API error: %s", err_body)
            meta_msg = err_body.get("error", {}).get("message", resp.text)
            raise RuntimeError(f"Meta API 400: {meta_msg}")
        except (ValueError, KeyError):
            logger.error("Meta API raw error: %s", resp.text)
        resp.raise_for_status()

    data = resp.json()
    creation_id = data.get("id")
    if not creation_id:
        raise RuntimeError(f"upload_photo failed: {data}")
    return creation_id


def wait_for_container(creation_id: str, access_token: str, max_wait: int = 30) -> None:
    """
    Poll container status until FINISHED (Instagram needs time to process images).
    Raises if ERROR or timeout.
    """
    import time
    base = _api_base(access_token)
    for attempt in range(max_wait // 3):
        resp = requests.get(f"{base}/{creation_id}", params={
            "fields": "status_code",
            "access_token": access_token,
        }, timeout=10)
        resp.raise_for_status()
        status_code = resp.json().get("status_code", "")
        logger.info("Container %s status: %s (attempt %d)", creation_id, status_code, attempt + 1)
        if status_code == "FINISHED":
            return
        if status_code == "ERROR":
            raise RuntimeError(f"Media container {creation_id} processing failed (ERROR)")
        time.sleep(3)
    raise RuntimeError(f"Media container {creation_id} not ready after {max_wait}s")


def publish_media(ig_account_id: str, creation_id: str, access_token: str) -> str:
    """
    Wait for container to be ready, then publish.  Returns the published media ID.
    """
    wait_for_container(creation_id, access_token)
    base = _api_base(access_token)
    resp = requests.post(f"{base}/{ig_account_id}/media_publish", params={
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

    # Primary attempt with stored token
    primary_err_msg = None
    try:
        creation_id = upload_photo(ig_account_id, image_url, caption, access_token)
        media_id = publish_media(ig_account_id, creation_id, access_token)
        logger.info("Published media_id=%s for persona_id=%s", media_id, persona_id)
        return media_id
    except Exception as e:
        primary_err_msg = str(e)
        logger.warning("Primary token failed (%s), trying env fallback token", e)

    # Fallback: use env INSTAGRAM_ACCESS_TOKEN if available and different from current
    env_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    env_user_id = os.getenv("INSTAGRAM_USER_ID", "")
    if env_token and env_token != access_token and env_user_id:
        logger.info("Retrying publish with env access token (ig_account_id=%s)", env_user_id)
        creation_id = upload_photo(env_user_id, image_url, caption, env_token)
        media_id = publish_media(env_user_id, creation_id, env_token)
        logger.info("Published via env token: media_id=%s for persona_id=%s", media_id, persona_id)
        # Update stored token to working env token for next time
        _token_store[persona_id]["access_token"] = env_token
        _token_store[persona_id]["ig_account_id"] = env_user_id
        return media_id

    raise RuntimeError(f"發布失敗，env token 也無法使用或未設定。原始錯誤：{primary_err_msg}")


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
