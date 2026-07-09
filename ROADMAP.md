# Railway Dashboard Migration Roadmap

## Objective

Convert the current Sheets-backed prototype into a production-ready Railway Dashboard with a stable database layer, authentication, stronger analytics, deployable infrastructure, and AI-assisted workflows.

This roadmap is ordered by dependency. Each phase assumes the previous phase is complete or at least stable enough to build on.

---

## Phase 1: Database Migration

### Goal

Replace the current ad hoc SQLite rebuild pattern with a production-grade persistence layer and a repeatable schema migration strategy.

### Scope

- Define a durable relational schema for stations, catering units, earnings, sanctioned works, and derived link tables.
- Introduce proper migrations instead of drop-and-recreate sync behavior.
- Add indexes for station code, unit number, station mappings, and lookup-heavy columns.
- Separate raw ingested rows from cleaned normalized tables.
- Introduce timestamps, sync audit fields, and source metadata.
- Decide whether to keep SQLite for single-instance deployments or move to PostgreSQL for production.

### Recommended work

- Extract schema definitions into migration files.
- Introduce repository/data-access layer.
- Add ETL staging tables for Google Sheets imports.
- Add validation around column drift and missing headers.
- Store sync history and source tab version metadata.

### Estimated file impact

Likely changed files:
- `backend/app.py`
- `backend/requirements.txt`
- `backend/rail_dashboard.db` or replacement DB bootstrap path
- new migration files under something like `backend/migrations/`
- new schema modules under something like `backend/app/db/`
- new loader/parser modules under something like `backend/app/services/`

Estimated files changed: 6 to 12

---

## Phase 2: Authentication

### Goal

Add secure access control so the dashboard is usable by authenticated users only, with role-based permissions for administrators and viewers.

### Scope

- Add login/logout flow.
- Protect all API endpoints behind authentication.
- Introduce role-based access control.
- Support session-based auth or JWT-based auth depending on deployment model.
- Create an admin role for sync control and schema management.
- Restrict sync operations to privileged users.

### Recommended work

- Add backend auth middleware and token/session handling.
- Add user model and password hashing.
- Add login UI and auth guards in the frontend.
- Add route protection for the dashboard shell.
- Add server-side permission checks for sync and administrative endpoints.

### Estimated file impact

Likely changed files:
- `backend/app.py`
- new auth modules under `backend/app/auth.py` or similar
- new user/role model modules
- `frontend/app/page.jsx`
- new login page/component files
- `frontend/app/layout.jsx`
- frontend API client helpers

Estimated files changed: 6 to 14

---

## Phase 3: Dashboard Improvements

### Goal

Make the dashboard operationally useful, faster to scan, and less dependent on client-side inference.

### Scope

- Move key rollups to backend API responses.
- Add station-level revenue, active units, pending receipts, and latest fee status.
- Add richer station/unit/work detail drawers.
- Improve filter semantics and make them consistent across views.
- Add saved filters, better search, and empty states.
- Add responsive layouts for mobile and desktop.
- Reduce client-side data shaping.

### Recommended work

- Add backend aggregation endpoints or summary objects.
- Add reusable filter and table components.
- Introduce station dashboard cards with operational KPIs.
- Improve linking between stations, units, earnings, and works.
- Add pagination or virtualized lists for larger datasets.

### Estimated file impact

Likely changed files:
- `frontend/app/page.jsx`
- `frontend/app/globals.css`
- new UI components under `frontend/components/`
- backend endpoint updates in `backend/app.py`
- backend query/helper modules

Estimated files changed: 4 to 10

---

## Phase 4: Analytics

### Goal

Turn the dashboard into an analytics tool that can answer operational questions without manual spreadsheet work.

### Scope

- Station-wise revenue summaries.
- Unit-wise fee collection and pending detection.
- Monthly trend charts for receipts and station earnings.
- Work pipeline summaries by station, division, section, and status.
- Category, division, and section trend breakdowns.
- Exportable reports.
- Cross-module KPIs for stations, units, earnings, and works.

### Recommended work

- Add analytics tables or materialized summary tables.
- Add API endpoints for chart-ready data.
- Add date-bucketed aggregation logic.
- Add report export support.
- Introduce chart components in the frontend.

### Estimated file impact

Likely changed files:
- `backend/app.py`
- analytics/query modules
- summary/aggregation modules
- `frontend/app/page.jsx`
- new chart components
- report export helpers

Estimated files changed: 5 to 12

---

## Phase 5: Deployment

### Goal

Package the app for reliable deployment with clear environment configuration, repeatable startup, and operational observability.

### Scope

- Move to production database hosting if required.
- Define environment variables for API base URL, database URL, auth keys, and sync settings.
- Add deployment manifests and scripts.
- Add logging and error handling suitable for production.
- Add health checks and readiness checks.
- Add CORS and security headers appropriate for deployed environments.

### Recommended work

- Split frontend and backend deployment concerns.
- Add Dockerfiles or equivalent build definitions.
- Add process manager or platform-specific startup config.
- Add static asset and API routing rules.
- Add structured logs and request tracing.

### Estimated file impact

Likely changed files:
- `backend/start.ps1`
- `frontend/start.ps1`
- `backend/requirements.txt`
- `frontend/package.json`
- deployment files such as `Dockerfile`, `docker-compose.yml`, `railway.toml`, or platform config files
- environment example files such as `.env.example`

Estimated files changed: 6 to 15

---

## Phase 6: AI Integration

### Goal

Add AI assistance for operational analysis, anomaly detection, and natural-language querying across stations, units, earnings, and works.

### Scope

- Natural-language search over the railway dataset.
- AI-generated station summaries.
- Exception detection for missing fees, inactive units, or unusual work patterns.
- Conversational analytics and query generation.
- Optional assistant sidebar for dashboard guidance.
- AI summaries that cite backend data instead of hallucinating from raw prompts.

### Recommended work

- Add backend AI orchestration layer.
- Build prompt templates grounded in database query results.
- Add guardrails for tool use and response formatting.
- Add frontend chat/assistant UI.
- Add moderation or safety constraints for generated content.

### Estimated file impact

Likely changed files:
- `backend/app.py`
- new AI service modules
- new prompt/template files
- `frontend/app/page.jsx`
- new assistant panel components
- new API client utilities

Estimated files changed: 5 to 12

---

## Cross-Cutting Work

These tasks should run across multiple phases rather than waiting for a single phase:

- add automated tests for parsing, linking, and API responses
- add sample fixtures for Google Sheets exports
- add logging and error tracking
- add documentation for schema and endpoints
- add data validation for sheet column drift
- add rate limiting or sync locking if sync can be triggered repeatedly

## Suggested Execution Order

1. Database migration
2. Authentication
3. Dashboard improvements
4. Analytics
5. Deployment
6. AI integration

## Risk Notes

- The current system relies on Google Sheets column names staying stable.
- The current sync model drops and recreates tables, which is not production-safe.
- Authentication should be introduced before public deployment.
- Analytics and AI both depend on stable normalized data and predictable summary endpoints.

## Summary

This roadmap keeps the existing product direction intact, but changes the architecture from a prototype dashboard into a maintained application with controlled data flow, security, observability, and extensibility.
