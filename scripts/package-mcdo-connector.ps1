$ErrorActionPreference = 'Stop'
$taskRepoRoot = Split-Path $PSScriptRoot -Parent
$taskConnectorRoot = Join-Path $taskRepoRoot 'browser-connector'
$taskPublicRoot = Join-Path $taskRepoRoot 'frontend\public'
New-Item -ItemType Directory -Force -Path $taskPublicRoot | Out-Null
Compress-Archive -Path (Join-Path $taskConnectorRoot '*') -DestinationPath (Join-Path $taskPublicRoot 'mcdo-connector.zip') -Force
@'
SBC NAV MCDO browser connector

1. Download mcdo-connector.zip and extract it to a permanent folder.
2. Chrome: open chrome://extensions. Edge: open edge://extensions.
3. Enable Developer mode, click Load unpacked, select the extracted folder.
4. Reload https://sbcnav-38t2.vercel.app/?view=mcdo.
5. Click Sign in to IREPS. Authenticate with your USB DSC token there.
6. Return to MCDO, enter the operator key, click Check IREPS.
7. Review the preview, then click Update sheets & Oracle.

Keep SBC NAV open while checking. Your DSC signer and token driver remain
required by IREPS. The Windows IREPS Updater is not used by this workflow.
The connector reads IREPS business records only. It does not receive the
operator key or read passwords, token PINs, cookies or private keys.
Its scripting permission is limited to https://www.ireps.gov.in.
Sheet and Oracle writes require configured operator access on the backend.
'@ | Set-Content -Encoding utf8 (Join-Path $taskPublicRoot 'mcdo-connector-setup.txt')
