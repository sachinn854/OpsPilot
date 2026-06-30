#!/bin/sh
set -e

echo "Initializing database (best-effort)..."
python -c "
import asyncio, sys
from backend.db.session import init_db
async def run():
    try:
        await init_db()
        print('DB initialized.')
    except Exception as e:
        print(f'DB init skipped: {e}', file=sys.stderr)
asyncio.run(run())
" || echo "DB init failed — uvicorn will retry on first request."

echo "Starting uvicorn..."
exec uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-1}" \
  --log-level "${LOG_LEVEL:-info}"
