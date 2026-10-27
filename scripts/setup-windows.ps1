#Requires -Version 5.1
<#
.SYNOPSIS
  First-time MailFlow setup for Windows 11 x64.

.DESCRIPTION
  Installs/checks prerequisites (optionally via winget), creates a project venv,
  installs dependencies from lockfiles/requirements, prepares local .env with
  generated secrets (without printing them), starts Postgres via Docker Compose
  when available, and runs Alembic migrations.

  Safe to re-run. Never overwrites an existing .env, database volume, or uploads.
  Does NOT change machine-wide PowerShell execution policy.
#>
[CmdletBinding()]
param(
    [switch]$InstallPrereqs,
    [switch]$SkipDocker,
    [switch]$SkipMigrations,
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Fail([string]$Message) {
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

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

function Test-IsWindows11OrCompatible {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $arch = (Get-CimInstance Win32_Processor | Select-Object -First 1).Architecture
        # 9 = x64
        $is64 = ($env:PROCESSOR_ARCHITECTURE -eq "AMD64") -or ($arch -eq 9)
        if (-not $is64) {
            return @{ Ok = $false; Reason = "MailFlow Windows setup supports Windows 11 x64 only. This machine reports architecture '$($env:PROCESSOR_ARCHITECTURE)'." }
        }
        # Caption often contains "Windows 11"; also accept Windows 10 22H2+ with warning.
        $caption = [string]$os.Caption
        if ($caption -match "Windows 11") {
            return @{ Ok = $true; Reason = $caption }
        }
        if ($caption -match "Windows 10") {
            Write-Host "WARNING: Detected $caption. Official target is Windows 11 x64; continuing anyway." -ForegroundColor Yellow
            return @{ Ok = $true; Reason = $caption }
        }
        return @{ Ok = $false; Reason = "Unsupported OS: $caption. Use Windows 11 x64." }
    } catch {
        return @{ Ok = $false; Reason = "Could not detect Windows version: $($_.Exception.Message)" }
    }
}

function Find-Command([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Get-PythonVersionString([string]$PythonExe) {
    & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
}

function Ensure-WingetPackage {
    param(
        [string]$Id,
        [string]$DisplayName
    )
    $winget = Find-Command "winget"
    if (-not $winget) {
        throw "winget is not available. Install $DisplayName manually (see docs/WINDOWS_LOCAL_SETUP.md)."
    }
    Write-Host "Installing/updating $DisplayName via winget ($Id). Approve UAC prompts if shown..."
    & winget install --id $Id -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
        # -1978335189 often means already installed
        throw "winget failed for $Id (exit $LASTEXITCODE)."
    }
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function New-SecureToken([int]$Bytes = 32) {
    $data = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($data)
    $rng.Dispose()
    return ([Convert]::ToBase64String($data) -replace '[+/=]', 'x')
}

function New-FernetKey {
    # 32 url-safe base64-encoded bytes (Fernet)
    $data = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($data)
    $rng.Dispose()
    return [Convert]::ToBase64String($data)
}

function Ensure-LocalEnv {
    param([string]$Root)
    $rootEnv = Join-Path $Root ".env"
    $backendEnv = Join-Path $Root "backend\.env"
    $example = Join-Path $Root ".env.example"

    if ((Test-Path -LiteralPath $rootEnv) -or (Test-Path -LiteralPath $backendEnv)) {
        Write-Host "Existing .env found — leaving configuration unchanged."
        if ((Test-Path -LiteralPath $rootEnv) -and -not (Test-Path -LiteralPath $backendEnv)) {
            Copy-Item -LiteralPath $rootEnv -Destination $backendEnv
            Write-Host "Synced backend\.env from root .env"
        }
        return
    }

    if (-not (Test-Path -LiteralPath $example)) {
        throw ".env.example is missing; cannot create local configuration."
    }

    Write-Host "Creating .env from .env.example with generated local secrets (values not printed)."
    $text = Get-Content -LiteralPath $example -Raw -Encoding UTF8
    $jwt = New-SecureToken 48
    $cron = New-SecureToken 48
    $adminPw = New-SecureToken 24
    $fernet = New-FernetKey

    $text = [regex]::Replace($text, '(?m)^JWT_SECRET=.*$', "JWT_SECRET=$jwt")
    $text = [regex]::Replace($text, '(?m)^CRON_SECRET=.*$', "CRON_SECRET=$cron")
    $text = [regex]::Replace($text, '(?m)^TOKEN_ENCRYPTION_KEY=.*$', "TOKEN_ENCRYPTION_KEY=$fernet")
    $text = [regex]::Replace($text, '(?m)^ADMIN_PASSWORD=.*$', "ADMIN_PASSWORD=$adminPw")
    # Keep billing/sending off for local first run.
    $text = [regex]::Replace($text, '(?m)^CAMPAIGN_SENDING_ENABLED=.*$', "CAMPAIGN_SENDING_ENABLED=false")
    $text = [regex]::Replace($text, '(?m)^BILLING_ENABLED=.*$', "BILLING_ENABLED=false")

    # Write without echoing secrets
    [System.IO.File]::WriteAllText($rootEnv, $text)
    Copy-Item -LiteralPath $rootEnv -Destination $backendEnv
    Write-Host "Wrote .env and backend\.env (not committed)."
}

function Wait-Postgres {
    param([string]$Root, [int]$Seconds = 60)
    $compose = Find-Command "docker"
    if (-not $compose) { return $false }
    Push-Location -LiteralPath $Root
    try {
        for ($i = 0; $i -lt $Seconds; $i++) {
            docker compose exec -T postgres pg_isready -U mailflow 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $true }
            Start-Sleep -Seconds 1
        }
    } finally {
        Pop-Location
    }
    return $false
}

# --- main ---
$root = Get-RepoRoot
$logDir = Join-Path $root "launcher\.runtime"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "setup-windows.log"
Start-Transcript -Path $logFile -Append | Out-Null

try {
    Write-Step "MailFlow Windows setup"
    Write-Host "Repo: $root"
    Write-Host "Log:  $logFile"

    $osCheck = Test-IsWindows11OrCompatible
    if (-not $osCheck.Ok) {
        throw $osCheck.Reason
    }
    Write-Host "OS check: $($osCheck.Reason)"

    if ($InstallPrereqs) {
        Write-Step "Installing prerequisites via winget (UAC may prompt)"
        if (-not (Find-Command "winget")) {
            throw @"
winget is not available on this machine.
Install App Installer from Microsoft Store, or install manually:
  Git:      https://git-scm.com/download/win
  Python:   https://www.python.org/downloads/release/python-31210/
            (3.12.x only — do not use 3.14; check 'Add python.exe to PATH')
  Node.js:  https://nodejs.org/en/download (LTS 20+)
  Docker:   https://docs.docker.com/desktop/setup/install/windows-install/
Then re-run Setup-MailFlow-Windows.cmd
"@
        }
        Ensure-WingetPackage -Id "Git.Git" -DisplayName "Git"
        Ensure-WingetPackage -Id "Python.Python.3.12" -DisplayName "Python 3.12"
        Ensure-WingetPackage -Id "OpenJS.NodeJS.LTS" -DisplayName "Node.js LTS"
        if (-not $SkipDocker) {
            Ensure-WingetPackage -Id "Docker.DockerDesktop" -DisplayName "Docker Desktop"
        }
        Refresh-Path
        Write-Host "If newly installed tools are still missing, close this window, open a new one, and re-run setup."
    }

    Write-Step "Checking required tools"
    $python = Find-Command "python"
    $pyLauncher = Find-Command "py"
    if (-not $python -and $pyLauncher) {
        $python = $pyLauncher
    }
    if (-not $python) {
        throw @"
Python was not found.
Install Python 3.12 from https://www.python.org/downloads/ (check Add to PATH),
or re-run: Setup-MailFlow-Windows.cmd -InstallPrereqs
"@
    }

    # Prefer py -3.12 when available
    $pythonExe = $python
    if (Find-Command "py") {
        try {
            $ver = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver) { $pythonExe = $ver.Trim() }
        } catch { }
    }

    $pyVer = Get-PythonVersionString $pythonExe
    if ($pyVer -ne "3.12") {
        throw "Python 3.12 is required (found $pyVer at $pythonExe). Do not use 3.14."
    }
    Write-Host "Python: $pythonExe ($pyVer)"

    $node = Find-Command "node"
    $npm = Find-Command "npm"
    if (-not $node -or -not $npm) {
        throw @"
Node.js / npm not found.
Install Node.js 20+ LTS from https://nodejs.org/en/download
or re-run with -InstallPrereqs.
"@
    }
    $nodeVer = (& node -v).Trim()
    Write-Host "Node: $nodeVer"
    if ($nodeVer -notmatch '^v(2[0-9]|[3-9][0-9])\.') {
        Write-Host "WARNING: Node $nodeVer detected; MailFlow expects Node 20+." -ForegroundColor Yellow
    }

    $git = Find-Command "git"
    if (-not $git) {
        Write-Host "WARNING: Git not found. ZIP downloads work, but cloning/updates need Git." -ForegroundColor Yellow
        Write-Host "Download: https://git-scm.com/download/win"
    }

    Ensure-LocalEnv -Root $root

    if (-not $SkipDocker) {
        Write-Step "PostgreSQL via Docker Compose"
        $docker = Find-Command "docker"
        if (-not $docker) {
            Write-Host @"
Docker not found. MailFlow requires PostgreSQL 16+ (same architecture as other platforms).
Install Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/
Then start Docker Desktop and re-run setup.
Alternatively, install PostgreSQL 16 locally and set DATABASE_URL in .env to match.
"@ -ForegroundColor Yellow
        } else {
            Push-Location -LiteralPath $root
            try {
                docker compose up -d postgres
                if ($LASTEXITCODE -ne 0) { throw "docker compose up failed (exit $LASTEXITCODE)." }
                if (-not (Wait-Postgres -Root $root)) {
                    throw "Postgres did not become ready in time. Is Docker Desktop running?"
                }
                Write-Host "Postgres is ready."
            } finally {
                Pop-Location
            }
        }
    }

    Write-Step "Backend virtual environment + dependencies"
    $backend = Join-Path $root "backend"
    $venvPython = Join-Path $backend ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Push-Location -LiteralPath $backend
        try {
            & $pythonExe -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw "Failed to create .venv" }
        } finally {
            Pop-Location
        }
    }
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

    if (-not $SkipMigrations) {
        Write-Step "Running migrations (setup only — not on everyday Start)"
        # Validate local DATABASE_URL host before migrating
        $envPath = Join-Path $backend ".env"
        if (-not (Test-Path -LiteralPath $envPath)) { $envPath = Join-Path $root ".env" }
        $dbUrl = ""
        Get-Content -LiteralPath $envPath | ForEach-Object {
            if ($_ -match '^\s*DATABASE_URL=(.*)$') { $dbUrl = $Matches[1].Trim() }
        }
        if ($dbUrl -notmatch 'localhost|127\.0\.0\.1') {
            throw "Refusing migrations: DATABASE_URL does not target localhost. Edit .env for local Postgres."
        }
        Push-Location -LiteralPath $backend
        try {
            & $venvPython -m alembic upgrade head
            if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head failed" }
        } finally {
            Pop-Location
        }
    }

    Write-Step "Frontend dependencies (package-lock.json)"
    $frontend = Join-Path $root "frontend"
    Push-Location -LiteralPath $frontend
    try {
        if (Test-Path -LiteralPath (Join-Path $frontend "package-lock.json")) {
            npm ci
            if ($LASTEXITCODE -ne 0) {
                Write-Host "npm ci failed; falling back to npm install" -ForegroundColor Yellow
                npm install
            }
        } else {
            npm install
        }
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        Write-Host "Running production build check..."
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
    } finally {
        Pop-Location
    }

    Write-Step "Setup complete"
    Write-Host "Everyday use: double-click Start-MailFlow-Windows.cmd, then Start MailFlow."
    Write-Host "Optional admin (password never printed here):"
    Write-Host "  cd backend"
    Write-Host "  .\.venv\Scripts\python.exe -m app.scripts.create_admin --email you@example.com --name Admin"
    Write-Host ""
    Write-Host "Before Gmail / real auth email / campaign sending, see docs\WINDOWS_LOCAL_SETUP.md"
}
catch {
    Write-Fail $_.Exception.Message
    Write-Host "See log: $logFile"
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
