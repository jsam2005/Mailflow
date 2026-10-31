#Requires -Version 5.1
<#
.SYNOPSIS
  Safe fallback stop for launcher-owned MailFlow services on Windows.

.DESCRIPTION
  Calls the loopback launcher /api/stop with the session token from the
  running launcher HTML when available. Never runs taskkill against all
  python/node/docker processes.
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
$launcherUrl = "http://127.0.0.1:8765"

try {
    $html = (Invoke-WebRequest -Uri "$launcherUrl/" -UseBasicParsing -TimeoutSec 3).Content
} catch {
    Write-Host "Launcher is not running on $launcherUrl - nothing to stop via control API."
    Write-Host "If MailFlow was started outside the launcher, stop those windows manually."
    Read-Host "Press Enter to close"
    exit 0
}

$token = $null
if ($html -match 'const TOKEN = "([^"]+)"') {
    $token = $Matches[1]
}
if (-not $token -or $token -eq "__LAUNCHER_TOKEN__") {
    Write-Host "ERROR: Could not read launcher session token. Is the launcher UI up?" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

try {
    $headers = @{
        Authorization = "Bearer $token"
        Origin = $launcherUrl
        "Content-Type" = "application/json"
    }
    $resp = Invoke-WebRequest -Uri "$launcherUrl/api/stop" -Method POST -Headers $headers -Body "{}" -UseBasicParsing -TimeoutSec 60
    Write-Host "Stop response: $($resp.Content)"
} catch {
    Write-Host "ERROR: Stop request failed: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Requested stop of launcher-owned services."
Write-Host "You can close the Start-MailFlow-Windows.cmd window if it is still open."
Read-Host "Press Enter to close"
