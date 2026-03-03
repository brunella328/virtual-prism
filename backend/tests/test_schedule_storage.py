"""
Unit tests for schedule_storage.py
Uses a temporary directory — no external services needed.
"""
import pytest
import json
from pathlib import Path


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Redirect STORAGE_DIR to a temp directory for each test."""
    import app.services.schedule_storage as ss
    monkeypatch.setattr(ss, "STORAGE_DIR", tmp_path)
    return tmp_path


SAMPLE_POSTS = [
    {"post_id": "pid-1", "day": 1, "date": "2026-02-28", "scene": "咖啡廳", "caption": "早安", "image_url": "https://res.cloudinary.com/test/a.jpg", "status": "draft"},
    {"post_id": "pid-2", "day": 2, "date": "2026-03-01", "scene": "健身房", "caption": "練腿日", "image_url": "https://res.cloudinary.com/test/b.jpg", "status": "draft"},
    {"post_id": "pid-3", "day": 3, "date": "2026-03-02", "scene": "夜市",   "caption": "吃貨",  "image_url": "https://res.cloudinary.com/test/c.jpg", "status": "draft"},
]


class TestSaveAndLoad:
    def test_save_then_load_returns_same_posts(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, load_schedule
        save_schedule("persona_1", SAMPLE_POSTS)
        result = load_schedule("persona_1")
        assert result == SAMPLE_POSTS

    def test_load_nonexistent_returns_empty(self, tmp_storage):
        from app.services.schedule_storage import load_schedule
        assert load_schedule("nobody") == []

    def test_save_creates_file(self, tmp_storage):
        from app.services.schedule_storage import save_schedule
        save_schedule("persona_2", SAMPLE_POSTS)
        assert (tmp_storage / "persona_2.json").exists()

    def test_save_overwrites_previous(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, load_schedule
        save_schedule("persona_3", SAMPLE_POSTS)
        new_posts = [{"post_id": "pid-x", "day": 1, "date": "2026-04-01", "status": "approved"}]
        save_schedule("persona_3", new_posts)
        assert load_schedule("persona_3") == new_posts

    def test_file_is_valid_json(self, tmp_storage):
        from app.services.schedule_storage import save_schedule
        save_schedule("persona_4", SAMPLE_POSTS)
        raw = (tmp_storage / "persona_4.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["persona_id"] == "persona_4"
        assert len(data["posts"]) == len(SAMPLE_POSTS)
        assert data["posts"][0]["post_id"] == "pid-1"

    def test_load_ignores_corrupted_file(self, tmp_storage):
        from app.services.schedule_storage import load_schedule
        (tmp_storage / "bad.json").write_text("not json", encoding="utf-8")
        assert load_schedule("bad") == []

    def test_load_auto_assigns_post_id_to_legacy_posts(self, tmp_storage):
        """舊資料（無 post_id）load 時自動補 UUID"""
        from app.services.schedule_storage import load_schedule
        legacy = [{"day": 1, "date": "2026-01-01", "status": "draft"}]
        (tmp_storage / "legacy.json").write_text(
            json.dumps({"persona_id": "legacy", "posts": legacy}),
            encoding="utf-8",
        )
        result = load_schedule("legacy")
        assert len(result) == 1
        assert "post_id" in result[0]
        assert len(result[0]["post_id"]) == 36  # UUID format

    def test_save_does_not_mutate_input(self, tmp_storage):
        """save_schedule 不應修改傳入的 list/dict"""
        from app.services.schedule_storage import save_schedule
        posts = [{"day": 1, "date": "2026-01-01", "status": "draft"}]
        save_schedule("persona_x", posts)
        assert "post_id" not in posts[0]  # 原始 dict 未被 mutate


class TestUpdatePostStatus:
    def test_update_existing_post(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, update_post_status, load_schedule
        save_schedule("persona_5", SAMPLE_POSTS)
        ok = update_post_status("persona_5", post_id="pid-1", status="approved")
        assert ok is True
        posts = load_schedule("persona_5")
        assert posts[0]["status"] == "approved"
        assert posts[1]["status"] == "draft"  # 其他篇不受影響

    def test_update_nonexistent_persona_returns_false(self, tmp_storage):
        from app.services.schedule_storage import update_post_status
        assert update_post_status("ghost", post_id="pid-1", status="approved") is False

    def test_update_nonexistent_post_id_returns_false(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, update_post_status
        save_schedule("persona_6", SAMPLE_POSTS)
        assert update_post_status("persona_6", post_id="not-exist", status="approved") is False

    def test_update_persists_to_disk(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, update_post_status
        save_schedule("persona_7", SAMPLE_POSTS)
        update_post_status("persona_7", post_id="pid-2", status="rejected")
        raw = json.loads((tmp_storage / "persona_7.json").read_text())
        post2 = next(p for p in raw["posts"] if p["post_id"] == "pid-2")
        assert post2["status"] == "rejected"


class TestGetPost:
    def test_get_existing_post(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, get_post
        save_schedule("persona_8", SAMPLE_POSTS)
        post = get_post("persona_8", "pid-2")
        assert post is not None
        assert post["scene"] == "健身房"

    def test_get_nonexistent_returns_none(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, get_post
        save_schedule("persona_9", SAMPLE_POSTS)
        assert get_post("persona_9", "not-exist") is None


class TestUpdatePostFields:
    def test_update_multiple_fields(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, update_post_fields, load_schedule
        save_schedule("persona_10", SAMPLE_POSTS)
        ok = update_post_fields("persona_10", "pid-3", scheduled_at="2026-03-10T09:00:00Z", job_id="job-abc")
        assert ok is True
        posts = load_schedule("persona_10")
        post3 = next(p for p in posts if p["post_id"] == "pid-3")
        assert post3["scheduled_at"] == "2026-03-10T09:00:00Z"
        assert post3["job_id"] == "job-abc"
