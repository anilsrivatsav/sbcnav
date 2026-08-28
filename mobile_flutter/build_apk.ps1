param(
  [string]$ApiBaseUrl = "http://10.0.2.2:8000",
  [ValidateSet("arm64", "arm32", "universal")]
  [string]$Architecture = "arm64"
)

$ErrorActionPreference = "Stop"

$flutterCommand = Get-Command flutter -ErrorAction SilentlyContinue
if ($flutterCommand) {
  $flutter = $flutterCommand.Source
} else {
  $localFlutter = "C:\Users\CMI PA\development\flutter\bin\flutter.bat"
  if (-not (Test-Path -LiteralPath $localFlutter)) {
    throw "Flutter SDK was not found. Install Flutter and Android SDK before building."
  }
  $flutter = $localFlutter
}

Push-Location $PSScriptRoot
try {
  if (-not (Test-Path -LiteralPath "android")) {
    & $flutter create . --platforms=android --project-name rail_inspect --org in.gov.railway
  }

  & $flutter pub get
  & $flutter analyze --no-fatal-infos --no-fatal-warnings
  if ($LASTEXITCODE -ne 0) { throw "Flutter analysis failed." }

  switch ($Architecture) {
    "arm64" {
      & $flutter build apk --release --target-platform android-arm64 --split-per-abi --dart-define "API_BASE_URL=$ApiBaseUrl"
      $apkName = "app-arm64-v8a-release.apk"
    }
    "arm32" {
      & $flutter build apk --release --target-platform android-arm --split-per-abi --dart-define "API_BASE_URL=$ApiBaseUrl"
      $apkName = "app-armeabi-v7a-release.apk"
    }
    default {
      & $flutter build apk --release --dart-define "API_BASE_URL=$ApiBaseUrl"
      $apkName = "app-release.apk"
    }
  }
  if ($LASTEXITCODE -ne 0) { throw "Flutter APK build failed." }

  $apk = Join-Path $PSScriptRoot "build\app\outputs\flutter-apk\$apkName"
  if (-not (Test-Path -LiteralPath $apk)) {
    throw "APK build finished but $apkName was not found."
  }

  Write-Output "APK created: $apk"
} finally {
  Pop-Location
}
