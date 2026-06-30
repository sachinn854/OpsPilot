#!/bin/sh
set -e

echo "Running Alembic migrations..."
cd /app
python -m alembic -c backend/alembic.ini upgrade head 2>/dev/null || \
  python -c "
import asyncio
from backend.db.session import init_db
asyncio.run(init_db())
print('DB tables created via SQLAlchemy (no alembic.ini found).')
"

echo "Starting uvicorn..."
exec uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-1}" \
  --log-level "${LOG_LEVEL:-info}"
