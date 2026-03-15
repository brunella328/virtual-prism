"""
Unit tests for backup_service — local archive creation and rotation.
S3 upload is not tested here (requires live credentials).
"""
import tarfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_dirs(tmp_path, monkeypatch):
    """Override DATA_DIR and BACKUP_DIR to isolated temp directories."""
    import app.services.backup_service as svc
    data_dir   = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "personas").mkdir()
    (data_dir / "users").mkdir()
    # Plant dummy files so the archive is non-empty
    (data_dir / "personas" / "test.json").write_text('{"name": "test"}')
    (data_dir / "users"    / "user.json").write_text('{"email": "a@b.com"}')

    monkeypatch.setattr(svc, "DATA_DIR",   data_dir)
    monkeypatch.setattr(svc, "BACKUP_DIR", backup_dir)
    return data_dir, backup_dir


# ── _create_archive ──────────────────────────────────────────────────────────

def test_create_archive_produces_tar_gz(tmp_dirs):
    from app.services.backup_service import _create_archive
    _, backup_dir = tmp_dirs
    archive = _create_archive()
    assert archive.exists()
    assert archive.suffix == ".gz"
    assert tarfile.is_tarfile(archive)


def test_archive_contains_data_directory(tmp_dirs):
    from app.services.backup_service import _create_archive
    data_dir, _ = tmp_dirs
    archive = _create_archive()
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
    assert any("personas/test.json" in n for n in names)
    assert any("users/user.json"    in n for n in names)


# ── _rotate_local ────────────────────────────────────────────────────────────

def test_rotation_removes_oldest(tmp_dirs, monkeypatch):
    from app.services import backup_service as svc
    _, backup_dir = tmp_dirs
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create 5 dummy archives with different timestamps
    archives = []
    for i in range(5):
        p = backup_dir / f"backup_2024-01-0{i+1}_00-00-00.tar.gz"
        p.write_bytes(b"dummy")
        archives.append(p)

    svc._rotate_local(keep=3)

    remaining = sorted(backup_dir.glob("backup_*.tar.gz"))
    assert len(remaining) == 3
    # Newest 3 should survive
    assert archives[-1] in remaining
    assert archives[-2] in remaining
    assert archives[-3] in remaining
    # Oldest 2 should be gone
    assert not archives[0].exists()
    assert not archives[1].exists()


def test_rotation_no_op_when_under_limit(tmp_dirs):
    from app.services import backup_service as svc
    _, backup_dir = tmp_dirs
    backup_dir.mkdir(parents=True, exist_ok=True)
    for i in range(3):
        (backup_dir / f"backup_2024-01-0{i+1}_00-00-00.tar.gz").write_bytes(b"x")

    svc._rotate_local(keep=7)
    assert len(list(backup_dir.glob("backup_*.tar.gz"))) == 3


# ── run_backup (end-to-end, no S3) ──────────────────────────────────────────

def test_run_backup_ok(tmp_dirs, monkeypatch):
    import app.services.backup_service as svc
    monkeypatch.setattr(svc, "S3_BUCKET", "")   # disable S3
    monkeypatch.setattr(svc, "KEEP_LOCAL", 7)

    result = svc.run_backup()
    assert result == "ok"
    assert svc._last_backup_status == "ok"
    assert svc._last_backup_at is not None
    _, backup_dir = tmp_dirs
    assert len(list(backup_dir.glob("backup_*.tar.gz"))) == 1


def test_run_backup_status_on_error(tmp_dirs, monkeypatch):
    import app.services.backup_service as svc

    def bad_create():
        raise RuntimeError("disk full")

    monkeypatch.setattr(svc, "_create_archive", bad_create)
    result = svc.run_backup()
    assert result.startswith("error:")
    assert "disk full" in svc._last_backup_status
