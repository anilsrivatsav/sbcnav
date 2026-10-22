param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$InnoCompiler,
    [string]$Output = (Join-Path $PSScriptRoot '../dist/windows'),
    [string]$PrivateConnection,
    [string]$PrivateOutput,
    [switch]$SkipApplicationBuild
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Output = [IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Force -Path $Output | Out-Null
if (!$SkipApplicationBuild) {
& $Python -m PyInstaller --noconfirm --distpath (Join-Path $Output 'app') --workpath (Join-Path $root 'build/windows') (Join-Path $root 'desktop-companion/windows/SBCNAV.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Standalone application build failed.' }
}
& $InnoCompiler ('/DBuildDir=' + (Join-Path $Output 'app/SBCNAVUpdater')) ('/DOutputDir=' + $Output) (Join-Path $root 'desktop-companion/windows/setup.iss')
if ($LASTEXITCODE -ne 0) { throw 'Windows installer build failed.' }
$installer = Join-Path $Output 'SBC-NAV-Setup-2.2.0.exe'
$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $Output 'SBC-NAV-Setup-2.2.0.sha256'), "$hash  SBC-NAV-Setup-2.2.0.exe`n")
Write-Output "Built: $installer"
if ($PrivateConnection) {
    if (!$PrivateOutput) { throw 'PrivateOutput must be outside the public build directory.' }
    $PrivateOutput = [IO.Path]::GetFullPath($PrivateOutput)
    if ($PrivateOutput.StartsWith($Output, [StringComparison]::OrdinalIgnoreCase)) { throw 'Private installer output must be outside the public build directory.' }
    New-Item -ItemType Directory -Path $PrivateOutput -Force | Out-Null
    & $InnoCompiler ('/DBuildDir=' + (Join-Path $Output 'app/SBCNAVUpdater')) ('/DOutputDir=' + $PrivateOutput) ('/DPrivateConnection=' + [IO.Path]::GetFullPath($PrivateConnection)) (Join-Path $root 'desktop-companion/windows/setup.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Private onboarding installer build failed.' }
    Write-Output ('Private installer built in: ' + $PrivateOutput)
}
