"""
Interaction Hub API (T10) — Auto-Reply System
Endpoints:
  GET/POST /webhook/instagram   — IG Webhook verification & event handling
  GET      /replies/pending/{persona_id}
  POST     /replies/{reply_id}/send
  POST     /replies/{reply_id}/dismiss
  GET      /settings/{persona_id}
  POST     /settings/{persona_id}
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.services import interact_service
from app.services.instagram_service import _token_store as ig_token_store

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Webhook — GET (hub verification) & POST (events)
# ---------------------------------------------------------------------------

WEBHOOK_VERIFY_TOKEN = "virtual_prism_webhook_token"


@router.get("/webhook/instagram")
async def instagram_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Handle IG Webhook hub verification (GET).
    Returns hub.challenge value when verify token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge or "")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/webhook/instagram")
async def instagram_webhook(request: Request):
    """
    Receive IG Webhook events (POST).
    Parses entry[].changes[] for comment events, generates drafts.
    """
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    entries = payload.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field", "")
            if field != "comments":
                continue

            value = change.get("value", {})
            ig_comment_id = value.get("id", "")
            ig_media_id = value.get("media", {}).get("id", "") if isinstance(value.get("media"), dict) else value.get("media_id", "")
            commenter_name = value.get("from", {}).get("name", "匿名用戶")
            comment_text = value.get("text", "")

            # Derive persona_id from media owner (best-effort: scan token store)
            ig_account_id_from_webhook = value.get("from", {}).get("id", "")
            persona_id = _resolve_persona_id(ig_account_id_from_webhook)

            if not comment_text:
                logger.warning("Received comment event with empty text, skipping")
                continue

            try:
                draft_text = interact_service.generate_reply_draft(
                    persona_id, comment_text, commenter_name
                )
                risk_level = interact_service.check_risk(comment_text)
                mode = interact_service.get_auto_reply_setting(persona_id)

                if mode == "auto" and risk_level == "low":
                    # Auto-send low-risk replies
                    token_info = ig_token_store.get(persona_id, {})
                    access_token = token_info.get("access_token", "")
                    if access_token:
                        draft = interact_service.add_pending_reply(
                            persona_id, ig_comment_id, ig_media_id,
                            commenter_name, comment_text, draft_text, risk_level,
                        )
                        interact_service.send_reply(draft["reply_id"], access_token)
                    else:
                        logger.warning("Auto mode but no access_token for persona_id=%s, queuing as draft", persona_id)
                        interact_service.add_pending_reply(
                            persona_id, ig_comment_id, ig_media_id,
                            commenter_name, comment_text, draft_text, risk_level,
                        )
                else:
                    # Draft mode (or high risk): queue for human review
                    interact_service.add_pending_reply(
                        persona_id, ig_comment_id, ig_media_id,
                        commenter_name, comment_text, draft_text, risk_level,
                    )
            except Exception as exc:
                logger.error("Error processing comment event: %s", exc)

    return {"status": "ok"}


def _resolve_persona_id(ig_account_id: str) -> str:
    """
    Try to find which persona owns the given ig_account_id.
    Falls back to 'demo' if not found.
    """
    for persona_id, info in ig_token_store.items():
        if info.get("ig_account_id") == ig_account_id:
            return persona_id
    return "demo"


# ---------------------------------------------------------------------------
# Pending Replies
# ---------------------------------------------------------------------------

@router.get("/replies/pending/{persona_id}")
async def get_pending_replies(persona_id: str):
    """Return all pending reply drafts for the given persona."""
    drafts = interact_service.get_pending_replies(persona_id)
    return {"persona_id": persona_id, "replies": drafts, "count": len(drafts)}


# ---------------------------------------------------------------------------
# Send Reply
# ---------------------------------------------------------------------------

class SendReplyBody(BaseModel):
    persona_id: str


@router.post("/replies/{reply_id}/send")
async def send_reply(reply_id: str, body: SendReplyBody):
    """
    Confirm and send a queued reply draft to Instagram.
    Looks up the access_token via instagram_service token store.
    """
    token_info = ig_token_store.get(body.persona_id, {})
    access_token = token_info.get("access_token", "")
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail=f"No Instagram access token found for persona_id={body.persona_id}",
        )

    try:
        draft = interact_service.send_reply(reply_id, access_token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"status": "sent", "reply": draft}


# ---------------------------------------------------------------------------
# Dismiss Reply
# ---------------------------------------------------------------------------

@router.post("/replies/{reply_id}/dismiss")
async def dismiss_reply(reply_id: str):
    """Mark a reply draft as dismissed (won't be sent)."""
    try:
        draft = interact_service.dismiss_reply(reply_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "dismissed", "reply": draft}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.get("/settings/{persona_id}")
async def get_settings(persona_id: str):
    """Return the auto-reply mode setting for the given persona."""
    mode = interact_service.get_auto_reply_setting(persona_id)
    return {"persona_id": persona_id, "mode": mode}


class SettingsBody(BaseModel):
    mode: str  # "draft" | "auto"


@router.post("/settings/{persona_id}")
async def update_settings(persona_id: str, body: SettingsBody):
    """Update the auto-reply mode setting for the given persona."""
    try:
        interact_service.set_auto_reply_setting(persona_id, body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"persona_id": persona_id, "mode": body.mode, "status": "updated"}
