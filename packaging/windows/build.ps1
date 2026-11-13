# Build MailFlow.exe for Windows (one folder, local SQLite).
# Run on the Windows PC from any directory:
#   powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1
# Requires Python 3.12 and Node.js 20+.
# Output: packaging\windows\dist\MailFlow\MailFlow.exe
# Data is stored in %LOCALAPPDATA%\MailFlow, not next to the exe.

$ErrorActionPreference = "Stop"

$SpecDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $SpecDir "..\..")).Path
Set-Location $Root

Write-Host "MailFlow Windows build"
Write-Host "Repository: $Root"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js 20+ is required. Install it, then run this script again."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required (it ships with Node.js)."
}

$VenvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating backend\.venv with Python 3.12"
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        & py -3.12 -m venv (Join-Path $Root "backend\.venv")
    } else {
        & python -m venv (Join-Path $Root "backend\.venv")
    }
}
if (-not (Test-Path $VenvPython)) {
    throw "Could not create backend\.venv. Install Python 3.12 and retry."
}

Write-Host "Installing Python dependencies"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $Root "backend\requirements.txt")
& $VenvPython -m pip install "pyinstaller==6.22.3"

Write-Host "Building frontend"
Push-Location (Join-Path $Root "frontend")
if (Test-Path "package-lock.json") {
    npm ci
} else {
    npm install
}
# Desktop build: open straight into the app, no login screen.
$env:VITE_MAILFLOW_DESKTOP = "1"
npm run build
Remove-Item Env:VITE_MAILFLOW_DESKTOP
Pop-Location

$DistPath = Join-Path $SpecDir "dist"
$WorkPath = Join-Path $SpecDir "build"
Write-Host "Packaging MailFlow.exe"
& $VenvPython -m PyInstaller `
    (Join-Path $SpecDir "MailFlow.spec") `
    --noconfirm `
    --clean `
    --distpath $DistPath `
    --workpath $WorkPath

$Exe = Join-Path $DistPath "MailFlow\MailFlow.exe"
if (-not (Test-Path $Exe)) {
    throw "Build finished but $Exe was not created."
}

Write-Host ""
Write-Host "Built: $Exe"
Write-Host "Double-click MailFlow.exe. Your database is %LOCALAPPDATA%\MailFlow\mailflow.db"
