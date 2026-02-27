"""
Unit tests for schedule_storage.py
Uses a temporary directory — no external services needed.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Redirect STORAGE_DIR to a temp directory for each test."""
    import app.services.schedule_storage as ss
    monkeypatch.setattr(ss, "STORAGE_DIR", tmp_path)
    return tmp_path


SAMPLE_POSTS = [
    {"day": 1, "date": "2026-02-28", "scene": "咖啡廳", "caption": "早安", "image_url": "https://res.cloudinary.com/test/a.jpg", "status": "draft"},
    {"day": 2, "date": "2026-03-01", "scene": "健身房", "caption": "練腿日", "image_url": "https://res.cloudinary.com/test/b.jpg", "status": "draft"},
    {"day": 3, "date": "2026-03-02", "scene": "夜市",   "caption": "吃貨",  "image_url": "https://res.cloudinary.com/test/c.jpg", "status": "draft"},
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
        new_posts = [{"day": 1, "date": "2026-04-01", "status": "approved"}]
        save_schedule("persona_3", new_posts)
        assert load_schedule("persona_3") == new_posts

    def test_file_is_valid_json(self, tmp_storage):
        from app.services.schedule_storage import save_schedule
        save_schedule("persona_4", SAMPLE_POSTS)
        raw = (tmp_storage / "persona_4.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["persona_id"] == "persona_4"
        assert data["posts"] == SAMPLE_POSTS

    def test_load_ignores_corrupted_file(self, tmp_storage):
        from app.services.schedule_storage import load_schedule
        (tmp_storage / "bad.json").write_text("not json", encoding="utf-8")
        assert load_schedule("bad") == []


class TestUpdatePostStatus:
    def test_update_existing_day(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, update_post_status, load_schedule
        save_schedule("persona_5", SAMPLE_POSTS)
        ok = update_post_status("persona_5", day=1, status="approved")
        assert ok is True
        posts = load_schedule("persona_5")
        assert posts[0]["status"] == "approved"
        # Other days unchanged
        assert posts[1]["status"] == "draft"

    def test_update_nonexistent_persona_returns_false(self, tmp_storage):
        from app.services.schedule_storage import update_post_status
        assert update_post_status("ghost", day=1, status="approved") is False

    def test_update_nonexistent_day_returns_false(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, update_post_status
        save_schedule("persona_6", SAMPLE_POSTS)
        assert update_post_status("persona_6", day=99, status="approved") is False

    def test_update_persists_to_disk(self, tmp_storage):
        from app.services.schedule_storage import save_schedule, update_post_status
        import app.services.schedule_storage as ss
        save_schedule("persona_7", SAMPLE_POSTS)
        update_post_status("persona_7", day=2, status="rejected")
        raw = json.loads((tmp_storage / "persona_7.json").read_text())
        day2 = next(p for p in raw["posts"] if p["day"] == 2)
        assert day2["status"] == "rejected"
