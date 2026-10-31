#Requires -Version 5.1
<#
.SYNOPSIS
  One-click everyday MailFlow start for Windows.

.DESCRIPTION
  Ensures Docker Desktop + Postgres are up, starts the loopback launcher,
  then automatically starts MailFlow and opens the app in the browser.
  Leave this window open while using MailFlow.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [switch]$NoAutoStart
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

function Test-DockerReady {
    try {
        docker info 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Ensure-DockerDesktop {
    if (Test-DockerReady) {
        Write-Host "Docker is ready."
        return
    }

    $dockerExe = Join-Path ${env:ProgramFiles} "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $dockerExe)) {
        $dockerExe = Join-Path ${env:ProgramFiles(x86)} "Docker\Docker\Docker Desktop.exe"
    }

    if (Test-Path -LiteralPath $dockerExe) {
        Write-Host "Starting Docker Desktop..."
        Start-Process -FilePath $dockerExe | Out-Null
    } else {
        throw @"
Docker Desktop is not installed or not ready.
Install it from https://docs.docker.com/desktop/setup/install/windows-install/
Then run Start-MailFlow-Windows.cmd again.
"@
    }

    Write-Host "Waiting for Docker Desktop (first launch can take 1-2 minutes)..."
    $deadline = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerReady) {
            Write-Host "Docker is ready."
            return
        }
        Start-Sleep -Seconds 3
    }
    throw "Docker Desktop did not become ready in time. Open Docker Desktop manually, wait until it is running, then try again."
}

function Ensure-Postgres {
    param([string]$Root)
    Write-Host "Starting Postgres (docker compose)..."
    Push-Location -LiteralPath $Root
    try {
        docker compose up -d postgres
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose up -d postgres failed (exit $LASTEXITCODE)."
        }
        for ($i = 0; $i -lt 60; $i++) {
            docker compose exec -T postgres pg_isready -U mailflow 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Postgres is ready."
                return
            }
            Start-Sleep -Seconds 1
        }
        throw "Postgres did not become ready. Check Docker Desktop and try again."
    } finally {
        Pop-Location
    }
}

function Get-LauncherToken {
    param([string]$BaseUrl)
    $html = (Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing -TimeoutSec 5).Content
    if ($html -match 'const TOKEN = "([^"]+)"') {
        $token = $Matches[1]
        if ($token -and $token -ne "__LAUNCHER_TOKEN__") {
            return $token
        }
    }
    throw "Could not read launcher session token."
}

function Invoke-LauncherStart {
    param([string]$BaseUrl)
    $token = Get-LauncherToken -BaseUrl $BaseUrl
    $headers = @{
        Authorization = "Bearer $token"
        Origin = $BaseUrl.TrimEnd("/")
        "Content-Type" = "application/json"
    }
    Write-Host "Starting MailFlow services..."
    $resp = Invoke-WebRequest -Uri "$BaseUrl/api/start" -Method POST -Headers $headers -Body "{}" -UseBasicParsing -TimeoutSec 120
    Write-Host "Start response: $($resp.Content)"
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

try {
    Ensure-DockerDesktop
    Ensure-Postgres -Root $root
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

$launcherUrl = "http://127.0.0.1:8765"
$launcherAlreadyUp = $false
try {
    $resp = Invoke-WebRequest -Uri "$launcherUrl/" -UseBasicParsing -TimeoutSec 2
    if ($resp.StatusCode -ge 200) { $launcherAlreadyUp = $true }
} catch { }

if ($launcherAlreadyUp) {
    Write-Host "Launcher already running."
    if (-not $NoAutoStart) {
        try {
            Invoke-LauncherStart -BaseUrl $launcherUrl
        } catch {
            Write-Host "Could not auto-start services: $($_.Exception.Message)" -ForegroundColor Yellow
            Start-Process "$launcherUrl/"
        }
    } else {
        Start-Process "$launcherUrl/"
    }
    Write-Host "MailFlow should open in your browser. You can close this window only if you use Stop separately;"
    Write-Host "keeping the original Start window open is still recommended."
    exit 0
}

Write-Host ""
Write-Host "Starting MailFlow (one-click)..."
Write-Host "Keep this window open while you use the app."
Write-Host ""

# After launcher binds: auto Start MailFlow + open app (launcher /api/start opens browser).
$helper = Start-Job -ScriptBlock {
    param($BaseUrl, $DoAutoStart)
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing -TimeoutSec 1
            if ($r.StatusCode -ge 200) { break }
        } catch { }
        Start-Sleep -Milliseconds 400
    }
    if (-not $DoAutoStart) {
        Start-Process "$BaseUrl/"
        return
    }
    try {
        $html = (Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing -TimeoutSec 5).Content
        if ($html -notmatch 'const TOKEN = "([^"]+)"') { Start-Process "$BaseUrl/"; return }
        $token = $Matches[1]
        $headers = @{
            Authorization = "Bearer $token"
            Origin = $BaseUrl
            "Content-Type" = "application/json"
        }
        Invoke-WebRequest -Uri "$BaseUrl/api/start" -Method POST -Headers $headers -Body "{}" -UseBasicParsing -TimeoutSec 120 | Out-Null
    } catch {
        Start-Process "$BaseUrl/"
    }
} -ArgumentList $launcherUrl, (-not $NoAutoStart)

try {
    & $python -m launcher --host 127.0.0.1 --port 8765
    $code = $LASTEXITCODE
} finally {
    Receive-Job $helper -ErrorAction SilentlyContinue | Out-Null
    Remove-Job $helper -Force -ErrorAction SilentlyContinue
}

if ($code -ne 0) {
    Write-Host "Launcher exited with code $code" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit $code
}
