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
