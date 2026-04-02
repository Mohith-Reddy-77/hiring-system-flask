#!/usr/bin/env bash
set -euo pipefail

echo "Entry point: starting up"

# Optionally skip migrations by setting SKIP_MIGRATIONS=1
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  echo "Running Alembic migrations..."
  # If alembic is not available or migrations fail, we continue to start the app
  if command -v alembic >/dev/null 2>&1; then
    alembic upgrade head || echo "alembic upgrade head failed; continuing to start the app"
  else
    echo "alembic not found; skipping migrations"
  fi
else
  echo "SKIP_MIGRATIONS=1 set; skipping migrations"
fi

echo "Starting Gunicorn"
exec gunicorn "app:app" --workers 2 --bind 0.0.0.0:${PORT:-5000}
