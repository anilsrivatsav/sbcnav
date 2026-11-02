#!/bin/bash
# Run as root from a directory containing backend/ from the reviewed source.
set -euo pipefail
umask 077
cd "$(dirname "$0")"
work=$(pwd)
test -f backend/mcdo_monthly_router.py
test -f backend/mcdo/templates/sbc_mcdo.xlsx
unit=/etc/systemd/system/sbcnav-backend.service
test -f "$unit"
old_image=$(docker inspect sbcnav-backend --format '{{.Config.Image}}')
old_id=$(docker inspect sbcnav-backend --format '{{.Image}}')
new_image=sbcnav-backend:mcdo-monthly-20261102
docker tag "$old_id" sbcnav-backend:before-mcdo-monthly-20261102
cp -p "$unit" "$work/backend.service.before"
if docker inspect sbcnav-postgres >/dev/null 2>&1; then
    docker exec sbcnav-postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$work/database-before.dump"
    test -s "$work/database-before.dump"
fi
cat > Dockerfile <<'DOCKER'
FROM sbcnav-backend:before-mcdo-monthly-20261102
COPY backend/app.py backend/models.py backend/mcdo_router.py backend/mcdo_monthly_router.py backend/test_mcdo_monthly.py /app/
COPY backend/mcdo/monthly.py /app/mcdo/monthly.py
COPY backend/mcdo/templates/sbc_mcdo.xlsx /app/mcdo/templates/sbc_mcdo.xlsx
COPY backend/alembic/versions/0035_mcdo_monthly.py /app/alembic/versions/0035_mcdo_monthly.py
DOCKER
docker build --network=none -t "$new_image" .
docker run --rm --memory=512m --entrypoint python -e DATABASE_URL=sqlite:///:memory: "$new_image" -m unittest test_mcdo_monthly test_mcdo test_mcdo_deadlines test_publicity_earnings -q
changed=0
rollback() {
    result=$?
    if [ "$result" -ne 0 ] && [ "$changed" -eq 1 ]; then
        cp -p "$work/backend.service.before" "$unit"
        systemctl daemon-reload
        systemctl restart sbcnav-backend
        echo 'Previous backend image restored. Additive monthly tables, if created, are retained.'
    fi
}
trap rollback EXIT
python3 - "$unit" "$old_image" "$new_image" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]);content=p.read_text()
assert content.count(sys.argv[2])==1,'Unexpected backend image reference; service unchanged.'
p.write_text(content.replace(sys.argv[2],sys.argv[3]))
PY
changed=1
systemctl daemon-reload
systemctl restart sbcnav-backend
for attempt in $(seq 1 30); do
    if curl --fail --silent --max-time 3 http://127.0.0.1:8000/api/mcdo/monthly/2026-10 > "$work/monthly-health.json"; then
        python3 - "$work/monthly-health.json" <<'PY'
import json,sys
report=json.load(open(sys.argv[1]))
assert report['success'] and report['data']['period']=='2026-10'
print('Monthly MCDO API verified:',report['data']['status'])
PY
        touch "$work/deployment-complete"
        systemctl is-active sbcnav-backend
        exit 0
    fi
    sleep 2
done
echo 'Monthly endpoint did not become healthy; restoring previous service.' >&2
exit 1
