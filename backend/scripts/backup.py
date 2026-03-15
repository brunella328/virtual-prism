#!/usr/bin/env python3
"""
Standalone backup script — run manually or via external cron.

Usage:
    python scripts/backup.py

Required env vars (same as backup_service.py):
    BACKUP_S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    AWS_ENDPOINT_URL (optional, for Cloudflare R2 / Backblaze B2)

Exit codes:
    0 — success
    1 — error
"""
import os
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from app.services.backup_service import run_backup

if __name__ == "__main__":
    result = run_backup()
    if result == "ok":
        print("Backup completed successfully.")
        sys.exit(0)
    else:
        print(f"Backup failed: {result}", file=sys.stderr)
        sys.exit(1)
