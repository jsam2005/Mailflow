# Phase 7 — Campaign delivery engine

Phase 7 adds asynchronous campaign sending with safety limits, pause/resume/cancel, message tracking, and restart recovery.

## Worker architecture

- **APScheduler** runs in the FastAPI process lifespan (`start_scheduler` / `shutdown_scheduler`).
- Interval: `CAMPAIGN_WORKER_INTERVAL_SECONDS` (default 5).
- Each tick: `CampaignSenderWorker.tick()` — stale recovery, claim queued messages, send via `GmailProvider`, completion detection.
- Disabled in `ENVIRONMENT=test` and when `CAMPAIGN_SENDING_ENABLED=false`.
- Health: `GET /api/v1/system/worker-health`.

### Claiming

- Messages move `queued → sending` with a conditional `UPDATE` (atomic; safe for multiple workers on PostgreSQL with `FOR UPDATE SKIP LOCKED`-style patterns via rowcount check).
- At most **one in-flight send per email account** per tick (in-memory set + `next_send_allowed_at`).

### Ordering

- Eligible messages: `next_attempt_at ASC`, `created_at ASC` (oldest first across campaigns sharing an account).

## Message lifecycle

| Status | Meaning |
|--------|---------|
| `queued` | Waiting for worker |
| `sending` | Claimed; provider call in progress or interrupted |
| `sent` | Provider accepted; IDs stored |
| `failed` | Permanent failure or max retries |
| `cancelled` | Campaign cancelled or recipient no longer eligible |

One `EmailMessage` per `CampaignRecipient` (unique constraint).

**RFC Message-ID** is assigned and persisted before the Gmail API call to improve traceability on retry (not a guarantee of exactly-once delivery across provider crash windows).

**Stale `sending`:** after `CAMPAIGN_STALE_SENDING_MINUTES`, marked `failed` with `UNCERTAIN_PROVIDER_RESULT` (no blind resend).

## Campaign lifecycle

| Transition | Endpoint |
|------------|----------|
| `ready → running` | `POST /api/v1/campaigns/{id}/start` |
| `running → paused` | `POST .../pause` |
| `paused → running` | `POST .../resume` |
| `ready|running|paused → cancelled` | `POST .../cancel` |
| `running → completed` | Automatic when no queued/sending messages remain |

Start creates `EmailMessage` rows and sets recipients `pending → queued`. HTTP returns immediately; worker sends.

Duplicate start returns **409** (unique constraint + state check).

## Rate limits

Effective limits = **minimum** of campaign and email account caps (campaign cannot exceed account safety).

- **Daily:** counts `EmailMessage` with `status=sent` and `sent_at` in the current calendar day in `APP_TIMEZONE` (default `Asia/Kolkata`). UTC stored in DB.
- **Hourly:** rolling previous 60 minutes per account and per campaign.
- **Delay:** after each send attempt, `EmailAccount.next_send_allowed_at = now + effective minimum_delay_seconds` (no long sleeps in worker).

When limited, messages stay `queued` with `next_attempt_at` deferred.

## Retry policy

- Max attempts: `CAMPAIGN_MAX_SEND_ATTEMPTS` (default 3).
- Retry transient errors (429, 5xx, timeouts): backoff `CAMPAIGN_RETRY_DELAY_1_SECONDS` / `_2_SECONDS`.
- No retry: invalid recipient, auth revoked, `UNCERTAIN_PROVIDER_RESULT`, permanent provider errors.
- OAuth failure: account marked expired; **running campaign auto-paused**.

Manual retry: `POST .../messages/{message_id}/retry` (failed only; not `UNCERTAIN_PROVIDER_RESULT`).

## Content at send time

Uses **frozen campaign snapshot** (`snapshot_subject`, `snapshot_html`, `snapshot_plain_text`), not live template rows. Personalization uses the **current contact** linked from `CampaignRecipient`.

## Development safety

```env
CAMPAIGN_SENDING_ENABLED=false   # default — start returns 503
CAMPAIGN_TEST_RECIPIENT_ALLOWLIST=you@example.com   # optional; non-listed addresses deferred
```

Only send to addresses you have permission to contact.

## Known limitations

- Exactly-once delivery is not guaranteed if Gmail accepts a message and the backend crashes before commit.
- Reply/open/click tracking is Phase 8+.
- SQLite tests do not reproduce PostgreSQL `SKIP LOCKED`; concurrency covered via atomic update tests.

## API summary

- `POST /api/v1/campaigns/{id}/start|pause|resume|cancel`
- `GET /api/v1/campaigns/{id}/messages` (pagination, status, search)
- `GET /api/v1/campaigns/{id}/messages/{message_id}`
- `POST /api/v1/campaigns/{id}/messages/{message_id}/retry`
- `GET /api/v1/system/worker-health`

Stats endpoint includes message counts and `progress_percent` (processed / messages_total).
