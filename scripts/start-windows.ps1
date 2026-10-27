#Requires -Version 5.1
<#
.SYNOPSIS
  Everyday MailFlow launcher entry for Windows (loopback control service).
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    if ($RepoRoot -and (Test-Path -LiteralPath $RepoRoot)) {
        return (Resolve-Path -LiteralPath $RepoRoot).Path
    }
    $here = $PSScriptRoot
    if (-not $here) {
        $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $here "..")).Path
}

$root = Get-RepoRoot
Set-Location -LiteralPath $root

$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "ERROR: backend\.venv not found. Run Setup-MailFlow-Windows.cmd first." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# Refresh PATH for npm when started from Explorer.
$machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
$user = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machine;$user"

$launcherUrl = "http://127.0.0.1:8765/"
try {
    $resp = Invoke-WebRequest -Uri $launcherUrl -UseBasicParsing -TimeoutSec 2
    if ($resp.StatusCode -ge 200) {
        Write-Host "Launcher already running — opening $launcherUrl"
        Start-Process $launcherUrl
        exit 0
    }
} catch {
    # not running yet
}

Write-Host "Starting MailFlow launcher on $launcherUrl"
Write-Host "Keep this window open. Close it or press Ctrl+C to shut the launcher down."
Write-Host ""

# Open browser once the port accepts connections.
$opener = Start-Job -ScriptBlock {
    param($Url)
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1
            if ($r.StatusCode -ge 200) {
                Start-Process $Url
                return
            }
        } catch { }
        Start-Sleep -Milliseconds 300
    }
} -ArgumentList $launcherUrl

try {
    & $python -m launcher --host 127.0.0.1 --port 8765
    $code = $LASTEXITCODE
} finally {
    Receive-Job $opener -ErrorAction SilentlyContinue | Out-Null
    Remove-Job $opener -Force -ErrorAction SilentlyContinue
}

if ($code -ne 0) {
    Write-Host "Launcher exited with code $code" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit $code
}
