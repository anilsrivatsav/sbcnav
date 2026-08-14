# Changelog

## 0.9.2+19 - 2026-08-04

- Classifies units without a licensee and contract period as available for allotment.
- Displays availability remarks instead of contract validity and payment information.
- Excludes tender and EMD receipts from contract earnings while retaining them for audit.
- Adds optional Remarks-column support to future catering-sheet synchronizations.

## 0.9.1+18 - 2026-08-03

- Removed source and synchronization metadata from complete station records.
- Renamed the detailed amenity group to Passenger amenity details.
- Retained every operational station and passenger amenity field.

## 0.9.0+17 - 2026-08-03

- Rebuilt Station 360 as focused Overview, Amenities, Contracts, Works, and Inspection workspaces.
- Added compact module navigation with consistent selected-state pills and record counts.
- Added a concise station overview with direct access to each available linked dataset.
- Preserved every source field through a complete station record bottom sheet.
- Kept normalized FOB data when no authoritative FOB access record is available.
- Reduced the station hero height and added animated workspace transitions.

## 0.8.2+16 - 2026-08-03

- Added a Settings action to refresh catering units and earnings from the configured Google Sheet.
- Refreshes PostgreSQL first and then replaces the device's offline station snapshot.
- Shows unit, receipt, and duplicate-removal results with online and server error handling.
- Records the last successful catering refresh time on the device.

## 0.8.1+15 - 2026-08-03

- Reorganized Station 360 so platforms, FOB details, amenity categories, and norms live under Passenger Amenities.
- Replaced oversized amenity cards with a compact horizontal category summary and full-detail bottom sheets.
- Removed the duplicate normalized FOB tile while preserving the authoritative FOB access record.
- Replaced inline norm expansion with grouped, tabbed norm details that retain every source row.
- Moved Action Centre to the end of Station 360 and made action and detail surfaces fully opaque.

## 0.8.0+14 - 2026-08-03

- Added a Station 360 action centre for deficiencies, inspection history, contract alerts, and sync state.
- Added deficiency ownership, target dates, overdue visibility, and full corrective-action status tracking.
- Added structured contract alert fields with 1, 5, 10, 30, and 50-day expiry bands.
- Added resilient per-record synchronization, failed-record retry, queue diagnostics, and sync history.
- Preserved all existing offline inspections and cached station data through a versioned database migration.

## 0.7.6+13 - 2026-08-03

- Replaced oversized contract-validity cards with compact, station-aware rows.
- Added structured unit or contract codes, contract names, station codes, and validity dates to reports and PDF exports.
- Added a green `50+` validity segment for contracts with more than 50 days remaining.
- Kept multi-station contracts distinct per linked station in validity reports.

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
## 0.9.3+20

- Added station-wise lift, ramp, and escalator details from the combined accessibility sheet.
- Added a Passenger Amenities card with a readable detail bottom sheet in Station 360.
## 0.9.4+21

- Completed inspections now generate and share a full PDF report.
- Reports are retained locally under the inspection reports folder before sharing.
- Submitted inspections have a Share PDF action for later reuse.
## 0.9.5+22

- Moved lift, ramp and escalator details into the FOB detail bottom sheet.
- Empty and `NA` accessibility values are omitted.
## 0.9.6+23

- Station details now refresh from the API when opened, while preserving offline cache fallback.
- Newly imported FOB accessibility details become visible without clearing app data.
