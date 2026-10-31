# MailFlow

Email campaign management for controlled Gmail outreach.

Private admin-only application (no public signup). Create administrators with the CLI.

## Prerequisites

- PostgreSQL 16+
- Python 3.12 (do not use 3.14)
- Node.js 20+
- (Optional) Docker Compose for local Postgres

---

## Local launcher

`launcher.html` alone cannot run shell commands (`file://` has no terminal access). A small loopback control service on `127.0.0.1:8765` owns Start / Open / Stop. In-app **Exit local app** appears only when Vite was started by that launcher (not in hosted builds).

| Platform | First-time setup | Everyday start | Fallback stop |
|----------|------------------|----------------|---------------|
| macOS | `launcher/setup.command` | `MailFlow.command` | Launcher **Stop** / Exit |
| Windows 11 x64 | `Setup-MailFlow-Windows.cmd` | `Start-MailFlow-Windows.cmd` | `Stop-MailFlow-Windows.cmd` |

Full Windows guide (fresh PC, winget, Git/ZIP, Gmail, auth email): [docs/WINDOWS_LOCAL_SETUP.md](docs/WINDOWS_LOCAL_SETUP.md).

Local updates from GitHub (Check for updates / Update now): [docs/LOCAL_UPDATES.md](docs/LOCAL_UPDATES.md).

**First-time setup** installs dependencies and runs migrations once — not on every Start. Manual equivalent remains below.

## Development

```bash
cp .env.example .env
# Set JWT_SECRET, TOKEN_ENCRYPTION_KEY, ADMIN_* for local bootstrap

# Postgres (Docker)
docker compose up -d postgres

# Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:5173      |
| Backend  | http://localhost:8000      |
| API docs | http://localhost:8000/docs |
| Launcher | http://127.0.0.1:8765      |

Local admin is created on startup only when `ENVIRONMENT=development` and `ADMIN_EMAIL` / `ADMIN_PASSWORD` are set. Prefer:

```bash
cd backend
python -m app.scripts.create_admin --email you@example.com --name Admin
```

Dev seed (never runs in production):

```bash
ENVIRONMENT=development python scripts/seed_dev.py
```

Local cleanup utility (interactive; refuses production):

```bash
ENVIRONMENT=development python scripts/clean_development_data.py
```

Campaign sending is off by default. For local send tests:

```env
CAMPAIGN_SENDING_ENABLED=true
ENABLE_LOCAL_SCHEDULER=true
# Optional allowlist:
CAMPAIGN_TEST_RECIPIENT_ALLOWLIST=you@example.com
```

Vite proxies `/api` → `http://localhost:8000`. Leave `VITE_API_BASE_URL` empty for same-origin calls.

---

## Testing

```bash
# Backend (isolated DB — defaults to in-memory SQLite)
cd backend
source .venv/bin/activate
pytest

# Optional dedicated test DB:
# TEST_DATABASE_URL=postgresql+psycopg2://mailflow:mailflow_secret@localhost:5432/mailflow_test pytest

# Frontend
cd frontend
npm test
npx tsc --noEmit
npm run build

# Local launcher (from repo root)
backend/.venv/bin/pytest launcher/tests -q
```

Pytest refuses non-local / known-hosted production database URLs.

Migration round-trip:

```bash
cd backend
alembic upgrade head
alembic downgrade 007
alembic upgrade head
```

---

## Production

Do **not** deploy until the deployment phase. Preparation is documented in:

- [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md)
- [docs/GOOGLE_PRODUCTION_VERIFICATION.md](docs/GOOGLE_PRODUCTION_VERIFICATION.md)
- [`.env.production.example`](.env.production.example)

Summary:

1. External PostgreSQL (Neon) + SSL / pooled URL
2. Object storage (`STORAGE_PROVIDER=vercel_blob`)
3. Vercel project with `vercel.json` (SPA + `/api`; no Hobby cron schedule)
4. Set production env vars (no defaults, no localhost DB)
5. `alembic upgrade head` once (not per request)
6. `python -m app.scripts.create_admin` (no default password)
7. Production Google OAuth callback HTTPS URL
8. Keep `CAMPAIGN_SENDING_ENABLED=false` on Hobby (automatic campaign delivery needs frequent worker invocations)

Production must use:

```env
ENVIRONMENT=production
ENABLE_LOCAL_SCHEDULER=false
CAMPAIGN_SENDING_ENABLED=false
```

Vercel Hobby only allows daily crons, which is unsuitable for MailFlow sending. The worker endpoint stays for a future external scheduler — see [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md).

---

## Architecture

- **Frontend:** React, Vite, TypeScript, Tailwind, TanStack Query
- **Backend:** FastAPI, SQLAlchemy, Alembic, JWT (Argon2/bcrypt passwords)
- **Database:** PostgreSQL
- **Storage:** `StorageProvider` — local (dev) or Vercel Blob (prod)
- **Workers:** APScheduler in development; protected HTTP batch worker in production (external scheduler when available; not Vercel Hobby cron)

## Docs

| Doc | Topic |
|-----|--------|
| [docs/PHASE7.md](docs/PHASE7.md) | Campaign delivery |
| [docs/GMAIL_SETUP.md](docs/GMAIL_SETUP.md) | Google OAuth local setup |
| [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md) | Deploy checklist |
| [docs/GOOGLE_PRODUCTION_VERIFICATION.md](docs/GOOGLE_PRODUCTION_VERIFICATION.md) | Google review prep |

## License

Private / proprietary — all rights reserved.
