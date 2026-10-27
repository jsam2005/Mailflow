#!/bin/bash
# Double-click to open the MailFlow local launcher (macOS).
# Leave this Terminal window open while you use MailFlow.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

PYTHON=""
if [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
  PYTHON="$ROOT/backend/.venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON="$(command -v python3.12)"
else
  PYTHON="$(command -v python3 || true)"
fi

fail() {
  echo ""
  echo "ERROR: $1" >&2
  osascript -e "display alert \"MailFlow launcher\" message \"$1\" as critical" >/dev/null 2>&1 || true
  echo ""
  read -r -p "Press Enter to close…"
  exit 1
}

if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  fail "Python was not found. Run launcher/setup.command first."
fi

if [[ ! -d "$ROOT/backend/.venv" ]]; then
  fail "Backend virtualenv missing. Run launcher/setup.command first."
fi

# If the launcher is already listening, just open the UI.
if curl -fsS "http://127.0.0.1:8765/" >/dev/null 2>&1; then
  echo "Launcher already running — opening http://127.0.0.1:8765/"
  open "http://127.0.0.1:8765/"
  exit 0
fi

echo "Starting MailFlow launcher on http://127.0.0.1:8765/"
echo "Keep this window open. Close it (or Ctrl+C) to shut the launcher down."
echo ""

# Prefer system browser (not an IDE embedded preview).
open "http://127.0.0.1:8765/" 2>/dev/null || true

# Start after a brief moment so the first open can retry once the server binds.
(
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS "http://127.0.0.1:8765/" >/dev/null 2>&1; then
      open "http://127.0.0.1:8765/"
      exit 0
    fi
    sleep 0.3
  done
) &

exec "$PYTHON" -m launcher --host 127.0.0.1 --port 8765
