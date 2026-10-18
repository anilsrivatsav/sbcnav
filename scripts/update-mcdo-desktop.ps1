param(
    [switch]$ConfirmIdle
)

$ErrorActionPreference = 'Stop'
$destination = Join-Path $env:LOCALAPPDATA 'IREPS Earnings Updater\Web companion'
$launcher = Join-Path $destination 'launch.py'
if (!(Test-Path -LiteralPath $launcher)) {
    throw 'SBC NAV desktop companion is not installed on this computer.'
}

function Set-UpdateState([string]$phase, [string]$message) {
    $payload = @{ phase = $phase; message = $message } | ConvertTo-Json -Compress
    Set-Content -LiteralPath (Join-Path $destination 'software-update.json') -Value $payload -Encoding UTF8
}

trap {
    Set-UpdateState 'error' $_.Exception.Message
    break
}

Set-UpdateState 'checking' 'Checking GitHub for the latest desktop version…'
try { Unregister-ScheduledTask -TaskName 'SBC NAV Desktop Update' -Confirm:$false -ErrorAction Stop } catch { }

$headers = @{ 'User-Agent' = 'SBC-NAV-desktop-updater'; 'Accept' = 'application/vnd.github+json' }
$commit = Invoke-RestMethod -Uri 'https://api.github.com/repos/anilsrivatsav/sbcnav/commits/main' -Headers $headers -TimeoutSec 30
$revision = [string]$commit.sha
if ($revision -notmatch '^[0-9a-f]{40}$') { throw 'GitHub returned an invalid revision.' }
$revisionFile = Join-Path $destination '.installed-commit'
if ((Test-Path -LiteralPath $revisionFile) -and ((Get-Content -LiteralPath $revisionFile -Raw).Trim() -eq $revision)) {
    Set-UpdateState 'current' "Desktop companion is current ($($revision.Substring(0, 7)))."
    Write-Output "SBC NAV desktop companion is current ($($revision.Substring(0, 7)))."
    return
}

function Get-CompanionProcesses {
    $serverPath = [regex]::Escape((Join-Path $destination 'server.py'))
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -in @('python.exe', 'pythonw.exe') -and $_.CommandLine -match $serverPath
    }
}

function Test-CompanionIdle {
    try {
        $status = Invoke-RestMethod -Uri 'http://127.0.0.1:48722/status' -Headers @{ Origin = 'https://sbcnav-38t2.vercel.app' } -TimeoutSec 3
        if ($status.busy -or $status.deskflow_busy) { return $false }
        if (($status.PSObject.Properties.Name -notcontains 'deskflow_busy') -and !$ConfirmIdle) {
            Write-Warning 'The older companion cannot report Deskflow activity. Run once with -ConfirmIdle after all work finishes.'
            return $false
        }
        return $true
    } catch {
        # An unresponsive but running companion may still be collecting IREPS data.
        if (@(Get-CompanionProcesses).Count -gt 0) {
            throw 'The running desktop companion did not report its work status. Close it after its current work finishes, then retry the update.'
        }
        return $true
    }
}

# Never interrupt a Sheets update or an IREPS/Deskflow collection.
if (!(Test-CompanionIdle)) {
    Set-UpdateState 'busy' 'MCDO or Deskflow is working. Try the desktop update after it finishes.'
    Write-Output 'SBC NAV is working. The desktop update will retry on the next run.'
    return
}

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('sbcnav-update-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$backup = Join-Path $temp 'backup'
$replaced = @('server.py', 'launch.py', 'deskflow.py', 'engine', 'rp')
$stopped = $false
$started = $false
try {
    Set-UpdateState 'downloading' 'Downloading the latest desktop companion…'
    $zip = Join-Path $temp 'source.zip'
    Invoke-WebRequest -Uri "https://github.com/anilsrivatsav/sbcnav/archive/$revision.zip" -OutFile $zip -TimeoutSec 120
    Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $temp 'source')
    $source = Join-Path $temp "source\sbcnav-$revision\desktop-companion"
    foreach ($item in $replaced) {
        if (!(Test-Path -LiteralPath (Join-Path $source $item))) { throw "Download is missing $item." }
    }

    $shell = New-Object -ComObject WScript.Shell
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'SBC NAV Updater.lnk'
    if (!(Test-Path -LiteralPath $shortcutPath)) { throw 'SBC NAV desktop shortcut is missing; Python location cannot be verified.' }
    $pythonWindowless = $shell.CreateShortcut($shortcutPath).TargetPath
    if (!(Test-Path -LiteralPath $pythonWindowless)) { throw 'The configured pythonw.exe is missing.' }

    # Recheck after the download; collection may have started while it arrived.
    if (!(Test-CompanionIdle)) {
        Set-UpdateState 'busy' 'MCDO or Deskflow started working. Try again after it finishes.'
        Write-Output 'SBC NAV started working during the download. The desktop update will retry on the next run.'
        return
    }

    $servers = @(Get-CompanionProcesses)
    Set-UpdateState 'installing' 'Installing and restarting the desktop companion…'
    foreach ($server in $servers) { Stop-Process -Id $server.ProcessId -Force -ErrorAction Stop }
    $stopped = $servers.Count -gt 0

    New-Item -ItemType Directory -Path $backup | Out-Null
    foreach ($item in $replaced) {
        $old = Join-Path $destination $item
        if (Test-Path -LiteralPath $old) { Move-Item -LiteralPath $old -Destination $backup -Force }
    }
    foreach ($item in $replaced) {
        Copy-Item -LiteralPath (Join-Path $source $item) -Destination $destination -Recurse -Force
    }
    $oldConfig = Join-Path $backup 'engine\config.json'
    if (Test-Path -LiteralPath $oldConfig) {
        Copy-Item -LiteralPath $oldConfig -Destination (Join-Path $destination 'engine\config.json') -Force
    }
    $updaterSource = Join-Path $temp "source\sbcnav-$revision\scripts\update-mcdo-desktop.ps1"
    if (!(Test-Path -LiteralPath $updaterSource)) { throw 'Download is missing the desktop updater.' }
    Copy-Item -LiteralPath $updaterSource -Destination (Join-Path $destination 'update.ps1') -Force
    Start-Process -FilePath $pythonWindowless -ArgumentList ('"' + $launcher + '" --background') -WorkingDirectory $destination -WindowStyle Hidden
    $started = $true
    $online = $false
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        Start-Sleep -Seconds 2
        try {
            $status = Invoke-RestMethod -Uri 'http://127.0.0.1:48722/status' -Headers @{ Origin = 'https://sbcnav-38t2.vercel.app' } -TimeoutSec 2
            if ($status.connected) { $online = $true; break }
        } catch [System.Net.WebException] {
            # Python is still starting.
        }
    }
    if (!$online) { throw 'The updated desktop companion did not start within 30 seconds.' }
    Set-Content -LiteralPath $revisionFile -Value $revision -NoNewline
    Set-UpdateState 'complete' "Desktop companion updated to $($revision.Substring(0, 7))."
    Write-Output "SBC NAV desktop companion updated to $($revision.Substring(0, 7))."
} catch {
    Set-UpdateState 'error' $_.Exception.Message
    if ($started) {
        @(Get-CompanionProcesses) | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    if (Test-Path -LiteralPath $backup) {
        foreach ($item in $replaced) {
            $old = Join-Path $backup $item
            if (Test-Path -LiteralPath $old) {
                $current = Join-Path $destination $item
                if (Test-Path -LiteralPath $current) { Remove-Item -LiteralPath $current -Recurse -Force }
                Move-Item -LiteralPath $old -Destination $destination -Force
            }
        }
    }
    if ($stopped -and (Test-Path -LiteralPath $launcher) -and $pythonWindowless) {
        Start-Process -FilePath $pythonWindowless -ArgumentList ('"' + $launcher + '" --background') -WorkingDirectory $destination -WindowStyle Hidden
    }
    throw
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
