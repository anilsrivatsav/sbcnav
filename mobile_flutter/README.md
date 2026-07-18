# Rail Dashboard Mobile

Flutter mobile client for the existing Railway Dashboard FastAPI backend.

This app is intentionally read-focused and mobile-first. It is not an admin CRUD console. It gives quick access to:

- Dashboard KPIs
- Station search
- Station detail bottom sheet
- Linked contracts and earnings
- Passenger amenities
- Platform extension, ramp, and lift status
- Works and reports

## API URL

The default backend URL is:

```sh
http://10.0.2.2:8000
```

Use this for Android emulator because `10.0.2.2` maps to the host machine.

For Flutter web or Windows desktop:

```sh
flutter run --dart-define API_BASE_URL=http://127.0.0.1:8000
```

For a physical phone on the same Wi-Fi network, replace the URL with your computer LAN IP:

```sh
flutter run --dart-define API_BASE_URL=http://192.168.1.10:8000
```

The FastAPI backend must be running and reachable from the device.

## First-Time Setup

If this folder was copied without platform folders, generate them once:

```sh
cd mobile_flutter
flutter create .
flutter pub get
```

Then run:

```sh
flutter run --dart-define API_BASE_URL=http://10.0.2.2:8000
```

## Backend Endpoints Used

- `GET /api/stats`
- `GET /api/reports`
- `GET /api/passenger-amenities/reports`
- `GET /api/stations`
- `GET /api/stations/{station_code}/detail`
- `GET /api/units`
- `GET /api/earnings`
- `GET /api/works`
- `GET /api/passenger-amenities`

## Notes

- No backend changes are required for this mobile layer.
- No web frontend changes are required.
- This client uses the existing response envelope:

```json
{
  "success": true,
  "message": "",
  "data": {}
}
```
