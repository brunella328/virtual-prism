"""
Backup Service
--------------
Creates tar.gz snapshots of data/ and optionally uploads to an
S3-compatible object store (AWS S3, Cloudflare R2, Backblaze B2).

Environment variables
---------------------
BACKUP_S3_BUCKET        bucket name — set this to enable S3 upload
BACKUP_S3_PREFIX        key prefix inside the bucket (default: "virtual-prism/")
AWS_ACCESS_KEY_ID       access key
AWS_SECRET_ACCESS_KEY   secret key
AWS_ENDPOINT_URL        endpoint override for non-AWS (R2: https://<id>.r2.cloudflarestorage.com)
BACKUP_INTERVAL_HOURS   how often the scheduler runs (default: 6)
BACKUP_KEEP_LOCAL       how many local archives to keep (default: 7)
"""

import asyncio
import logging
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR   = Path(__file__).parent.parent.parent / "data"
BACKUP_DIR = Path(__file__).parent.parent.parent / "backups"

INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "6"))
KEEP_LOCAL     = int(os.getenv("BACKUP_KEEP_LOCAL", "7"))

S3_BUCKET = os.getenv("BACKUP_S3_BUCKET", "")
S3_PREFIX  = os.getenv("BACKUP_S3_PREFIX", "virtual-prism/")

# ── Module-level state (read by /health) ────────────────────────────────────
_last_backup_at: Optional[str] = None
_last_backup_status: str = "never"


def get_status() -> dict:
    return {
        "last_backup_at":  _last_backup_at,
        "status":          _last_backup_status,
        "interval_hours":  INTERVAL_HOURS,
        "s3_enabled":      bool(S3_BUCKET),
    }


# ── Core logic ───────────────────────────────────────────────────────────────

def _create_archive() -> Path:
    """Tar-gz the data directory and return the archive path."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    dest = BACKUP_DIR / f"backup_{ts}.tar.gz"
    with tarfile.open(dest, "w:gz") as tar:
        if DATA_DIR.exists():
            tar.add(DATA_DIR, arcname="data")
    kb = dest.stat().st_size / 1024
    logger.info("Backup archive created: %s (%.1f KB)", dest.name, kb)
    return dest


def _rotate_local(keep: int) -> None:
    """Delete oldest archives, keeping the `keep` most recent."""
    archives = sorted(BACKUP_DIR.glob("backup_*.tar.gz"))
    for old in archives[:-keep] if len(archives) > keep else []:
        old.unlink()
        logger.info("Removed old local backup: %s", old.name)


def _upload_s3(archive_path: Path) -> None:
    """Upload archive to configured S3-compatible bucket."""
    import boto3
    endpoint = os.getenv("AWS_ENDPOINT_URL") or None
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    key = f"{S3_PREFIX.rstrip('/')}/{archive_path.name}"
    client.upload_file(str(archive_path), S3_BUCKET, key)
    logger.info("Backup uploaded → s3://%s/%s", S3_BUCKET, key)


def run_backup() -> str:
    """
    Execute one full backup cycle.
    Returns "ok" on success, "error: <msg>" on failure.
    """
    global _last_backup_at, _last_backup_status
    try:
        archive = _create_archive()
        if S3_BUCKET:
            _upload_s3(archive)
        _rotate_local(KEEP_LOCAL)
        _last_backup_at = datetime.now(timezone.utc).isoformat()
        _last_backup_status = "ok"
        return "ok"
    except Exception as exc:
        logger.error("Backup failed: %s", exc)
        _last_backup_status = f"error: {exc}"
        return f"error: {exc}"


# ── Background scheduler ─────────────────────────────────────────────────────

async def backup_scheduler() -> None:
    """
    Long-running asyncio task: sleep INTERVAL_HOURS, then back up.
    Attach to the FastAPI lifespan so it is cancelled on shutdown.
    """
    interval = INTERVAL_HOURS * 3600
    logger.info(
        "Backup scheduler started — interval=%dh, s3=%s",
        INTERVAL_HOURS, bool(S3_BUCKET),
    )
    while True:
        await asyncio.sleep(interval)
        logger.info("Running scheduled backup…")
        run_backup()
