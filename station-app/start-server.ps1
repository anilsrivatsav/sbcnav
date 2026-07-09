$ErrorActionPreference = "Stop"

$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Users\CMI PA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

Set-Location $appDir
& $python -m http.server 5173 --bind 127.0.0.1
