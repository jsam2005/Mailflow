# Production deployment

## Architecture

- **Frontend:** Vite/React static assets on Vercel
- **Backend:** FastAPI via Vercel Python (`/api/*`)
- **Database:** External PostgreSQL (Neon recommended)
- **Files:** `STORAGE_PROVIDER=vercel_blob` (not local disk)
- **Auth model:** Private admin-only app (no public registration). Create admin with CLI.

## Campaign worker on Vercel Hobby

Vercel Hobby only supports **daily** cron execution. MailFlow campaign delivery needs more frequent processing (minutes, not once per day), so **automatic campaign delivery is disabled** in the initial free deployment.

- `vercel.json` does **not** register a cron schedule (Hobby rejects `*/5 * * * *`).
- Keep `ENABLE_LOCAL_SCHEDULER=false` and `CAMPAIGN_SENDING_ENABLED=false` on Hobby.
- The protected worker endpoint remains available for a future external scheduler or always-on worker:

  `GET|POST /api/v1/internal/workers/campaign-send`

  Authenticate with `Authorization: Bearer <CRON_SECRET>` (min 32 characters). Never put the secret in the URL.

Do **not** use a daily Hobby cron as a workaround — it is not suitable for MailFlow send pacing.

When you move to a plan or host that can invoke the worker every few minutes, point that scheduler at the same endpoint with `CRON_SECRET`, then enable sending carefully (allowlist first).

## Sequence

1. Create Neon PostgreSQL (enable SSL; prefer pooled connection string for the app).
2. Create Vercel Blob store; copy `BLOB_READ_WRITE_TOKEN`.
3. Create one Vercel project from this repo (`vercel.json` builds frontend + routes `/api` to FastAPI).
4. Set env vars from `.env.production.example` (never commit secrets).
5. Deploy with `CAMPAIGN_SENDING_ENABLED=false`.
6. Run migrations **once** against production DB (from a trusted local machine; use the **direct** Neon URL, not the pooler):

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

10. Login → Connect Gmail → Send test email (manual test send; campaign queue automation stays off on Hobby).

## Database backups

MailFlow does **not** auto-backup PostgreSQL. Configure Neon/provider backups before real sends.

## Notes

- Never run `scripts/seed_dev.py` or `clean_development_data.py` in production.
- Never auto-migrate on every serverless request.
- APScheduler is disabled when `ENABLE_LOCAL_SCHEDULER=false` / production.
