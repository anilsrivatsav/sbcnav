$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not $env:DATABASE_URL) { throw "DATABASE_URL is required and must point to PostgreSQL" }
& "C:\Program Files\Python313\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
