param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$KeyFile
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '../desktop-companion'
$destination = Join-Path $env:LOCALAPPDATA 'IREPS Earnings Updater/Web companion'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -LiteralPath (Join-Path $source 'server.py'),(Join-Path $source 'launch.py') -Destination $destination -Force
Copy-Item -LiteralPath (Join-Path $source 'engine') -Destination $destination -Recurse -Force
Copy-Item -LiteralPath (Join-Path $source 'deskflow.py') -Destination $destination -Force
Copy-Item -LiteralPath (Join-Path $source 'rp') -Destination $destination -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'update-mcdo-desktop.ps1') -Destination (Join-Path $destination 'update.ps1') -Force
Copy-Item -LiteralPath $KeyFile -Destination (Join-Path $destination 'operator.key') -Force
$pythonWindowless = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (!(Test-Path -LiteralPath $pythonWindowless)) { throw 'The configured Python installation must include pythonw.exe.' }
$launcher = Join-Path $destination 'launch.py'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'SBC NAV Updater.lnk'))
$shortcut.TargetPath = $pythonWindowless
$shortcut.Arguments = '"' + $launcher + '"'
$shortcut.WorkingDirectory = $destination
$shortcut.Description = 'Open the web updater using the working desktop IREPS collector'
$shortcut.Save()
$startup = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Startup')) 'SBC NAV Updater.lnk'))
$startup.TargetPath = $pythonWindowless
$startup.Arguments = '"' + $launcher + '" --background'
$startup.WorkingDirectory = $destination
$startup.Save()
$protocol = 'HKCU:\Software\Classes\sbcnav-updater'
New-Item -Path "$protocol\shell\open\command" -Force | Out-Null
Set-Item -Path $protocol -Value 'URL:SBC NAV Updater'
New-ItemProperty -Path $protocol -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
Set-Item -Path "$protocol\shell\open\command" -Value ('"' + $pythonWindowless + '" "' + $launcher + '" --background')
Start-Process -FilePath $pythonWindowless -ArgumentList ('"' + $launcher + '" --background') -WindowStyle Hidden
Write-Output 'Desktop connection installed and started. No key is exposed to the web page.'
