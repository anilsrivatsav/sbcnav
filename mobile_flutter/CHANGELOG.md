# Changelog

## 0.7.5+12 - 2026-08-03

- Standardized Catering, MPS, and commercial contract detail sheets.
- Added validity dates, remaining days, renewal status, payment totals, paid-through date, and receipt history.
- Added consistent contract risk colours in Station 360 and Reports: red within 10 days, amber within 30 days, green active, grey missing dates.
- Recovered missing catering licensee names from linked earnings where available.
- Added fixed-screen contract-expiry reporting with native PDF export.

## 0.7.4+11 - 2026-08-03

- Added contract-validity report chips for the next 30, 10, and 5 days.
- Sorted expiring contracts by nearest validity end date.
- Reworked the mobile validity report into a fixed, paginated single-screen layout.
- Added native PDF export for all contracts in the selected validity window.
- Added matching contract-expiry reporting to the Next.js dashboard.

## 0.7.0+7 - 2026-07-31

- Added explicit ABSS station flags for the 19 designated stations.
- Added Station Redevelopment flags for YPR and BNC.
- Added program badges to the Stations list and Station 360 view.
- Added station-linked FOB access details for stairs, ramps, and lifts.
- Added collapsible passenger amenity norms grouped by MEA, Recommended, Desirable, and Divyangjan.
- Refined station contracts, sanctioned works, platform, and selected-state presentation.
## 0.7.1+8 - 2026-08-01
- Added working profile and settings actions.
- Added explicit PostgreSQL data refresh from the home and settings surfaces.
- Refreshes the mobile cache when the bundled station data version changes.
- Built the release APK against the deployed API host for physical devices.
## 0.7.2+9 - 2026-08-01
- Added offline contract expiry notifications and notification centre.
- Added contract validity dates and remaining-day indicators.
- Added commercial contract payment history to station detail responses.
- Clarified Findings and PostgreSQL refresh actions.
## 0.7.3+10

- Added a dedicated offline Reports workspace with overview, contract alerts, and findings tabs.
- Added consistent contract validity fields to station detail responses.
- Removed stale contract expiry notifications after refreshed station data.
- Refreshed the home profile and notification counts after sheets close.
