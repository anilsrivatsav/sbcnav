#!/bin/sh
set -eu

bootstrap="/backups/bootstrap.dump"
if [ ! -s "$bootstrap" ]; then
  echo "No bootstrap.dump found; starting with an empty migrated database."
  exit 0
fi

echo "Restoring initial data from /backups/bootstrap.dump..."
pg_restore \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  "$bootstrap"
echo "Initial database restore completed."
