# Production deployment

SBCNAV uses the existing Vercel frontend, Render API for its general views, and the Oracle FastAPI service for Deskflow and eAuction:

```text
Vercel Next.js ── general API ──> Render FastAPI
                └─ /api/deskflow ──> Oracle FastAPI ──> PostgreSQL and Google Sheets
                                               ↑
                                    Windows Deskflow companion
```

## Vercel

Build the `frontend` directory with `npm run build`. Keep `NEXT_PUBLIC_API_URL` pointed at the existing general API. The Next.js `/api/deskflow` route uses `DESKFLOW_API_URL`, or defaults to `https://sbcnav.137-23-58-53.sslip.io`. Deploying the frontend exposes `/eauction` and the icon links in SBCNAV. The browser never needs a Google key.

## Oracle API

Build `backend/Dockerfile` and restart `deploy/oracle/sbcnav-backend.service` with the new image. `backend/docker-entrypoint.sh` applies Alembic migrations before serving requests; this release adds `0034_auction_schedule` for shared holidays and Deskflow lot links. Keep the existing PostgreSQL connection and `MCDO_ADMIN_TOKEN` (at least 32 characters). Set `DESKFLOW_PASSWORD` in `/opt/sbcnav/backend.env` if the agreed password changes.

The Oracle service account is configured server side with `MCDO_GOOGLE_CREDENTIALS`. Share the [Auction Schedule workbook](https://docs.google.com/spreadsheets/d/1n_aQpueOSE8OYl5y5KW3_NuYFg7Knlw3BYslllEp1zk/edit?gid=1939091527) with the service account's `client_email` as an Editor. If the environment variable points to a JSON file inside the container, mount that file read only in the systemd Docker command. Do not put service account JSON in Git or the browser.

The scheduler reads all monthly tabs, creates the auction month's tab if needed, calculates category schedule IDs and the next global catalogue number, and writes Date, Time, Category, IDs, Status, and Sync ID in columns A:G. A successful schedule is green; cancelled and withdrawn rows are red in both the app and the Sheet. Writes carry a Sync ID and are checked before append, so retries do not create duplicate rows. Holidays are stored in PostgreSQL and must be populated with the official list used for scheduling.

## Verification

After both services deploy, unlock `/eauction` and check that existing monthly rows load. Add a holiday and confirm another browser sees it. Add a test auction only when an actual schedule is required; verify the same Sync ID appears once in the monthly Sheet tab. Cancel or withdraw only a row that should genuinely change status. Open Deskflow, collect IREPS lots on the Windows companion, and verify its selected lot links to the scheduled auction. Running contracts use LAR as RP, completed contracts use LAR plus 10%, and foreclosed contracts use LAR; other statuses retain the existing fixation rules.

Do not commit `.env` files, database passwords, service account keys, or source workbooks to GitHub.
