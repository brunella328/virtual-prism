"""
Fan Memory Service (T11) — 粉絲記憶庫
MVP: in-memory dict store（可替換為 Pinecone / Chroma 向量資料庫）

FanRecord 結構：
  fan_id            : str   — IG user ID
  username          : str   — IG username
  interaction_count : int   — 累計互動次數
  last_interaction  : str   — 最後互動時間（ISO datetime）
  notes             : str   — 累計互動摘要（每次追加）
  first_seen        : str   — 首次互動時間（ISO datetime）
"""

import logging
from datetime import datetime, timezone
from typing import TypedDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FanRecord TypedDict
# ---------------------------------------------------------------------------

class FanRecord(TypedDict):
    fan_id: str
    username: str
    interaction_count: int
    last_interaction: str   # ISO datetime
    notes: str              # 累計互動摘要
    first_seen: str         # ISO datetime


# ---------------------------------------------------------------------------
# In-memory store — replace with Pinecone/Chroma in production
# Key: "persona_id:fan_id"
# ---------------------------------------------------------------------------

fan_store: dict[str, FanRecord] = {}


def _store_key(persona_id: str, fan_id: str) -> str:
    return f"{persona_id}:{fan_id}"


# ---------------------------------------------------------------------------
# Core CRUD functions
# ---------------------------------------------------------------------------

def upsert_fan(
    persona_id: str,
    fan_id: str,
    username: str,
    comment_text: str,
) -> FanRecord:
    """
    建立或更新粉絲記錄。
    - 若不存在：新建 FanRecord
    - 若存在：interaction_count += 1、更新 last_interaction、追加 notes
    """
    key = _store_key(persona_id, fan_id)
    now = datetime.now(timezone.utc).isoformat()

    if key not in fan_store:
        record: FanRecord = {
            "fan_id": fan_id,
            "username": username,
            "interaction_count": 1,
            "last_interaction": now,
            "notes": comment_text,
            "first_seen": now,
        }
        fan_store[key] = record
        logger.info("New fan record: persona_id=%s fan_id=%s username=%s", persona_id, fan_id, username)
    else:
        record = fan_store[key]
        record["interaction_count"] += 1
        record["last_interaction"] = now
        # Append new comment to notes (separated by " | ")
        if record["notes"]:
            record["notes"] = record["notes"] + " | " + comment_text
        else:
            record["notes"] = comment_text
        # Update username in case it changed
        record["username"] = username
        logger.info(
            "Updated fan record: persona_id=%s fan_id=%s count=%d",
            persona_id, fan_id, record["interaction_count"],
        )

    return fan_store[key]


def get_fan(persona_id: str, fan_id: str) -> FanRecord | None:
    """Return the FanRecord for the given persona + fan, or None if not found."""
    return fan_store.get(_store_key(persona_id, fan_id))


def list_fans(persona_id: str, limit: int = 20) -> list[FanRecord]:
    """
    Return up to `limit` fan records for the given persona,
    sorted by interaction_count (descending).
    """
    prefix = f"{persona_id}:"
    records = [v for k, v in fan_store.items() if k.startswith(prefix)]
    records.sort(key=lambda r: r["interaction_count"], reverse=True)
    return records[:limit]


def get_fan_context(persona_id: str, fan_id: str) -> str:
    """
    Return a human-readable fan context string for prompt injection.
    - 若有記錄：返回 "這位粉絲 @{username} 已互動 {count} 次，上次留言：{notes[-100:]}"
    - 若無記錄：返回 ""
    """
    record = get_fan(persona_id, fan_id)
    if not record:
        return ""
    notes_snippet = record["notes"][-100:] if record["notes"] else ""
    return (
        f"這位粉絲 @{record['username']} 已互動 {record['interaction_count']} 次，"
        f"上次留言：{notes_snippet}"
    )
