# Production deployment

## Architecture

- **Frontend:** Vite/React static assets on Vercel
- **Backend:** FastAPI via Vercel Python (`/api/*`)
- **Database:** External PostgreSQL (Neon recommended)
- **Files:** `STORAGE_PROVIDER=vercel_blob` (not local disk)
- **Auth model:** Private admin-only app (no public registration). Create admin with CLI.

## Campaign worker on Vercel Hobby

Vercel Hobby rejects minute-level cron (`*/5 * * * *`). MailFlow does **not** register unsupported crons.

Sending on Hobby uses:

1. **Kick on start/resume** — one worker batch runs in-process after a campaign starts or resumes.
2. **Authenticated drain** — logged-in admin can call:

   `POST /api/v1/system/process-campaign-queue`

   (JWT session; repeats until the queue is empty / rate-limited.)
3. **Cron secret endpoint** (optional external scheduler / Pro plan):

   `GET|POST /api/v1/internal/workers/campaign-send`  
   `Authorization: Bearer <CRON_SECRET>`

Keep `ENABLE_LOCAL_SCHEDULER=false` on Vercel. Enable `CAMPAIGN_SENDING_ENABLED=true` only when ready, preferably with `CAMPAIGN_TEST_RECIPIENT_ALLOWLIST` set to one controlled address first.

Queued message personalization can be repaired (unsent only) via:

`POST /api/v1/campaigns/{id}/personalize-queued`

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
