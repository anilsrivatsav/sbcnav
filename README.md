# Railway Dashboard

FastAPI, Next.js, PostgreSQL, and Flutter applications for railway station,
commercial contract, catering, earnings, passenger amenity, sanctioned work, and
offline inspection workflows.

## Portable Docker runtime

The recommended runtime needs only Docker Desktop:

```powershell
railctl.cmd up
```

This builds and starts PostgreSQL, FastAPI, and Next.js, applies Alembic
migrations, restores `backups/bootstrap.dump` on the first database creation, and
waits for service health checks.

See [PORTABLE_SETUP.md](PORTABLE_SETUP.md) for standalone, central-server,
frontend-only client, backup, restore, networking, and APK build instructions.

## Existing Windows runtime

Double-click `Rail Dashboard Control.cmd` to manage the locally installed
PostgreSQL service, FastAPI, Next.js, logs, and Flutter APK builds without Docker
or Codex.

## Catering data refresh

The catering refresh reads only `UNITS BASE DATA` and `EARNINGS BASE DATA` from
the spreadsheet configured by `CATERING_SPREADSHEET_ID`. In the Next.js
Contracts workspace, use **Refresh catering data** to validate, deduplicate,
reconcile, and commit the source in one PostgreSQL transaction.

- `POST /api/catering/sync?dry_run=true` validates without writing.
- `POST /api/catering/sync` updates PostgreSQL.
- `GET /api/catering/sync-history` returns recent sync outcomes.
