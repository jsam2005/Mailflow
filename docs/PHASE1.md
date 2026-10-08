# Phase 1 verification checklist

## What was built

- Docker Compose stack (`postgres`, `backend`, `frontend`)
- FastAPI backend with JWT auth, health checks, admin bootstrap
- Alembic migration for `users`
- React + Vite + TypeScript + Tailwind frontend
- Login, protected routes, sidebar layout, dashboard shell

## Commands

```bash
# From repo root
cp .env.example .env
docker compose up --build

# Backend tests
cd backend && source .venv/bin/activate && pytest

# Frontend
cd frontend && npm run typecheck && npm run build && npm test
```

## Verify

1. **Backend liveness:** `curl http://localhost:8000/health`
2. **Backend readiness:** `curl http://localhost:8000/api/v1/health`
3. **Login:** `POST /api/v1/auth/login` with admin credentials
4. **Frontend:** open http://localhost:5173 → sign in → dashboard shell
5. **Postgres:** `docker compose exec postgres psql -U mailflow -d mailflow -c '\dt'`

## Stop

Phase 1 is complete. Wait for instruction: **CONTINUE PHASE 2**
