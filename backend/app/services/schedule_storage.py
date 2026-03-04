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
      "post_id": "uuid-v4",          ← 唯一識別（T1 新增）
      "day": 1,                       ← display/ordering index（保留，由 LLM 輸出）
      "date": "2026-02-28",
      "scene": "...",
      "caption": "...",
      "image_url": "https://res.cloudinary.com/...",
      "image_prompt": "...",
      "scene_prompt": "...",
      "status": "draft",              ← draft / scheduled / publishing / published / failed
      "scheduled_at": null,           ← 排程時間（ISO 8601），持久化
      "job_id": null,                 ← APScheduler job UUID，排程後寫入
      "published_at": null,           ← 實際發布時間
      "ig_media_id": null,            ← IG 回傳 media_id
      "error_message": null,          ← 發布失敗原因
      "hashtags": [...]
    }
  ]
}
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

STORAGE_DIR = Path(__file__).parent.parent.parent / "data" / "schedules"


def _ensure_dir():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _assign_missing_post_ids(posts: List[dict]) -> tuple[List[dict], bool]:
    """舊資料向後兼容：補丁缺少 post_id 的 post，回傳 (posts, was_modified)。"""
    modified = False
    for post in posts:
        if not post.get("post_id"):
            post["post_id"] = str(uuid.uuid4())
            modified = True
    return posts, modified


def save_schedule(persona_id: str, posts: List[dict]) -> None:
    """儲存排程（覆寫）。寫入前確保每篇有 post_id（不 mutate 原始 list）。"""
    _ensure_dir()
    posts_to_save = []
    for post in posts:
        p = {**post}
        if not p.get("post_id"):
            p["post_id"] = str(uuid.uuid4())
        posts_to_save.append(p)
    data = {
        "persona_id": persona_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "posts": posts_to_save,
    }
    (STORAGE_DIR / f"{persona_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_schedule(persona_id: str) -> List[dict]:
    """讀取排程。舊資料自動補丁 post_id 並回寫。不存在時回傳空陣列。"""
    path = STORAGE_DIR / f"{persona_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        posts = data.get("posts", [])
        posts, modified = _assign_missing_post_ids(posts)
        if modified:
            save_schedule(persona_id, posts)
        return posts
    except Exception:
        return []


def get_post(persona_id: str, post_id: str) -> Optional[dict]:
    """回傳單篇貼文，找不到時回傳 None。"""
    for post in load_schedule(persona_id):
        if post.get("post_id") == post_id:
            return post
    return None


def update_post_fields(persona_id: str, post_id: str, **kwargs) -> bool:
    """通用欄位更新（可一次更新多個欄位）。value=None 表示刪除該欄位。"""
    posts = load_schedule(persona_id)
    for post in posts:
        if post.get("post_id") == post_id:
            for k, v in kwargs.items():
                if v is None:
                    post.pop(k, None)
                else:
                    post[k] = v
            save_schedule(persona_id, posts)
            return True
    return False


def update_post_status(persona_id: str, post_id: str, status: str) -> bool:
    """更新單篇貼文狀態（draft / scheduled / publishing / published / failed）"""
    return update_post_fields(persona_id, post_id, status=status)


def update_post_content(persona_id: str, post_id: str, caption: str, scene_prompt: str) -> bool:
    """更新單篇貼文的文案與重繪方向"""
    return update_post_fields(persona_id, post_id, caption=caption, scene_prompt=scene_prompt)


def update_post_scheduled_at(persona_id: str, post_id: str, scheduled_at: str) -> bool:
    """儲存 Instagram 排程時間（ISO 8601）"""
    return update_post_fields(persona_id, post_id, scheduled_at=scheduled_at)


def update_post_image(persona_id: str, post_id: str, image_url: str, image_prompt: str) -> bool:
    """套用重繪結果：更新 image_url 與 image_prompt"""
    return update_post_fields(persona_id, post_id, image_url=image_url, image_prompt=image_prompt)
