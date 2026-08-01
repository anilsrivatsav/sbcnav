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
