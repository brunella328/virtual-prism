"""
Schedule Storage Service
------------------------
每個 persona 的發文排程存為獨立 JSON 檔案：
  data/schedules/{persona_id}.json

Schema:
{
  "persona_id": "...",
  "updated_at": "2026-02-27T...",
  "posts": [
    {
      "day": 1,
      "date": "2026-02-28",
      "scene": "...",
      "caption": "...",
      "image_url": "https://res.cloudinary.com/...",
      "image_prompt": "...",
      "status": "draft",
      "hashtags": [...]
    }
  ]
}
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

STORAGE_DIR = Path(__file__).parent.parent.parent / "data" / "schedules"


def _ensure_dir():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_schedule(persona_id: str, posts: List[dict]) -> None:
    """儲存排程（覆寫）"""
    _ensure_dir()
    data = {
        "persona_id": persona_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "posts": posts,
    }
    (STORAGE_DIR / f"{persona_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_schedule(persona_id: str) -> List[dict]:
    """讀取排程，不存在時回傳空陣列"""
    path = STORAGE_DIR / f"{persona_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("posts", [])
    except Exception:
        return []


def update_post_status(persona_id: str, day: int, status: str) -> bool:
    """更新單篇貼文狀態（draft / approved / rejected）"""
    posts = load_schedule(persona_id)
    if not posts:
        return False
    for post in posts:
        if post.get("day") == day:
            post["status"] = status
            save_schedule(persona_id, posts)
            return True
    return False


def update_post_content(persona_id: str, day: int, caption: str, scene_prompt: str) -> bool:
    """更新單篇貼文的文案與重繪方向"""
    posts = load_schedule(persona_id)
    if not posts:
        return False
    for post in posts:
        if post.get("day") == day:
            post["caption"] = caption
            post["scene_prompt"] = scene_prompt
            save_schedule(persona_id, posts)
            return True
    return False
