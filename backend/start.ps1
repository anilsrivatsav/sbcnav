$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
      [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
  }
}
if (-not $env:DATABASE_URL) { throw "DATABASE_URL is required and must point to PostgreSQL" }
& "C:\Program Files\Python313\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
