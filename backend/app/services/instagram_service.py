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
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/instagram/callback")
FRONTEND_URL = os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

FB_OAUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
FB_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
FB_LONG_LIVED_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
GRAPH_URL = "https://graph.facebook.com/v19.0"
IG_GRAPH_URL = "https://graph.instagram.com/v19.0"  # for IGAA tokens (Basic Display / Creator)

# Instagram API with Instagram Login (replaces Facebook Login for Creator accounts)
IG_OAUTH_URL = "https://www.instagram.com/oauth/authorize"
IG_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
IG_LONG_LIVED_URL = "https://graph.instagram.com/access_token"
IG_ME_URL = "https://graph.instagram.com/me"

OAUTH_SCOPE = "instagram_business_basic,instagram_business_content_publish"

# ---------------------------------------------------------------------------
# Token store — in-memory + JSON 持久化
# ---------------------------------------------------------------------------
import json
from pathlib import Path

_TOKEN_FILE = Path(__file__).parent.parent.parent / "data" / "instagram_tokens.json"
_SCHEDULER_DB = Path(__file__).parent.parent.parent / "data" / "scheduler.db"

def _load_token_store() -> dict:
    """從 JSON 檔案讀取 token store（backend 重啟後恢復）"""
    if _TOKEN_FILE.exists():
        try:
            return json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load token store: {e}")
    return {}

def _save_token_store() -> None:
    """把 token store 寫回 JSON 檔案"""
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps(_token_store, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to save token store: {e}")

# { persona_id: { "access_token": str, "ig_account_id": str, "ig_username": str, "expires_at": str } }
_token_store: dict[str, dict] = _load_token_store()

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
    if _ENV_ACCESS_TOKEN and _ENV_USER_ID and "default" not in _token_store:
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
_SCHEDULER_DB.parent.mkdir(parents=True, exist_ok=True)
_scheduler = BackgroundScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{_SCHEDULER_DB}")},
    timezone="UTC",
)


def get_scheduler() -> BackgroundScheduler:
    return _scheduler


def start_scheduler() -> None:
    """Start APScheduler and register token refresh jobs.
    Called from application lifespan/startup."""
    if not _scheduler.running:
        _scheduler.start()
        logger.info("APScheduler started")
    _schedule_token_refresh_jobs()


# ---------------------------------------------------------------------------
# Telegram notifications
# ---------------------------------------------------------------------------

def _send_telegram(message: str) -> None:
    """Send a message via Telegram Bot API.  Fire-and-forget; logs errors."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured (missing BOT_TOKEN or CHAT_ID), skipping notification")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not resp.ok:
            logger.warning("Telegram send failed: %s", resp.text)
    except Exception as e:
        logger.warning("Telegram send exception: %s", e)


# ---------------------------------------------------------------------------
# Token auto-refresh (C1 + C2)
# ---------------------------------------------------------------------------

def refresh_instagram_token(persona_id: str = "default") -> None:
    """
    Refresh the IGAA long-lived token for a persona.
    Called by APScheduler every 50 days.
    On success: updates _token_store and .env (for restart persistence).
    On failure: sends Telegram notification.
    """
    info = _token_store.get(persona_id)
    if not info:
        logger.warning("refresh_instagram_token: no token found for persona_id=%s, skipping", persona_id)
        return

    access_token = info.get("access_token", "")
    if not access_token:
        _send_telegram(
            f"⚠️ *Virtual Prism - Token 刷新失敗*\n\n"
            f"persona_id: `{persona_id}`\n"
            f"原因: token store 中無 access_token\n"
            f"請手動重新授權"
        )
        return

    logger.info("Refreshing IGAA token for persona_id=%s ...", persona_id)
    try:
        resp = requests.get(
            "https://graph.instagram.com/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": access_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        new_token = data.get("access_token")
        expires_in = data.get("expires_in", 5183944)  # ~60 days default

        if not new_token:
            raise RuntimeError(f"Refresh response missing access_token: {data}")

        # Update in-memory store
        _token_store[persona_id]["access_token"] = new_token
        _token_store[persona_id]["refreshed_at"] = datetime.now(timezone.utc).isoformat()
        _token_store[persona_id]["expires_in"] = expires_in

        _save_token_store()   # JSON 持久化（重啟後恢復）

        logger.info("Token refreshed successfully for persona_id=%s", persona_id)
        _send_telegram(
            f"✅ *Virtual Prism - Token 自動刷新成功*\n\n"
            f"persona_id: `{persona_id}`\n"
            f"有效期: 約 {expires_in // 86400} 天\n"
            f"下次刷新: 50 天後"
        )

    except Exception as e:
        logger.error("Token refresh failed for persona_id=%s: %s", persona_id, e)
        _send_telegram(
            f"🚨 *Virtual Prism - Token 刷新失敗！*\n\n"
            f"persona_id: `{persona_id}`\n"
            f"錯誤: `{str(e)[:200]}`\n\n"
            f"請盡快手動刷新 token，或重新走 OAuth 流程！"
        )


def _schedule_token_refresh_jobs() -> None:
    """Register token refresh jobs for all personas currently in token store.
    Called once at startup after token store is pre-seeded."""
    for persona_id in list(_token_store.keys()):
        job_id = f"ig_token_refresh_{persona_id}"
        if not _scheduler.get_job(job_id):
            _scheduler.add_job(
                refresh_instagram_token,
                trigger="interval",
                days=50,
                args=[persona_id],
                id=job_id,
                name=f"IG token refresh ({persona_id})",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            logger.info("Scheduled token refresh job for persona_id=%s (every 50 days)", persona_id)


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def get_auth_url(persona_id: str) -> str:
    """Return the Instagram OAuth dialog URL for a given persona.
    Uses Instagram API with Instagram Login (supports Creator + Business accounts).
    """
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
    return f"{IG_OAUTH_URL}?{query}"


def exchange_code_for_token(code: str, state: str) -> dict:
    """
    Exchange the OAuth code for a short-lived token via Instagram API with Instagram Login,
    then upgrade to a long-lived token (~60 days).  Stores the token and returns info.

    Flow (Instagram API with Instagram Login):
    1. POST api.instagram.com/oauth/access_token  → short-lived IGAA token
    2. GET graph.instagram.com/access_token       → long-lived IGAA token (ig_exchange_token)
    3. GET graph.instagram.com/me                 → ig_user_id + username
    """
    if not INSTAGRAM_APP_ID or not INSTAGRAM_APP_SECRET:
        raise ValueError("INSTAGRAM_APP_ID / INSTAGRAM_APP_SECRET not configured")

    # 1. Short-lived token (Instagram token endpoint)
    resp = requests.post(IG_TOKEN_URL, data={
        "client_id": INSTAGRAM_APP_ID,
        "client_secret": INSTAGRAM_APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=10)
    if not resp.ok:
        logger.error("IG token exchange failed: status=%s body=%s", resp.status_code, resp.text)
        raise RuntimeError(f"IG token exchange {resp.status_code}: {resp.text}")
    short_data = resp.json()
    short_token = short_data.get("access_token")
    if not short_token:
        raise RuntimeError(f"Failed to get short-lived IG token: {short_data}")
    logger.info("Short-lived IGAA token obtained for state=%s", state)

    # 2. Long-lived token (~60 days) via graph.instagram.com
    resp2 = requests.get(IG_LONG_LIVED_URL, params={
        "grant_type": "ig_exchange_token",
        "client_secret": INSTAGRAM_APP_SECRET,
        "access_token": short_token,
    }, timeout=10)
    resp2.raise_for_status()
    long_data = resp2.json()
    long_token = long_data.get("access_token")
    if not long_token:
        raise RuntimeError(f"Failed to get long-lived IGAA token: {long_data}")
    logger.info("Long-lived IGAA token obtained")

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

    # 5. Register token refresh job for this persona
    _schedule_token_refresh_jobs()

    logger.info("Token stored for persona_id=%s ig_account_id=%s username=%s",
                persona_id, ig_account_id, ig_username)
    return _token_store[persona_id]


def get_instagram_account_id(access_token: str) -> tuple[str, str]:
    """
    Return (ig_account_id, ig_username) for the authenticated user.

    For IGAA tokens (Instagram API with Instagram Login):
      → graph.instagram.com/me?fields=user_id,username

    For EAA tokens (Facebook Graph API, Business accounts):
      → Strategy 1: /me/accounts → pages → instagram_business_account
      → Strategy 2: /me?fields=instagram_business_account (Creator / direct link)
    """
    # --- IGAA token path (Instagram API with Instagram Login) ---
    if access_token.startswith("IGAA"):
        try:
            resp = requests.get(f"{IG_ME_URL}", params={
                "fields": "user_id,username",
                "access_token": access_token,
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info("graph.instagram.com/me response: %s", data)
            user_id = data.get("user_id") or data.get("id")
            username = data.get("username", "")
            if user_id:
                return str(user_id), username
        except Exception as e:
            logger.warning("IGAA /me lookup failed: %s", e)

    # --- EAA token path (Facebook Graph API, Business accounts) ---
    # Strategy 1: via Facebook Pages
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

    # Strategy 2: /me → instagram_business_account (Creator accounts)
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

    # --- Fallback: use INSTAGRAM_USER_ID from env ---
    env_user_id = os.getenv("INSTAGRAM_USER_ID", "")
    if env_user_id:
        logger.warning("Falling back to INSTAGRAM_USER_ID from env: %s", env_user_id)
        return env_user_id, _ENV_USERNAME or "unknown"

    raise RuntimeError(
        "找不到 Instagram 帳號。請確認：\n"
        "1. IG 帳號已切換為「專業帳號」（創作者或商業帳號）\n"
        "2. OAuth 使用 Instagram API with Instagram Login（非 Facebook Login）\n"
        "3. Meta App 開發模式下，用測試帳號授權"
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


def connect_with_access_token(
    persona_id: str,
    access_token: str,
    ig_user_id: Optional[str] = None,
    ig_username: Optional[str] = None,
) -> dict:
    """
    Directly connect an IG account using a long-lived access token (bypass OAuth).
    Validates the token by fetching user info from /me if not provided.
    Uses ig_user_id as the actual persona_id for storage.
    Stores the token and returns connection info.
    """
    # If ig_user_id not provided, fetch from API
    if not ig_user_id or not ig_username:
        fetched_id, fetched_username = get_instagram_account_id(access_token)
        ig_user_id = ig_user_id or fetched_id
        ig_username = ig_username or fetched_username
    
    # Use ig_user_id as the actual persona_id (one IG account = one persona)
    actual_persona_id = ig_user_id
    
    # Store token with ig_user_id as key
    _token_store[actual_persona_id] = {
        "access_token": access_token,
        "ig_account_id": ig_user_id,
        "ig_username": ig_username,
        "expires_in": 5183944,  # ~60 days default for long-lived tokens
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Register token refresh job
    _schedule_token_refresh_jobs()

    # 持久化到 JSON（重啟後恢復）
    _save_token_store()

    logger.info("Token manually connected for persona_id=%s ig_account_id=%s username=%s",
                actual_persona_id, ig_user_id, ig_username)
    return _token_store[actual_persona_id]


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
    若圖片是 WebP，下載後轉換成 JPEG 並上傳至 tmpfiles.org（免費公開 CDN）。
    """
    import io
    import base64
    try:
        head = requests.head(image_url, timeout=10, allow_redirects=True)
        content_type = head.headers.get("Content-Type", "")
        if "webp" in content_type or image_url.lower().endswith(".webp"):
            logger.warning("WebP detected (%s), converting to JPEG...", image_url)
            img_resp = requests.get(image_url, timeout=30)
            img_resp.raise_for_status()
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=92)
                buf.seek(0)
                
                # 上傳至 tmpfiles.org（免費 24 小時暫存）
                try:
                    upload_resp = requests.post(
                        "https://tmpfiles.org/api/v1/upload",
                        files={"file": ("image.jpg", buf, "image/jpeg")},
                        timeout=30
                    )
                    upload_resp.raise_for_status()
                    upload_data = upload_resp.json()
                    if upload_data.get("status") == "success":
                        # tmpfiles.org 返回格式：https://tmpfiles.org/12345
                        # 需改為 dl 連結：https://tmpfiles.org/dl/12345
                        tmp_url = upload_data["data"]["url"]
                        cdn_url = tmp_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                        logger.info("Converted WebP to JPEG and uploaded to CDN: %s", cdn_url)
                        return cdn_url
                except Exception as upload_err:
                    logger.error("Failed to upload to tmpfiles.org: %s", upload_err)
                    # Fallback: 返回 base64 data URL（可能太大但至少能用）
                    buf.seek(0)
                    b64 = base64.b64encode(buf.read()).decode('utf-8')
                    data_url = f"data:image/jpeg;base64,{b64}"
                    logger.warning("Using base64 data URL as fallback (size: %d chars)", len(data_url))
                    return data_url
                    
            except ImportError:
                raise RuntimeError(
                    f"圖片為 WebP 格式（Instagram 不支援），且無法轉換（缺少 Pillow）。"
                    f"請安裝 Pillow: pip install Pillow"
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
