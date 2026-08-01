# Portable Railway Dashboard

The portable runtime uses Docker Compose to run PostgreSQL, FastAPI, and Next.js
without installing those runtimes separately on each computer.

## Deployment modes

### Central server (recommended)

Run the complete stack on one always-available server or office computer. All web
and mobile clients connect to its FastAPI URL. This provides one authoritative
PostgreSQL database.

```text
Web browsers ─┐
Flutter apps ─┼─> FastAPI ─> PostgreSQL
Other PCs ────┘
```

Flutter remains offline-first through its local SQLite database and synchronizes
with this central API when a connection is available.

### Standalone computer

Run the complete stack independently on a laptop or demonstration computer. Each
computer receives its own PostgreSQL container and persistent Docker volume.
Standalone databases do not synchronize with one another.

### Frontend-only client

Run `client-up` to host only the Next.js frontend and point it to a central API.
Set `CENTRAL_API_URL` in `.env.docker` before building the client.

## Requirements

- Windows 10/11, Linux, or macOS
- Docker Desktop, or Docker Engine with Compose v2
- At least 6 GB free disk space
- At least 4 GB available memory

Windows can install Docker Desktop with:

```powershell
railctl.cmd install-docker
```

Docker Desktop may require WSL 2, hardware virtualization, and a Windows restart.

## First start

On Windows:

```powershell
railctl.cmd up
```

On Linux or macOS:

```sh
chmod +x scripts/railctl.sh
./scripts/railctl.sh up
```

The first command creates `.env.docker` with a random PostgreSQL password, builds
the images, runs all Alembic migrations, and waits for both web services.

- Dashboard: `http://localhost:3000`
- FastAPI documentation: `http://localhost:8000/docs`
- PostgreSQL host port: `5433`

PostgreSQL uses port 5433 on the host to avoid conflicting with a locally
installed PostgreSQL service. Containers use port 5432 internally.

## Current data on a new machine

If `backups/bootstrap.dump` exists before the first `up`, PostgreSQL restores it
while creating the Docker volume. The restore happens only for a new, empty
volume.

To start without existing data, omit `bootstrap.dump`; Alembic creates an empty
production schema.

Do not commit database dumps to a public repository. They can contain operational
and personal information.

## Commands

| Command | Purpose |
| --- | --- |
| `railctl.cmd up` | Build and start the complete stack |
| `railctl.cmd down` | Stop containers without deleting database data |
| `railctl.cmd restart` | Restart the stack |
| `railctl.cmd status` | Show container and health status |
| `railctl.cmd logs` | Follow combined service logs |
| `railctl.cmd open` | Open the local dashboard |
| `railctl.cmd backup` | Create a timestamped PostgreSQL dump |
| `railctl.cmd restore -Backup backups\file.dump` | Restore a selected dump |
| `railctl.cmd migrate` | Apply pending Alembic migrations |
| `railctl.cmd rebuild` | Pull base images, rebuild, and restart |
| `railctl.cmd client-up` | Run frontend only against `CENTRAL_API_URL` |
| `railctl.cmd client-down` | Stop the frontend-only client |

Linux and macOS use the same action names with `./scripts/railctl.sh`.

`down` deliberately preserves the PostgreSQL volume. No command in the controller
deletes the volume automatically.

## Network configuration

For access from other computers, replace `localhost` in `.env.docker`:

```dotenv
PUBLIC_API_URL=http://192.168.1.50:8000
CORS_ORIGINS=http://192.168.1.50:3000,http://localhost:3000
```

Run `railctl.cmd rebuild` after changing `PUBLIC_API_URL`, because Next.js embeds
that value during its production build.

For an internet deployment, use HTTPS through a reverse proxy and set:

```dotenv
PUBLIC_API_URL=https://api.example.com
CORS_ORIGINS=https://dashboard.example.com
```

Do not expose PostgreSQL port 5433 to the public internet.

## Mobile builds

Local ARM64 build:

```powershell
mobile_flutter\build_apk.ps1 -Architecture arm64 -ApiBaseUrl https://api.example.com
```

GitHub Actions workflow `.github/workflows/build-mobile-apk.yml` builds ARM64 and
universal APKs. Run it manually and provide the deployed FastAPI URL. Build
artifacts remain downloadable for 30 days.

An APK built with `http://10.0.2.2:8000` targets the Android emulator. A physical
phone must use a reachable LAN address or HTTPS production API.

## Backup and recovery

Create backups regularly:

```powershell
railctl.cmd backup
```

Restore:

```powershell
railctl.cmd restore -Backup backups\rail_dashboard_YYYYMMDD_HHMMSS.dump
```

The restore temporarily stops FastAPI, restores PostgreSQL, reapplies migrations,
and starts FastAPI again.

Copy `backups`, `.env.docker`, and the project source to recover on another
computer. Keep `.env.docker` and database dumps private.
