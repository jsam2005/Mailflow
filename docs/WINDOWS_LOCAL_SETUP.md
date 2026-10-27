# MailFlow on a fresh Windows 11 PC

Target: **Windows 11 x64**. Other editions may work but are unsupported.

A `file://` HTML page **cannot** run shell commands. Windows uses:

| File | Role |
|------|------|
| `Setup-MailFlow-Windows.cmd` | First-time setup (double-click) |
| `scripts/setup-windows.ps1` | Setup logic |
| `Start-MailFlow-Windows.cmd` | Everyday launcher (double-click) |
| `Stop-MailFlow-Windows.cmd` | Fallback stop of **launcher-owned** services |
| Launcher UI at `http://127.0.0.1:8765/` | Start / Open / Stop / status |

macOS continues to use `MailFlow.command` / `launcher/setup.command`.

---

## 1. Obtain the repository

### Option A — Git (recommended)

1. If Git is missing, install from https://git-scm.com/download/win (or use setup with `-InstallPrereqs` after a ZIP download of just the scripts — see below).
2. Open PowerShell:

```powershell
cd $env:USERPROFILE\Documents
git clone https://github.com/jsam2005/Mailflow.git
cd Mailflow
```

### Option B — GitHub ZIP (no Git yet)

1. Open the GitHub repo → **Code** → **Download ZIP**.
2. Extract to a folder **without** relying on OneDrive-only online placeholders if possible (e.g. `C:\Users\<you>\Documents\Mailflow`).
3. Paths with spaces are supported (e.g. `C:\Users\Jane Doe\Documents\Mailflow`).

Official downloads if you install tools yourself:

| Tool | Version | Link |
|------|---------|------|
| Git | latest | https://git-scm.com/download/win |
| Python | **3.12.x only** (not 3.14) | https://www.python.org/downloads/ — enable **Add python.exe to PATH** |
| Node.js | **20+ LTS** | https://nodejs.org/en/download |
| Docker Desktop | current | https://docs.docker.com/desktop/setup/install/windows-install/ |
| winget | App Installer | Microsoft Store → “App Installer” |

---

## 2. First-time setup

1. Start **Docker Desktop** and wait until it is running (Postgres uses Compose — same engine as macOS/Linux; MailFlow does **not** switch to SQLite for local app data).
2. Double-click **`Setup-MailFlow-Windows.cmd`**.
3. To also install Git / Python 3.12 / Node LTS / Docker via winget (UAC prompts are normal):

```text
Setup-MailFlow-Windows.cmd -InstallPrereqs
```

Or from PowerShell in the repo folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1 -InstallPrereqs
```

`-ExecutionPolicy Bypass` applies **only to that process**. Setup never changes the machine-wide execution policy or disables Windows security features.

### What setup does

- Checks Windows x64 and required tool versions  
- Creates `backend\.venv` (project-specific)  
- `pip install -r backend\requirements.txt`  
- `npm ci` (falls back to `npm install`) using `frontend\package-lock.json`  
- Runs `npm run build` once as a compile check (everyday Start still uses Vite dev)  
- Creates `.env` / `backend\.env` from `.env.example` **only if missing**, with generated `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY`, `CRON_SECRET`, and `ADMIN_PASSWORD` (never printed, never committed)  
- Starts Compose Postgres when Docker is available  
- Runs `alembic upgrade head` against **localhost** only  

### What setup does **not** do

- Overwrite an existing `.env`, database volume, or upload storage  
- Enable `CAMPAIGN_SENDING_ENABLED` or live billing  
- Install dependencies again on everyday Start  

Logs: `launcher\.runtime\setup-windows.log`

---

## 3. Everyday use

1. Ensure Docker Desktop (Postgres) is running.  
2. Double-click **`Start-MailFlow-Windows.cmd`** and **leave the window open**.  
3. Browser opens `http://127.0.0.1:8765/` → **Start MailFlow**.  
4. When ready, MailFlow opens at `http://127.0.0.1:5173/`.  
5. In-app **Exit local app** (launcher mode only) or launcher **Stop** / **`Stop-MailFlow-Windows.cmd`** stops **only** processes this launcher started.

---

## 4. Configuration you must complete yourself

Setup generates local secrets and leaves development defaults. You must still supply:

| Purpose | Variables / action |
|---------|------------------|
| Login admin | Prefer `python -m app.scripts.create_admin` (see README). Dev bootstrap `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env` only apply when `ENVIRONMENT=development`. |
| Gmail connect | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/email-accounts/google/callback` — configure the same redirect in Google Cloud (see [GMAIL_SETUP.md](GMAIL_SETUP.md)). |
| Auth emails to a real inbox | Default `AUTH_EMAIL_PROVIDER=console` (or `file`) prints/writes messages locally — **not** delivered to inboxes. For real delivery use `AUTH_EMAIL_PROVIDER=resend` plus `RESEND_API_KEY` and `AUTH_EMAIL_FROM`. |
| Campaign sending | Keep `CAMPAIGN_SENDING_ENABLED=false` until ready; then set `true` and optionally `CAMPAIGN_TEST_RECIPIENT_ALLOWLIST`. |
| Billing | Keep disabled for local; Stripe test keys only when intentionally enabling billing. |

Never commit `.env` or real OAuth/API keys.

---

## 5. Email behavior (local)

| Provider | Behavior |
|----------|----------|
| `console` | Verification / reset messages go to the API console log |
| `file` | Written under `AUTH_EMAIL_OUTBOX_PATH` (local outbox files) |
| `resend` | Real transactional email via Resend (needs API key) |

Campaign mail uses **Gmail OAuth**, not Resend. Tests must not send real mail (`CAMPAIGN_SENDING_ENABLED=false` by default).

---

## 6. Troubleshooting

| Symptom | What to check |
|---------|----------------|
| `ERR_CONNECTION_REFUSED` on `:8765` | Start via `Start-MailFlow-Windows.cmd`, not only setup |
| Port 8000 / 5173 in use | Stop the other app, or Open if MailFlow is already healthy |
| Migrations refused | `DATABASE_URL` must use `localhost` / `127.0.0.1` |
| winget missing | Install App Installer, or use the manual links above |
| Docker errors | Start Docker Desktop; WSL2 backend required on Windows 11 |

---

## 7. Security notes

- Launcher binds to **loopback only** (`127.0.0.1:8765`).  
- Control actions are allowlisted (`start` / `stop` / `open` / `status`) with a session token and Origin checks.  
- Hosted / production builds do **not** expose **Exit local app**.  
- Stop never runs broad kills of all Python, Node, PostgreSQL, or Docker processes.
