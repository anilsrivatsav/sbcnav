# Production deployment

This project keeps the existing deployment split:

```text
Vercel Next.js → Render FastAPI → Render PostgreSQL
```

## Vercel

Set the project root directory to `frontend` and add this production environment variable:

```text
NEXT_PUBLIC_API_URL=https://sbcnav.onrender.com
```

The eAuction scheduler is an internal page at `/eauction`, opened by the calendar icon in SBCNAV. Its Google Sheets route runs in Next.js on Vercel, so the Python API and Oracle server need no scheduler changes.

For the **Send to Google Sheet** button, also set these Vercel environment variables:

```text
GOOGLE_SERVICE_ACCOUNT_JSON=<complete Google service-account JSON>
SHEETS_SYNC_KEY=<long random secret shared with the scheduler user>
GOOGLE_SHEET_ID=1n_aQpueOSE8OYl5y5KW3_NuYFg7Knlw3BYslllEp1zk
```

Share the `Auction Schedule` spreadsheet with the service account's `client_email` as an Editor. The scheduler selects the newest monthly tab (for example, `October 26`) and writes the sheet's Date, Time, Category, EA Schedule ID, Catalogue ID and Status to columns A:F. To force a particular tab, set the optional `GOOGLE_SHEET_GID` to its numeric tab ID. Keep the sync key private; enter it in the scheduler before sending rows. The scheduler stores unsent rows and holidays in the current browser. Add or import the applicable official holiday list before scheduling.

Build command:

```text
npm run build
```

## Render API

Use `backend/Dockerfile` or the existing Docker deployment. The container entrypoint applies Alembic migrations before starting FastAPI.

Set these environment variables:

```text
DATABASE_URL=<Render PostgreSQL internal connection string>
CORS_ORIGINS=https://sbcnav.vercel.app,https://sbcnav-38t2.vercel.app
BACKEND_WORKERS=2
LOG_LEVEL=info
```

The migration head is `0029_uts_prs_station_metrics`.

## One-time production contract import

After the Render deployment is healthy, upload the exported E-auction workbook to the new API:

```powershell
curl.exe -X POST "https://sbcnav.onrender.com/api/contracts/import" `
  -F "file=@Master file - Running contracts Part 3 Running in 2024.xlsx"
```

The import also backfills the existing commercial and catering contract tables into the unified registry. Verify:

```text
https://sbcnav.onrender.com/api/contracts/summary
https://sbcnav.vercel.app/contracts
```

Do not commit `.env` files, database passwords, service-account keys, or the source workbook to GitHub.
