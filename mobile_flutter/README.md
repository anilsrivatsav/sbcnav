# Rail Inspect

Offline-first Flutter application for railway commercial inspectors and
officers. The app is a field inspection client for the existing FastAPI and
PostgreSQL Railway Dashboard.

## Current Vertical Slice

- Ship a bundled PostgreSQL snapshot for immediate offline use.
- Refresh all Station 360 details through a paginated offline download.
- Search stations without a network.
- Open Station 360 offline with platforms, amenities, units, earnings,
  contracts, and sanctioned works.
- Start scheduled, surprise, or follow-up inspections.
- Complete versioned Pass / Fail / N/A checklists.
- Create findings when an item fails.
- Capture photo evidence and contextual inspection notes.
- Save every edit to SQLite before attempting network access.
- Queue idempotent operations for later upload.
- Pull server changes using a monotonic cursor.
- Display sync status and pending operation count.

The initial general station template covers passenger amenities, cleanliness,
Divyangjan compliance, commercial records and returns, admitted/disputed
debits, and saleable items. More specialist templates can be added by the
backend without releasing a new app.

## Local API

Android Emulator:

```powershell
flutter run --dart-define API_BASE_URL=http://10.0.2.2:8000
```

Physical Android device on the same network:

```powershell
flutter run --dart-define API_BASE_URL=http://YOUR_COMPUTER_LAN_IP:8000
```

Production:

```powershell
flutter build apk --release --dart-define API_BASE_URL=https://YOUR_API_HOST
```

## Mobile API

- `GET /api/mobile/v1/bootstrap`
- `GET /api/mobile/v1/templates`
- `GET /api/mobile/v1/stations/{station_code}/360`
- `GET /api/mobile/v1/offline/station-details`
- `GET /api/mobile/v1/inspections`
- `GET /api/mobile/v1/inspections/{inspection_id}`
- `POST /api/mobile/v1/inspections`
- `POST /api/mobile/v1/sync/push`
- `GET /api/mobile/v1/sync/pull`

Run PostgreSQL migrations through `0013_inspection_evidence_notes` before
using the app.

## Source Layout

```text
lib/
  core/                 configuration and visual theme
  data/local/           SQLite offline database and queue
  data/remote/          FastAPI client
  data/sync/            incremental synchronization
  features/home/        Today summary
  features/stations/    station search and Station 360
  features/inspections/ inspection setup and checklist
  features/findings/    action register
  features/sync/        download/upload controls
  shared/               reusable mobile widgets
```
