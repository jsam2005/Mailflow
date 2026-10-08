# Production deployment (prepare now — deploy in next phase)

Do **not** deploy until the deployment phase starts. This document is the checklist.

## Architecture

- **Frontend:** Vite/React static assets on Vercel
- **Backend:** FastAPI via Vercel Python (`/api/*`)
- **Database:** External PostgreSQL (Neon recommended)
- **Files:** `STORAGE_PROVIDER=vercel_blob` (not local disk)
- **Worker:** Vercel Cron → `GET /api/v1/internal/workers/campaign-send`
  - Set env `CRON_SECRET` (min 32 chars). Vercel Cron automatically sends
    `Authorization: Bearer <CRON_SECRET>` when that variable is present.
  - The endpoint rejects missing/invalid secrets with 401. Never put the secret in the URL.
- **Auth model:** Private admin-only app (no public registration). Create admin with CLI.

## Sequence

1. Create Neon PostgreSQL (enable SSL; prefer pooled connection string).
2. Create Vercel Blob store; copy `BLOB_READ_WRITE_TOKEN`.
3. Create Vercel project from this repo (do not deploy yet until phase starts).
4. Set env vars from `.env.production.example` (never commit secrets).
5. Deploy.
6. Run migrations **once** against production DB (from CI or secure local machine):

   ```bash
   cd backend
   export DATABASE_URL=...
   alembic upgrade head
   ```

7. Create production admin:

   ```bash
   cd backend
   python -m app.scripts.create_admin --email you@company.com --name "Admin"
   ```

8. Google Cloud OAuth:
   - Add production redirect: `https://YOUR_DOMAIN/api/v1/email-accounts/google/callback`
   - Add authorized domain
   - Keep app in Testing with test users, or complete verification (see `GOOGLE_PRODUCTION_VERIFICATION.md`)

9. Verify:

   ```bash
   curl https://YOUR_DOMAIN/api/v1/health
   ```

10. Login → Connect Gmail → Send test email → one-recipient campaign.
11. Confirm cron runs (Vercel → Crons) and worker health.
12. Set `CAMPAIGN_SENDING_ENABLED=true` only after single-email success.

## Database backups

MailFlow does **not** auto-backup PostgreSQL. Configure Neon/provider backups before real sends.

## Notes

- Never run `scripts/seed_dev.py` or `clean_development_data.py` in production.
- Never auto-migrate on every serverless request.
- APScheduler is disabled when `ENABLE_LOCAL_SCHEDULER=false` / production.
