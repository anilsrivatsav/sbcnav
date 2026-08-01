#!/bin/sh
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "Applying database migrations..."
alembic upgrade head

workers="${BACKEND_WORKERS:-2}"
log_level="${LOG_LEVEL:-info}"

exec gunicorn \
  --bind 0.0.0.0:8000 \
  --workers "$workers" \
  --worker-class uvicorn.workers.UvicornWorker \
  --access-logfile - \
  --error-logfile - \
  --log-level "$log_level" \
  app:app
