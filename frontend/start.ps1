$ErrorActionPreference = "Stop"
$portableRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "tools\node-portable"
$node = Get-ChildItem -LiteralPath $portableRoot -Recurse -Filter "node.exe" -ErrorAction SilentlyContinue |
  Select-Object -First 1
if (-not $node) {
  throw "Project-local Node.js was not found under tools\node-portable."
}
$nodeHome = $node.DirectoryName
$env:PATH = "$nodeHome;$env:PATH"
Set-Location $PSScriptRoot
& "$nodeHome\npm.cmd" run dev
