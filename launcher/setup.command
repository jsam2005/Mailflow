#!/bin/bash
# One-time local setup for MailFlow on this Mac. Safe to re-run.
# Does NOT start the app — use MailFlow.command / the launcher Start button after this.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "==> MailFlow first-time setup"
echo "    Repo: $ROOT"

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Python 3.12 is required (do not use 3.14)."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 20+ is required."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is recommended for local Postgres (docker compose up -d postgres)."
fi

if [[ ! -f "$ROOT/.env" && ! -f "$ROOT/backend/.env" ]]; then
  if [[ -f "$ROOT/.env.example" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo "Created .env from .env.example — edit secrets before real use."
  else
    echo "Missing .env — copy .env.example to .env first."
    exit 1
  fi
fi

# Prefer backend/.env for uvicorn when running from backend cwd.
if [[ -f "$ROOT/.env" && ! -f "$ROOT/backend/.env" ]]; then
  cp "$ROOT/.env" "$ROOT/backend/.env"
  echo "Synced backend/.env from root .env"
fi

if command -v docker >/dev/null 2>&1; then
  echo "==> Starting Postgres (docker compose)"
  docker compose up -d postgres
  echo "Waiting for Postgres…"
  for _ in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-mailflow}" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

echo "==> Backend venv + dependencies"
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3.12 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements.txt
echo "==> Running migrations (setup only — not on every Start)"
alembic upgrade head

echo "==> Frontend dependencies"
cd "$ROOT/frontend"
npm install

chmod +x "$ROOT/MailFlow.command" "$ROOT/launcher/setup.command" 2>/dev/null || true

echo
echo "Setup complete."
echo "Everyday use: double-click MailFlow.command, then Start MailFlow."
echo "Optional admin: cd backend && python -m app.scripts.create_admin --email you@example.com --name Admin"
read -r -p "Press Enter to close…"
