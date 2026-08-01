# Rail Dashboard Control

Launch `Rail Dashboard Control.cmd` from the project root. The control panel runs
locally on Windows and does not require Codex.

## Main actions

- **Start all** starts PostgreSQL, FastAPI, and Next.js, then waits for readiness.
- **Stop app** stops FastAPI and Next.js but leaves PostgreSQL running.
- **Stop all + DB** stops FastAPI, Next.js, and PostgreSQL.
- **Open dashboard** ensures all services are ready and opens the browser.
- **Open API docs** ensures PostgreSQL and FastAPI are ready and opens Swagger.
- **Build ARM64 APK** builds the smaller ARM64 release APK in the background.
- **Build universal APK** builds the larger universal release APK.
- **Open logs** opens `.runtime`, where service and build logs are stored.
- **Open APK folder** opens `mobile_flutter/build/app/outputs/flutter-apk`.

PostgreSQL service actions may display a Windows administrator permission prompt.
The controller uses the project-local portable Node.js runtime when present. If
that runtime is removed, use **Install Node.js LTS** and reopen the control panel.

For a cross-platform Docker runtime, use `railctl.cmd` on Windows or
`scripts/railctl.sh` on Linux/macOS. See `PORTABLE_SETUP.md`.

## Command-line use

The same controller supports:

```powershell
powershell -ExecutionPolicy Bypass -File tools\RailDashboardControl.ps1 -Action status
powershell -ExecutionPolicy Bypass -File tools\RailDashboardControl.ps1 -Action start-all
powershell -ExecutionPolicy Bypass -File tools\RailDashboardControl.ps1 -Action stop-app
powershell -ExecutionPolicy Bypass -File tools\RailDashboardControl.ps1 -Action stop-all
powershell -ExecutionPolicy Bypass -File tools\RailDashboardControl.ps1 -Action build-arm64
```
