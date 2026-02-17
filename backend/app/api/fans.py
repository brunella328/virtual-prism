"""
Fan Memory API (T11) — 粉絲記憶庫 Endpoints

GET /api/fans/{persona_id}           — 列出指定 persona 的所有粉絲記錄
GET /api/fans/{persona_id}/{fan_id}  — 查詢單一粉絲記錄
"""

import logging

from fastapi import APIRouter, HTTPException

from app.services import fan_memory_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{persona_id}")
async def list_fans(persona_id: str, limit: int = 20):
    """
    Return up to `limit` fan records for the given persona,
    sorted by interaction_count (descending).
    """
    fans = fan_memory_service.list_fans(persona_id, limit=limit)
    return {
        "persona_id": persona_id,
        "fans": fans,
        "count": len(fans),
    }


@router.get("/{persona_id}/{fan_id}")
async def get_fan(persona_id: str, fan_id: str):
    """Return a single fan record for the given persona + fan."""
    record = fan_memory_service.get_fan(persona_id, fan_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Fan not found: persona_id={persona_id} fan_id={fan_id}",
        )
    return record
