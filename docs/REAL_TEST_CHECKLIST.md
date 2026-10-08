# MailFlow Phase 7 — Real local test checklist

Use **only email addresses you personally control**.  
Do **not** import marketing leads. Keep limits ≤ 5/day and ≤ 5/hour for first tests.

Env file: project root [`.env`](../.env) (Docker Compose loads this).  
If you run uvicorn from `backend/`, also ensure that process sees the same vars (symlink recommended):

```bash
cd backend && ln -sf ../.env .env
```

---

## Values you must set manually in `.env`

| Variable | What to put |
|----------|-------------|
| `TOKEN_ENCRYPTION_KEY` | Output of Fernet generate command (valid key required) |
| `GOOGLE_CLIENT_ID` | From Google Cloud → OAuth Web client |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud → OAuth Web client |
| `GOOGLE_REDIRECT_URI` | Exact: `http://localhost:8000/api/v1/email-accounts/google/callback` |
| `FRONTEND_URL` | `http://localhost:5173` |
| `CAMPAIGN_SENDING_ENABLED` | Keep `false` until Section D passes; then `true` |
| `CAMPAIGN_TEST_RECIPIENT_ALLOWLIST` | Your controlled address(es), comma-separated |

Generate encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste output into `TOKEN_ENCRYPTION_KEY=` (replace any invalid placeholder).

---

## SECTION A — Preflight

- [ ] PostgreSQL running (`docker compose up -d postgres` or local Postgres on 5432)
- [ ] Migration 007 applied (`cd backend && alembic upgrade head`)
- [ ] Valid `TOKEN_ENCRYPTION_KEY` (Fernet)
- [ ] `GOOGLE_CLIENT_ID` present
- [ ] `GOOGLE_CLIENT_SECRET` present
- [ ] Redirect URI exact match in Google Cloud Console
- [ ] Gmail address added as Google OAuth **test user** (if app is in Testing mode)
- [ ] `CAMPAIGN_SENDING_ENABLED=false` initially
- [ ] `APP_TIMEZONE=Asia/Kolkata`
- [ ] No marketing dataset imported

---

## SECTION B — Start application

**Backend**

```bash
cd backend
source .venv/bin/activate
# ensure .env is visible (symlink to ../.env if needed)
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm run dev
```

**Or Docker**

```bash
docker compose up --build
```

Verify:

- [ ] http://localhost:8000/health → ok
- [ ] http://localhost:5173 loads

---

## SECTION C — Connect Gmail

1. Login to MailFlow (admin from `.env`)
2. Open `/email-accounts`
3. Click **Connect Gmail**
4. Complete Google OAuth
5. Confirm return to Email Accounts
6. Confirm status: **Connected**
7. Click **Test Connection**

Expected: connection working.

Scopes used by the app: `openid`, `userinfo.email`, `userinfo.profile`, `gmail.send` only (no mailbox read).

---

## SECTION D — Single test email first (STOP if this fails)

1. Use **Send Test Email** to an address **you control** (same Gmail or another you own)
2. Confirm API success
3. Confirm email arrives and HTML renders
4. If template has an image: confirm CID image renders

- [ ] Test email received

**If this fails: STOP. Do not enable campaign sending.**

---

## SECTION E — Enable campaign sending (after D passes)

In `.env`:

```env
CAMPAIGN_SENDING_ENABLED=true
CAMPAIGN_TEST_RECIPIENT_ALLOWLIST=YOUR_TEST_EMAIL@example.com
```

Restart backend. **Do not remove the allowlist.**

---

## SECTION F — Safe test data

**Contact list:** `MailFlow Test Contacts`  
**One contact only first:**

| Field | Value |
|-------|--------|
| First name | Test |
| Company | MailFlow Test |
| Email | YOUR_TEST_EMAIL (same as allowlist) |

**Template:** `MailFlow Delivery Test`

- Subject: `MailFlow test for {{first_name|there}}`
- Body: personalized first name + company; optional small image for CID

**Campaign:** `MailFlow Phase 7 Test`

- Daily / hourly limit: **5 / 5**
- Delay min/max: **30 / 30** (first test)
- Stop on reply: enabled (no reply sync yet — OK)

---

## SECTION G — Ready → Start → Complete

1. Validate → eligible = 1
2. **Mark Ready** → status `ready` (no send yet)
3. Confirm `CAMPAIGN_SENDING_ENABLED=true` + allowlist
4. **Start Campaign** → confirm dialog
5. Expect: `running` → message `queued` → `sending` → `sent` → campaign `completed`
6. Verify UI/API: `provider_message_id`, `rfc_message_id`, `sent_at`, attempt_count = 1
7. Verify inbox: personalization + HTML (+ CID if used)

---

## SECTION H — Pause / Resume (only after G passes)

1. Add **2** controlled addresses; update allowlist; restart backend
2. New campaign, delay **60** seconds
3. Start → after first send → **Pause**
4. Confirm remaining stay queued; wait past delay; still no send
5. **Resume** → remaining send → `completed`

---

## SECTION I — Cancel

1. New 2–3 recipient campaign
2. Start → after first sent → **Cancel**
3. Sent stays sent; queued → cancelled; no later sends

---

## SECTION J — Worker health & restart

```bash
curl -s http://localhost:8000/api/v1/system/worker-health
```

Expect: `scheduler_running`, `last_worker_tick`, no secrets.

Restart test: 2-recipient campaign, 60s delay, stop backend after first send, restart, second sends once, **no duplicate** of first.

---

## Safety rules

- Do not disable allowlist during first campaign tests
- Do not raise limits above 5 for initial testing
- Do not hammer Gmail / trigger abuse quotas on purpose
- Record outcomes in [`REAL_TEST_RESULT.md`](REAL_TEST_RESULT.md)
