param(
  [string]$ApiBaseUrl = "http://10.0.2.2:8000"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
  throw "Flutter SDK was not found on PATH. Install Flutter and Android SDK, then reopen PowerShell."
}

Push-Location $PSScriptRoot
try {
  if (-not (Test-Path -LiteralPath "android")) {
    flutter create .
  }

  flutter pub get
  flutter analyze
  flutter build apk --release --dart-define "API_BASE_URL=$ApiBaseUrl"

  $apk = Join-Path $PSScriptRoot "build\app\outputs\flutter-apk\app-release.apk"
  if (-not (Test-Path -LiteralPath $apk)) {
    throw "APK build finished but app-release.apk was not found."
  }

  Write-Output "APK created: $apk"
} finally {
  Pop-Location
}
