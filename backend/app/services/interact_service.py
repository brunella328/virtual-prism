"""
Interact Service (T10) — Auto-Reply System with RAG + Draft Mode
- RAG Pipeline (in-memory fallback for MVP)
- Reply draft generation via Claude API
- Risk control via keyword matching
- In-memory draft store (replace with DB in production)
- IG comment reply via Graph API
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import TypedDict

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk Control
# ---------------------------------------------------------------------------

NEGATIVE_KEYWORDS = ["詐騙", "假的", "退款", "投訴", "死", "爛", "垃圾", "騙", "黑心"]


def check_risk(text: str) -> str:
    """Return 'high' if any negative keyword is found in text, else 'low'."""
    for kw in NEGATIVE_KEYWORDS:
        if kw in text:
            return "high"
    return "low"


# ---------------------------------------------------------------------------
# RAG Pipeline — MVP: in-memory fallback, replace with Pinecone in production
# ---------------------------------------------------------------------------

# { persona_id: [ { "id": str, "text": str } ] }
_persona_index: dict[str, list[dict]] = {}


def _persona_json_to_chunks(persona_json: dict) -> list[str]:
    """
    Convert a persona JSON dict into text chunks for indexing.
    Handles PersonaCard fields: name, occupation, personality_tags,
    speech_pattern, values, weekly_lifestyle, appearance, etc.
    """
    chunks = []

    if "name" in persona_json:
        chunks.append(f"名稱：{persona_json['name']}")

    if "occupation" in persona_json:
        chunks.append(f"職業：{persona_json['occupation']}")

    if "personality_tags" in persona_json:
        tags = persona_json["personality_tags"]
        if isinstance(tags, list):
            chunks.append(f"個性標籤：{', '.join(tags)}")

    if "speech_pattern" in persona_json:
        chunks.append(f"口癖 / 說話方式：{persona_json['speech_pattern']}")

    if "values" in persona_json:
        vals = persona_json["values"]
        if isinstance(vals, list):
            chunks.append(f"價值觀：{', '.join(vals)}")

    if "weekly_lifestyle" in persona_json:
        chunks.append(f"生活方式：{persona_json['weekly_lifestyle']}")

    # Flatten appearance sub-fields
    if "appearance" in persona_json and isinstance(persona_json["appearance"], dict):
        app = persona_json["appearance"]
        for key, val in app.items():
            if val:
                chunks.append(f"外貌-{key}：{val}")

    # Generic fallback: pick up any top-level string/list not already handled
    handled = {"name", "occupation", "personality_tags", "speech_pattern",
               "values", "weekly_lifestyle", "appearance", "id"}
    for k, v in persona_json.items():
        if k in handled:
            continue
        if isinstance(v, str) and v:
            chunks.append(f"{k}：{v}")
        elif isinstance(v, list):
            chunks.append(f"{k}：{', '.join(str(i) for i in v)}")

    return chunks


def build_persona_index(persona_id: str, persona_json: dict) -> None:
    """
    Build (or rebuild) the in-memory RAG index for a persona.
    MVP: in-memory fallback, replace with Pinecone in production.
    """
    chunks = _persona_json_to_chunks(persona_json)
    _persona_index[persona_id] = [
        {"id": f"{persona_id}_{i}", "text": chunk}
        for i, chunk in enumerate(chunks)
    ]
    logger.info("Built persona index for persona_id=%s (%d chunks)", persona_id, len(chunks))


def query_persona_context(persona_id: str, query_text: str, top_k: int = 3) -> list[str]:
    """
    Return the top_k most relevant persona text chunks for the query.
    MVP: in-memory fallback with keyword matching — replace with Pinecone in production.
    """
    chunks = _persona_index.get(persona_id, [])
    if not chunks:
        return []

    query_lower = query_text.lower()
    query_tokens = set(query_lower.split())

    # Score each chunk by overlap with query tokens
    scored = []
    for chunk in chunks:
        chunk_lower = chunk["text"].lower()
        # Count how many query tokens appear in this chunk
        score = sum(1 for tok in query_tokens if tok in chunk_lower)
        scored.append((score, chunk["text"]))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [text for _, text in scored[:top_k]]

    # If no matches, just return first top_k chunks
    if all(s == 0 for s, _ in scored[:top_k]):
        top = [c["text"] for c in chunks[:top_k]]

    return top


# ---------------------------------------------------------------------------
# Reply Draft Generation (Claude API)
# ---------------------------------------------------------------------------

def is_dm_expired(created_at_iso: str) -> bool:
    """Return True if the DM is older than 24 hours (outside the messaging window)."""
    from datetime import timedelta
    try:
        created = datetime.fromisoformat(created_at_iso)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - created > timedelta(hours=24)
    except Exception:
        return False


def generate_reply_draft(
    persona_id: str,
    comment_text: str,
    commenter_name: str,
    fan_id: str = "",
    channel: str = "comment",
) -> str:
    """
    Generate a reply draft using Claude that matches the persona's voice.
    Falls back to a safe canned reply if the API call fails.

    fan_id (optional): when provided, fan memory context is injected into
    the prompt so Claude can personalise the reply for returning fans.
    """
    from app.services import fan_memory_service  # avoid circular import

    context_chunks = query_persona_context(persona_id, comment_text, top_k=3)
    persona_context = "\n".join(context_chunks) if context_chunks else "這是一個友善的虛擬網紅人設。"

    # Inject fan memory context if available
    fan_context = fan_memory_service.get_fan_context(persona_id, fan_id) if fan_id else ""
    fan_section = f"\n粉絲資訊：{fan_context}" if fan_context else ""

    if channel == "dm":
        interaction_context = f"有一位名叫「{commenter_name}」的粉絲傳了 Instagram 私訊（DM）給你：\n「{comment_text}」"
        tone_note = "- 語氣比公開留言更私密、更個人化，像是朋友間的對話\n- 不超過 100 字"
    else:
        interaction_context = f"有一位名叫「{commenter_name}」的粉絲在 Instagram 留言：\n「{comment_text}」"
        tone_note = "- 親切自然，不能太正式或太生硬\n- 不超過 150 字"

    prompt = f"""你是一個 AI 虛擬網紅，以下是你的人設資料：

{persona_context}{fan_section}

{interaction_context}

請根據你的人設，以符合你個性和語氣的方式，撰寫一則回覆給這位粉絲。
要求：
{tone_note}
- 可以加入適當的 emoji
- 若粉絲資訊中有 username，可以在回覆中叫出粉絲名字，讓回覆更個人化
- 只輸出回覆內容本身，不要加任何說明或前言"""

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        logger.warning("ANTHROPIC_API_KEY not set, returning fallback draft")
        return f"謝謝 {commenter_name} 的留言！😊 很高興聽到你的聲音，我們下次再聊！"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        draft = message.content[0].text.strip()
        return draft
    except Exception as exc:
        logger.error("Claude API error: %s", exc)
        return f"謝謝 {commenter_name} 的留言！😊 很高興和你互動，期待你的下次留言！"


# ---------------------------------------------------------------------------
# Draft Store — in-memory for MVP
# ---------------------------------------------------------------------------

class ReplyDraft(TypedDict):
    reply_id: str
    persona_id: str
    channel: str          # "comment" | "dm"
    ig_comment_id: str
    ig_media_id: str
    sender_igsid: str     # DM 專用：sender 的 IGSID（comment 留空）
    commenter_name: str
    comment_text: str
    draft_text: str
    risk_level: str   # "high" | "low"
    status: str       # "pending" | "sent" | "dismissed"
    created_at: str   # ISO datetime


# { reply_id: ReplyDraft }
pending_replies: dict[str, ReplyDraft] = {}

# { persona_id: "draft" | "auto" }
_auto_reply_settings: dict[str, str] = {}


def add_pending_reply(
    persona_id: str,
    ig_comment_id: str,
    ig_media_id: str,
    commenter_name: str,
    comment_text: str,
    draft_text: str,
    risk_level: str,
    channel: str = "comment",
    sender_igsid: str = "",
) -> ReplyDraft:
    """Add a new reply draft to the pending store."""
    reply_id = str(uuid.uuid4())
    draft: ReplyDraft = {
        "reply_id": reply_id,
        "persona_id": persona_id,
        "channel": channel,
        "ig_comment_id": ig_comment_id,
        "ig_media_id": ig_media_id,
        "sender_igsid": sender_igsid,
        "commenter_name": commenter_name,
        "comment_text": comment_text,
        "draft_text": draft_text,
        "risk_level": risk_level,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    pending_replies[reply_id] = draft
    logger.info(
        "Added pending reply reply_id=%s persona_id=%s risk=%s",
        reply_id, persona_id, risk_level,
    )
    return draft


def get_pending_replies(persona_id: str) -> list[ReplyDraft]:
    """Return all pending-status drafts for the given persona."""
    return [
        draft for draft in pending_replies.values()
        if draft["persona_id"] == persona_id and draft["status"] == "pending"
    ]


def send_reply(reply_id: str, access_token: str) -> ReplyDraft:
    """
    Post the draft reply to Instagram via the Graph API, then mark as sent.
    IG API: POST https://graph.instagram.com/v18.0/{comment_id}/replies
    """
    draft = pending_replies.get(reply_id)
    if not draft:
        raise ValueError(f"Reply not found: {reply_id}")
    if draft["status"] != "pending":
        raise ValueError(f"Reply is not in pending state: {draft['status']}")

    ig_comment_id = draft["ig_comment_id"]
    message_text = draft["draft_text"]

    # Call IG Graph API to post reply
    url = f"https://graph.instagram.com/v18.0/{ig_comment_id}/replies"
    try:
        resp = requests.post(url, params={
            "message": message_text,
            "access_token": access_token,
        }, timeout=15)
        resp.raise_for_status()
        logger.info("Sent reply for reply_id=%s ig_comment_id=%s", reply_id, ig_comment_id)
    except Exception as exc:
        logger.error("Failed to send reply to IG: %s", exc)
        raise RuntimeError(f"IG API error: {exc}") from exc

    draft["status"] = "sent"
    return draft


def send_dm(reply_id: str, access_token: str) -> ReplyDraft:
    """
    Send a DM reply via Instagram Graph API, then mark as sent.
    IG API: POST https://graph.instagram.com/v18.0/me/messages
    Requires: instagram_business_manage_messages scope.
    """
    draft = pending_replies.get(reply_id)
    if not draft:
        raise ValueError(f"Reply not found: {reply_id}")
    if draft["status"] != "pending":
        raise ValueError(f"Reply is not in pending state: {draft['status']}")

    sender_igsid = draft["sender_igsid"]
    message_text = draft["draft_text"]

    url = "https://graph.instagram.com/v18.0/me/messages"
    try:
        resp = requests.post(url, json={
            "recipient": {"id": sender_igsid},
            "message": {"text": message_text},
        }, params={"access_token": access_token}, timeout=15)
        resp.raise_for_status()
        logger.info("Sent DM for reply_id=%s sender_igsid=%s", reply_id, sender_igsid)
    except Exception as exc:
        logger.error("Failed to send DM to IG: %s", exc)
        raise RuntimeError(f"IG DM API error: {exc}") from exc

    draft["status"] = "sent"
    return draft


def dismiss_reply(reply_id: str) -> ReplyDraft:
    """Mark a reply draft as dismissed."""
    draft = pending_replies.get(reply_id)
    if not draft:
        raise ValueError(f"Reply not found: {reply_id}")
    draft["status"] = "dismissed"
    logger.info("Dismissed reply reply_id=%s", reply_id)
    return draft


def get_auto_reply_setting(persona_id: str) -> str:
    """Return the current auto-reply mode for a persona ('draft' or 'auto')."""
    return _auto_reply_settings.get(persona_id, "draft")


def set_auto_reply_setting(persona_id: str, mode: str) -> None:
    """Set the auto-reply mode for a persona ('draft' or 'auto')."""
    if mode not in ("draft", "auto"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'draft' or 'auto'.")
    _auto_reply_settings[persona_id] = mode
    logger.info("Set auto-reply mode for persona_id=%s → %s", persona_id, mode)
