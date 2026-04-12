import json
import os
from pathlib import Path
from app.models.chat_session import ChatSession

DATA_DIR = Path("data/chat_sessions")


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_session(session: ChatSession) -> None:
    _ensure_dir()
    path = DATA_DIR / f"{session.id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session.model_dump(), f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> ChatSession:
    path = DATA_DIR / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"ChatSession {session_id} not found")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ChatSession(**data)


def update_session(session: ChatSession) -> None:
    save_session(session)
