param(
  [ValidateSet(
    "gui",
    "status",
    "start-all",
    "start-backend",
    "start-frontend",
    "stop-app",
    "stop-all",
    "build-arm64",
    "build-universal"
  )]
  [string]$Action = "gui"
)

$ErrorActionPreference = "Stop"
$script:Root = Split-Path -Parent $PSScriptRoot
$script:Backend = Join-Path $script:Root "backend"
$script:Frontend = Join-Path $script:Root "frontend"
$script:Mobile = Join-Path $script:Root "mobile_flutter"
$script:Runtime = Join-Path $script:Root ".runtime"
$script:BackendOut = Join-Path $script:Runtime "backend.out.log"
$script:BackendErr = Join-Path $script:Runtime "backend.err.log"
$script:FrontendOut = Join-Path $script:Runtime "frontend.out.log"
$script:FrontendErr = Join-Path $script:Runtime "frontend.err.log"
$script:BuildOut = Join-Path $script:Runtime "apk-build.out.log"
$script:BuildErr = Join-Path $script:Runtime "apk-build.err.log"
$script:BuildProcess = $null

New-Item -ItemType Directory -Path $script:Runtime -Force | Out-Null

function Get-PostgresService {
  Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "postgresql*" -or $_.DisplayName -like "*PostgreSQL*" } |
    Select-Object -First 1
}

function Get-PortOwner([int]$Port) {
  $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if (-not $connection) { return $null }
  Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)" -ErrorAction SilentlyContinue
}

function Test-Http([string]$Url, [int]$TimeoutSeconds = 3) {
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
    return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Get-SystemState {
  $databaseService = Get-PostgresService
  $databaseReady = $databaseService -and $databaseService.Status -eq "Running" -and (Get-PortOwner 5432)
  [pscustomobject]@{
    Database = if ($databaseReady) { "Ready" } elseif ($databaseService) { "Stopped" } else { "Not installed" }
    Backend = if (Test-Http "http://127.0.0.1:8000/api/health") { "Ready" } elseif (Get-PortOwner 8000) { "Port conflict" } else { "Stopped" }
    Frontend = if (Test-Http "http://127.0.0.1:3000") { "Ready" } elseif (Get-PortOwner 3000) { "Starting" } else { "Stopped" }
    Node = if (Resolve-JsRunner -Quiet) { "Ready" } else { "Not installed" }
    Flutter = if (Resolve-Flutter -Quiet) { "Ready" } else { "Not installed" }
  }
}

function Wait-Until([scriptblock]$Condition, [int]$TimeoutSeconds, [string]$FailureMessage) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (& $Condition) { return }
    Start-Sleep -Milliseconds 500
    $formsApplication = "System.Windows.Forms.Application" -as [type]
    if ($formsApplication) {
      $formsApplication::DoEvents()
    }
  }
  throw $FailureMessage
}

function Invoke-ServiceAction([string]$ServiceName, [ValidateSet("Start", "Stop")] [string]$ServiceAction) {
  try {
    if ($ServiceAction -eq "Start") {
      Start-Service -Name $ServiceName
    } else {
      Stop-Service -Name $ServiceName
    }
  } catch {
    $command = if ($ServiceAction -eq "Start") {
      "Start-Service -Name '$ServiceName'"
    } else {
      "Stop-Service -Name '$ServiceName'"
    }
    $process = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList @(
      "-NoProfile",
      "-ExecutionPolicy", "Bypass",
      "-Command", $command
    )
    if ($process.ExitCode -ne 0) {
      throw "Administrator permission was not granted for PostgreSQL."
    }
  }
}

function Start-Database {
  $service = Get-PostgresService
  if (-not $service) { throw "PostgreSQL is not installed as a Windows service." }
  if ($service.Status -ne "Running") {
    Invoke-ServiceAction $service.Name "Start"
  }
  Wait-Until { (Get-PostgresService).Status -eq "Running" -and (Get-PortOwner 5432) } 30 "PostgreSQL did not become ready."
}

function Stop-Database {
  $service = Get-PostgresService
  if ($service -and $service.Status -ne "Stopped") {
    Invoke-ServiceAction $service.Name "Stop"
    Wait-Until { (Get-PostgresService).Status -eq "Stopped" } 30 "PostgreSQL did not stop."
  }
}

function Resolve-Python {
  $configured = "C:\Program Files\Python313\python.exe"
  if (Test-Path -LiteralPath $configured) { return $configured }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { return $python.Source }
  throw "Python 3 was not found."
}

function Resolve-JsRunner([switch]$Quiet) {
  $portableNodeRoot = Join-Path $script:Root "tools\node-portable"
  $portableNpm = Get-ChildItem -LiteralPath $portableNodeRoot -Recurse -Filter "npm.cmd" -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($portableNpm) {
    $startScript = Join-Path $script:Frontend "start.ps1"
    return [pscustomobject]@{
      Path = "powershell.exe"
      Arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$startScript`""
      )
    }
  }
  $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
  if ($pnpm -and $pnpm.Source -notlike "*\.cache\codex-runtimes\*") {
    return [pscustomobject]@{ Path = $pnpm.Source; Arguments = @("dev") }
  }
  $systemPnpm = Join-Path $env:APPDATA "npm\pnpm.cmd"
  if (Test-Path -LiteralPath $systemPnpm) {
    return [pscustomobject]@{ Path = $systemPnpm; Arguments = @("dev") }
  }
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if ($npm) {
    return [pscustomobject]@{ Path = $npm.Source; Arguments = @("run", "dev") }
  }
  $systemNpm = "C:\Program Files\nodejs\npm.cmd"
  if (Test-Path -LiteralPath $systemNpm) {
    return [pscustomobject]@{ Path = $systemNpm; Arguments = @("run", "dev") }
  }
  if ($Quiet) { return $null }
  throw "Node.js LTS is not installed. Use the Install Node.js LTS button, then reopen this control panel."
}

function Resolve-Flutter([switch]$Quiet) {
  $flutter = Get-Command flutter -ErrorAction SilentlyContinue
  if ($flutter) { return $flutter.Source }
  $localFlutter = "C:\Users\CMI PA\development\flutter\bin\flutter.bat"
  if (Test-Path -LiteralPath $localFlutter) { return $localFlutter }
  if ($Quiet) { return $null }
  throw "Flutter SDK was not found."
}

function Clear-LogFiles([string[]]$Paths) {
  foreach ($path in $Paths) {
    if (Test-Path -LiteralPath $path) {
      Remove-Item -LiteralPath $path -Force
    }
  }
}

function Start-Backend {
  Start-Database
  if (Test-Http "http://127.0.0.1:8000/api/health") { return }
  if (Get-PortOwner 8000) { throw "Port 8000 is occupied by another process." }

  Clear-LogFiles @($script:BackendOut, $script:BackendErr)
  $python = Resolve-Python
  Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $script:Backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $script:BackendOut `
    -RedirectStandardError $script:BackendErr | Out-Null
  Wait-Until { Test-Http "http://127.0.0.1:8000/api/health" } 60 "Backend failed to start. Check backend.err.log."
}

function Start-Frontend {
  if (Test-Http "http://127.0.0.1:3000") { return }
  if (Get-PortOwner 3000) { throw "Port 3000 is occupied by another process." }

  $runner = Resolve-JsRunner
  Clear-LogFiles @($script:FrontendOut, $script:FrontendErr)
  Start-Process -FilePath $runner.Path `
    -ArgumentList $runner.Arguments `
    -WorkingDirectory $script:Frontend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $script:FrontendOut `
    -RedirectStandardError $script:FrontendErr | Out-Null
  Wait-Until { Test-Http "http://127.0.0.1:3000" 5 } 90 "Frontend failed to start. Check frontend.err.log."
}

function Stop-AppPort([int]$Port, [string]$ExpectedPattern) {
  $owner = Get-PortOwner $Port
  if (-not $owner) { return }
  $description = "$($owner.Name) $($owner.CommandLine)"
  if ($description -notmatch $ExpectedPattern) {
    throw "Port $Port belongs to an unexpected process: $description"
  }
  Stop-Process -Id $owner.ProcessId -Force
  Wait-Until { -not (Get-PortOwner $Port) } 20 "Process on port $Port did not stop."
}

function Stop-Application {
  Stop-AppPort 3000 "node|next|npm|pnpm"
  Stop-AppPort 8000 "python|uvicorn|app:app"
}

function Start-All {
  Start-Database
  Start-Backend
  Start-Frontend
}

function Stop-All {
  Stop-Application
  Stop-Database
}

function Install-NodeLts {
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    throw "Windows Package Manager (winget) is unavailable. Install Node.js LTS from https://nodejs.org/."
  }
  $process = Start-Process -FilePath $winget.Source -Wait -PassThru -ArgumentList @(
    "install", "--exact", "--id", "OpenJS.NodeJS.LTS",
    "--accept-package-agreements", "--accept-source-agreements"
  )
  if ($process.ExitCode -ne 0) { throw "Node.js installation did not complete successfully." }
}

function Start-ApkBuild([ValidateSet("arm64", "universal")] [string]$Architecture, [switch]$Wait) {
  Resolve-Flutter | Out-Null
  if ($script:BuildProcess -and -not $script:BuildProcess.HasExited) {
    throw "An APK build is already running."
  }
  Clear-LogFiles @($script:BuildOut, $script:BuildErr)
  $buildScript = Join-Path $script:Mobile "build_apk.ps1"
  $arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$buildScript`"",
    "-Architecture", $Architecture
  )
  $script:BuildProcess = Start-Process powershell.exe `
    -ArgumentList $arguments `
    -WorkingDirectory $script:Mobile `
    -WindowStyle Hidden `
    -RedirectStandardOutput $script:BuildOut `
    -RedirectStandardError $script:BuildErr `
    -PassThru
  if ($Wait) {
    $script:BuildProcess.WaitForExit()
    if ($script:BuildProcess.ExitCode -ne 0) {
      throw "APK build failed. Check apk-build.err.log."
    }
    Get-Content $script:BuildOut
  }
}

function Show-State {
  $state = Get-SystemState
  $state | Format-List
}

function Show-ControlPanel {
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing

  [System.Windows.Forms.Application]::EnableVisualStyles()
  $form = New-Object System.Windows.Forms.Form
  $form.Text = "Rail Dashboard Control"
  $form.StartPosition = "CenterScreen"
  $form.Size = New-Object System.Drawing.Size(720, 590)
  $form.MinimumSize = New-Object System.Drawing.Size(720, 590)
  $form.BackColor = [System.Drawing.Color]::FromArgb(241, 246, 248)
  $form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

  $title = New-Object System.Windows.Forms.Label
  $title.Text = "Rail Dashboard Control"
  $title.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 20)
  $title.AutoSize = $true
  $title.Location = New-Object System.Drawing.Point(24, 18)
  $form.Controls.Add($title)

  $subtitle = New-Object System.Windows.Forms.Label
  $subtitle.Text = "PostgreSQL, FastAPI, Next.js and Flutter APK operations"
  $subtitle.ForeColor = [System.Drawing.Color]::FromArgb(70, 85, 95)
  $subtitle.AutoSize = $true
  $subtitle.Location = New-Object System.Drawing.Point(27, 58)
  $form.Controls.Add($subtitle)

  $statusPanel = New-Object System.Windows.Forms.Panel
  $statusPanel.Location = New-Object System.Drawing.Point(24, 92)
  $statusPanel.Size = New-Object System.Drawing.Size(655, 82)
  $statusPanel.BackColor = [System.Drawing.Color]::White
  $statusPanel.BorderStyle = "FixedSingle"
  $form.Controls.Add($statusPanel)

  $statusLabels = @{}
  $statusNames = @("Database", "Backend", "Frontend", "Node", "Flutter")
  for ($index = 0; $index -lt $statusNames.Count; $index++) {
    $name = $statusNames[$index]
    $heading = New-Object System.Windows.Forms.Label
    $heading.Text = $name
    $heading.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 9)
    $heading.Location = New-Object System.Drawing.Point((18 + ($index * 126)), 14)
    $heading.AutoSize = $true
    $statusPanel.Controls.Add($heading)

    $value = New-Object System.Windows.Forms.Label
    $value.Text = "Checking..."
    $value.Location = New-Object System.Drawing.Point((18 + ($index * 126)), 42)
    $value.AutoSize = $true
    $statusPanel.Controls.Add($value)
    $statusLabels[$name] = $value
  }

  $activity = New-Object System.Windows.Forms.TextBox
  $activity.Location = New-Object System.Drawing.Point(24, 382)
  $activity.Size = New-Object System.Drawing.Size(655, 135)
  $activity.Multiline = $true
  $activity.ReadOnly = $true
  $activity.ScrollBars = "Vertical"
  $activity.BackColor = [System.Drawing.Color]::FromArgb(18, 31, 39)
  $activity.ForeColor = [System.Drawing.Color]::FromArgb(212, 239, 233)
  $activity.Font = New-Object System.Drawing.Font("Consolas", 9)
  $form.Controls.Add($activity)

  function Add-Activity([string]$Message) {
    $activity.AppendText("$(Get-Date -Format 'HH:mm:ss')  $Message`r`n")
  }

  function Refresh-Status {
    $state = Get-SystemState
    foreach ($name in $statusNames) {
      $value = $statusLabels[$name]
      $value.Text = $state.$name
      $value.ForeColor = if ($state.$name -eq "Ready") {
        [System.Drawing.Color]::FromArgb(0, 122, 92)
      } elseif ($state.$name -in @("Stopped", "Not installed")) {
        [System.Drawing.Color]::FromArgb(177, 70, 38)
      } else {
        [System.Drawing.Color]::FromArgb(167, 112, 0)
      }
    }
  }

  function Invoke-UiAction([string]$Label, [scriptblock]$Operation) {
    try {
      $form.UseWaitCursor = $true
      Add-Activity "$Label started."
      & $Operation
      Add-Activity "$Label completed."
    } catch {
      Add-Activity "$Label failed: $($_.Exception.Message)"
      [System.Windows.Forms.MessageBox]::Show(
        $_.Exception.Message,
        "Rail Dashboard Control",
        "OK",
        "Error"
      ) | Out-Null
    } finally {
      $form.UseWaitCursor = $false
      Refresh-Status
    }
  }

  function New-ControlButton([string]$Text, [int]$X, [int]$Y, [int]$Width, [scriptblock]$Handler) {
    $button = New-Object System.Windows.Forms.Button
    $button.Text = $Text
    $button.Location = New-Object System.Drawing.Point($X, $Y)
    $button.Size = New-Object System.Drawing.Size($Width, 42)
    $button.FlatStyle = "Flat"
    $button.BackColor = [System.Drawing.Color]::White
    $button.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(185, 202, 210)
    $button.Add_Click($Handler)
    $form.Controls.Add($button)
  }

  New-ControlButton "Start all" 24 194 150 { Invoke-UiAction "Start all" { Start-All } }
  New-ControlButton "Stop app" 184 194 150 { Invoke-UiAction "Stop app" { Stop-Application } }
  New-ControlButton "Stop all + DB" 344 194 150 { Invoke-UiAction "Stop all" { Stop-All } }
  New-ControlButton "Refresh" 504 194 175 { Refresh-Status; Add-Activity "Status refreshed." }

  New-ControlButton "Open dashboard" 24 246 150 {
    Invoke-UiAction "Open dashboard" {
      Start-All
      Start-Process "http://127.0.0.1:3000"
    }
  }
  New-ControlButton "Open API docs" 184 246 150 {
    Invoke-UiAction "Open API docs" {
      Start-Backend
      Start-Process "http://127.0.0.1:8000/docs"
    }
  }
  New-ControlButton "Install Node.js LTS" 344 246 150 {
    Invoke-UiAction "Node.js installation" { Install-NodeLts }
  }
  New-ControlButton "Open logs" 504 246 175 {
    Start-Process explorer.exe $script:Runtime
  }

  New-ControlButton "Build ARM64 APK" 24 310 205 {
    Invoke-UiAction "ARM64 APK build" { Start-ApkBuild "arm64" }
    Add-Activity "Build continues in the background. Logs are available in .runtime."
  }
  New-ControlButton "Build universal APK" 239 310 205 {
    Invoke-UiAction "Universal APK build" { Start-ApkBuild "universal" }
    Add-Activity "Build continues in the background. Logs are available in .runtime."
  }
  New-ControlButton "Open APK folder" 454 310 225 {
    $apkFolder = Join-Path $script:Mobile "build\app\outputs\flutter-apk"
    New-Item -ItemType Directory -Path $apkFolder -Force | Out-Null
    Start-Process explorer.exe $apkFolder
  }

  $buildLabel = New-Object System.Windows.Forms.Label
  $buildLabel.Text = "APK build: idle"
  $buildLabel.Location = New-Object System.Drawing.Point(27, 354)
  $buildLabel.AutoSize = $true
  $buildLabel.ForeColor = [System.Drawing.Color]::FromArgb(70, 85, 95)
  $form.Controls.Add($buildLabel)

  $timer = New-Object System.Windows.Forms.Timer
  $timer.Interval = 3000
  $timer.Add_Tick({
    Refresh-Status
    if ($script:BuildProcess) {
      if ($script:BuildProcess.HasExited) {
        $buildLabel.Text = if ($script:BuildProcess.ExitCode -eq 0) { "APK build: completed" } else { "APK build: failed - open logs" }
      } else {
        $buildLabel.Text = "APK build: running"
      }
    }
  })
  $timer.Start()

  Refresh-Status
  Add-Activity "Control panel ready. Operations run locally without Codex."
  [void]$form.ShowDialog()
  $timer.Stop()
}

switch ($Action) {
  "gui" { Show-ControlPanel }
  "status" { Show-State }
  "start-all" { Start-All; Show-State }
  "start-backend" { Start-Backend; Show-State }
  "start-frontend" { Start-Frontend; Show-State }
  "stop-app" { Stop-Application; Show-State }
  "stop-all" { Stop-All; Show-State }
  "build-arm64" { Start-ApkBuild "arm64" -Wait }
  "build-universal" { Start-ApkBuild "universal" -Wait }
}
