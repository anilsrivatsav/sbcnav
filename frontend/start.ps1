$ErrorActionPreference = "Stop"
$nodeHome = "C:\Users\CMI PA\OneDrive - PRAGNA VIDYANIKETAN\Documents\Works - PH-53\tools\node-portable\node-v22.16.0-win-x64"
$env:PATH = "$nodeHome;$env:PATH"
Set-Location $PSScriptRoot
& "$nodeHome\npm.cmd" run dev
