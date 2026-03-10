#!/bin/sh
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --log-level info
