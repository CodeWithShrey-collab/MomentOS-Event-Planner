#!/bin/sh
set -eu

cd /app

# Fail closed on invalid or unreachable production dependencies before changing
# the database. The app factory validates production settings without logging
# secret values.
python -m flask --app backend.wsgi:app production-preflight

# Run only versioned Alembic migrations. Do not replace this with create_all().
python -m flask --app backend.wsgi:app db upgrade

# Free service: one conservative worker, a small thread pool, no background jobs.
exec gunicorn --chdir /app/backend wsgi:app \
  --bind "0.0.0.0:${PORT:-10000}" \
  --workers 1 \
  --worker-class gthread \
  --threads 2 \
  --timeout 90 \
  --graceful-timeout 30 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --error-logfile -
