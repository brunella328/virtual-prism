"""
Users Storage Service
---------------------
平台帳號存儲：data/users/{uuid}.json

Schema:
{
  "uuid": "...",
  "email": "...",
  "hashed_password": "...",
  "email_verified": false,
  "verification_token": "...",
  "posts_generated": 0,
  "created_at": "2026-03-10T..."
}
"""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

STORAGE_DIR = Path(__file__).parent.parent.parent / "data" / "users"

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)


def _ensure_dir():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _path(user_uuid: str) -> Path:
    if not _UUID_RE.match(user_uuid):
        raise ValueError(f"Invalid user UUID: {user_uuid!r}")
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
        "email_verified": False,
        "verification_token": str(uuid.uuid4()),
        "posts_generated": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_user(user)
    return user


def verify_email(token: str) -> Optional[dict]:
    """找到對應 verification_token 的 user，標記為已驗證並清除 token"""
    _ensure_dir()
    for p in STORAGE_DIR.glob("*.json"):
        with open(p, encoding="utf-8") as f:
            user = json.load(f)
        if user.get("verification_token") == token:
            user["email_verified"] = True
            user["verification_token"] = None
            save_user(user)
            return user
    return None


def increment_posts_generated(user_uuid: str, count: int = 1) -> Optional[dict]:
    user = get_user_by_uuid(user_uuid)
    if not user:
        return None
    user["posts_generated"] = user.get("posts_generated", 0) + count
    save_user(user)
    return user
