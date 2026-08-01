param(
  [ValidateSet(
    "up",
    "down",
    "restart",
    "status",
    "logs",
    "open",
    "backup",
    "restore",
    "migrate",
    "rebuild",
    "client-up",
    "client-down",
    "install-docker"
  )]
  [string]$Action = "status",
  [string]$Backup
)

$ErrorActionPreference = "Stop"
trap {
  Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
$script:Root = Split-Path -Parent $PSScriptRoot
$script:EnvFile = Join-Path $script:Root ".env.docker"
$script:ComposeFile = Join-Path $script:Root "compose.yaml"
$script:ClientComposeFile = Join-Path $script:Root "compose.client.yaml"
$script:Backups = Join-Path $script:Root "backups"

function Initialize-Environment {
  if (Test-Path -LiteralPath $script:EnvFile) { return }
  $template = Join-Path $script:Root ".env.docker.example"
  if (-not (Test-Path -LiteralPath $template)) {
    throw ".env.docker.example is missing."
  }
  $password = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")).Substring(0, 48)
  $content = (Get-Content -LiteralPath $template -Raw).Replace(
    "replace-with-a-long-url-safe-password",
    $password
  )
  [System.IO.File]::WriteAllText(
    $script:EnvFile,
    $content,
    (New-Object System.Text.UTF8Encoding($false))
  )
  Write-Host "Created .env.docker with a generated PostgreSQL password."
}

function Get-EnvironmentValue([string]$Name, [string]$Default) {
  $line = Get-Content -LiteralPath $script:EnvFile |
    Where-Object { $_ -match "^$([regex]::Escape($Name))=" } |
    Select-Object -Last 1
  if (-not $line) { return $Default }
  return ($line -split "=", 2)[1].Trim()
}

function Assert-Docker {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is not installed. Run: railctl.cmd install-docker"
  }
  & docker version --format "{{.Server.Version}}" *> $null
  if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is installed but its engine is not running."
  }
  & docker compose version *> $null
  if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose v2 is required."
  }
}

function Invoke-Compose([string[]]$Arguments, [switch]$Client) {
  $file = if ($Client) { $script:ClientComposeFile } else { $script:ComposeFile }
  & docker compose --env-file $script:EnvFile -f $file @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose command failed: $($Arguments -join ' ')"
  }
}

function Test-Url([string]$Url) {
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4
    return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Wait-ForStack {
  $backendPort = Get-EnvironmentValue "BACKEND_PORT" "8000"
  $frontendPort = Get-EnvironmentValue "FRONTEND_PORT" "3000"
  $deadline = (Get-Date).AddMinutes(4)
  while ((Get-Date) -lt $deadline) {
    $backendReady = Test-Url "http://127.0.0.1:$backendPort/api/health"
    $frontendReady = Test-Url "http://127.0.0.1:$frontendPort"
    if ($backendReady -and $frontendReady) {
      Write-Host "Stack is ready."
      Write-Host "Dashboard: http://127.0.0.1:$frontendPort"
      Write-Host "API docs:  http://127.0.0.1:$backendPort/docs"
      return
    }
    Start-Sleep -Seconds 3
  }
  Invoke-Compose @("ps")
  throw "The stack did not become healthy. Run railctl.cmd logs."
}

function Install-DockerDesktop {
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    throw "Install Docker Desktop manually from https://www.docker.com/products/docker-desktop/."
  }
  & $winget.Source install --exact --id Docker.DockerDesktop `
    --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) { throw "Docker Desktop installation failed." }
  Write-Host "Docker Desktop installed. Restart Windows if requested, then open Docker Desktop once."
}

function Backup-Database {
  New-Item -ItemType Directory -Path $script:Backups -Force | Out-Null
  $name = "rail_dashboard_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"
  $containerPath = "/backups/$name"
  Invoke-Compose @(
    "exec", "-T", "db", "sh", "-c",
    "pg_dump -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" -Fc -f '$containerPath'"
  )
  $hostPath = Join-Path $script:Backups $name
  if (-not (Test-Path -LiteralPath $hostPath)) {
    throw "Backup command completed but $hostPath was not created."
  }
  Write-Host "Backup created: $hostPath"
}

function Restore-Database([string]$RequestedBackup) {
  if ($RequestedBackup) {
    $path = Resolve-Path -LiteralPath $RequestedBackup -ErrorAction Stop
  } else {
    $path = Get-ChildItem -LiteralPath $script:Backups -Filter "*.dump" |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1
    if (-not $path) { throw "No .dump backup was found in the backups folder." }
  }
  $resolved = $path.Path
  $backupRoot = (Resolve-Path -LiteralPath $script:Backups).Path
  if (-not $resolved.StartsWith($backupRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Restore files must be placed inside the project backups folder."
  }
  $name = Split-Path -Leaf $resolved
  Invoke-Compose @("stop", "backend")
  try {
    Invoke-Compose @(
      "exec", "-T", "db", "sh", "-c",
      "pg_restore -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" --clean --if-exists --no-owner --no-privileges --exit-on-error '/backups/$name'"
    )
    Invoke-Compose @("run", "--rm", "backend", "alembic", "upgrade", "head")
  } finally {
    Invoke-Compose @("start", "backend")
  }
  Write-Host "Database restored from $resolved"
}

Initialize-Environment

if ($Action -eq "install-docker") {
  Install-DockerDesktop
  exit 0
}

Assert-Docker

switch ($Action) {
  "up" {
    Invoke-Compose @("up", "-d", "--build")
    Wait-ForStack
  }
  "down" {
    Invoke-Compose @("down")
  }
  "restart" {
    Invoke-Compose @("restart")
    Wait-ForStack
  }
  "status" {
    Invoke-Compose @("ps")
  }
  "logs" {
    Invoke-Compose @("logs", "--tail", "200", "-f")
  }
  "open" {
    Wait-ForStack
    $frontendPort = Get-EnvironmentValue "FRONTEND_PORT" "3000"
    Start-Process "http://127.0.0.1:$frontendPort"
  }
  "backup" {
    Backup-Database
  }
  "restore" {
    Restore-Database $Backup
  }
  "migrate" {
    Invoke-Compose @("run", "--rm", "backend", "alembic", "upgrade", "head")
  }
  "rebuild" {
    Invoke-Compose @("build", "--pull")
    Invoke-Compose @("up", "-d")
    Wait-ForStack
  }
  "client-up" {
    Invoke-Compose @("up", "-d", "--build") -Client
    $frontendPort = Get-EnvironmentValue "FRONTEND_PORT" "3000"
    Write-Host "Frontend client: http://127.0.0.1:$frontendPort"
  }
  "client-down" {
    Invoke-Compose @("down") -Client
  }
}
