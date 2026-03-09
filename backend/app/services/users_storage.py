"""
Users Storage Service
---------------------
平台帳號存儲：data/users/{uuid}.json

Schema:
{
  "uuid": "...",
  "email": "...",
  "hashed_password": "...",
  "ig_token": null,
  "ig_user_id": null,
  "created_at": "2026-03-10T..."
}
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

STORAGE_DIR = Path(__file__).parent.parent.parent / "data" / "users"


def _ensure_dir():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _path(user_uuid: str) -> Path:
    return STORAGE_DIR / f"{user_uuid}.json"


def save_user(user: dict) -> None:
    _ensure_dir()
    with open(_path(user["uuid"]), "w", encoding="utf-8") as f:
        json.dump(user, f, ensure_ascii=False, indent=2)


def get_user_by_uuid(user_uuid: str) -> Optional[dict]:
    p = _path(user_uuid)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_user_by_email(email: str) -> Optional[dict]:
    _ensure_dir()
    for p in STORAGE_DIR.glob("*.json"):
        with open(p, encoding="utf-8") as f:
            user = json.load(f)
        if user.get("email", "").lower() == email.lower():
            return user
    return None


def create_user(email: str, hashed_password: str) -> dict:
    user = {
        "uuid": str(uuid.uuid4()),
        "email": email.lower(),
        "hashed_password": hashed_password,
        "ig_token": None,
        "ig_user_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_user(user)
    return user


def update_ig_token(user_uuid: str, ig_token: Optional[str], ig_user_id: Optional[str]) -> Optional[dict]:
    user = get_user_by_uuid(user_uuid)
    if not user:
        return None
    user["ig_token"] = ig_token
    user["ig_user_id"] = ig_user_id
    save_user(user)
    return user
