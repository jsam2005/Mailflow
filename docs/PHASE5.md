# Phase 5 — Email account configuration (Gmail)

## Summary

Phase 5 adds production-quality Gmail account connection via OAuth 2.0: encrypted token storage, refresh, connection health, MailFlow safety limits, and a single manually triggered test email (including CID inline images from templates). Campaign sending is **not** included.

## EmailAccount architecture

Table `email_accounts` stores one row per connected provider mailbox per MailFlow user.

- Unique: `(user_id, provider, email_address)`
- Connection statuses: `connected`, `expired`, `error`, `disconnected`
- Soft disconnect: tokens cleared, status `disconnected`, `is_active=false`; historical row retained
- Reconnect OAuth updates the same row

Related tables:

- `oauth_states` — CSRF state (hashed), expiry, one-time use
- `email_test_logs` — manual test-send outcomes (no bodies/tokens)

## OAuth flow

1. Authenticated `POST /api/v1/email-accounts/google/connect` creates an `oauth_states` row and returns `authorization_url`.
2. Browser redirects to Google.
3. Google hits `GET /api/v1/email-accounts/google/callback?code&state` (no JWT; user comes from state).
4. Backend validates state, exchanges code, loads profile, encrypts tokens, upserts `email_accounts`.
5. Redirect to `FRONTEND_URL/email-accounts?connected=1` (or `?error=oauth_failed`).

## OAuth state security

- Cryptographically random state; only SHA-256 hash stored
- Bound to initiating `user_id`
- TTL ~10 minutes (`OAUTH_STATE_TTL_MINUTES`)
- Rejected when missing, expired, reused, or mismatched
- Callback never trusts a user id from the query string

## Token encryption

- Service: `TokenEncryptionService` (Fernet)
- Env: `TOKEN_ENCRYPTION_KEY`
- Startup fails in non-test environments if the key is missing/invalid
- API responses never include plaintext or ciphertext tokens

## Scopes

See [GMAIL_SETUP.md](./GMAIL_SETUP.md). Send + identity only; no mailbox read.

## Token refresh

Before Gmail API calls, if access token is expired or within ~2 minutes of expiry, MailFlow refreshes using the encrypted refresh token, re-encrypts the new access token, and updates expiry. Refresh failure → `connection_status=expired` and a reconnect message. No retry loops.

## Disconnect behavior

`DELETE /api/v1/email-accounts/{id}`:

1. Attempt Google token revocation
2. Clear encrypted tokens
3. Set `disconnected` / `is_active=false`
4. Keep the account row for history

## Account limits

User-configurable MailFlow safety limits:

- `daily_send_limit`, `hourly_send_limit`
- `minimum_delay_seconds`, `maximum_delay_seconds`

Validated so hourly ≤ daily and max delay ≥ min delay. These do **not** raise Gmail’s provider caps. Campaign enforcement comes in later phases; Phase 5 stores the settings.

## Test sending

`POST /api/v1/email-accounts/{id}/send-test`

- Exactly one message per request
- Modes: `simple` or `template` (optional `contact_id` personalization)
- Defaults: subject `MailFlow test email`, body `This is a test email sent from MailFlow.`
- Rate limit: `TEST_EMAIL_HOURLY_LIMIT` (default 10) per account → HTTP 429
- Uses Gmail API `users.messages.send` (not SMTP)

## CID images

`EmailMessageBuilder` finds `data-mailflow-asset-id`, verifies ownership, loads the file from storage, attaches inline MIME parts, and rewrites `src` to `cid:<content_id>`.

## Provider abstraction

`EmailProvider` interface with `GmailProvider` implementation. Future: Outlook, SMTP, SendGrid, SES — no Gmail logic in route handlers.

## API endpoints

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/email-accounts` | JWT |
| GET | `/api/v1/email-accounts/{id}` | JWT |
| PUT | `/api/v1/email-accounts/{id}` | JWT |
| DELETE | `/api/v1/email-accounts/{id}` | JWT |
| POST | `/api/v1/email-accounts/google/connect` | JWT |
| GET | `/api/v1/email-accounts/google/callback` | Public (state-bound) |
| POST | `/api/v1/email-accounts/{id}/test-connection` | JWT |
| POST | `/api/v1/email-accounts/{id}/send-test` | JWT |
| POST | `/api/v1/email-accounts/{id}/reconnect` | JWT |

## Frontend

Route: `/email-accounts` (sidebar **Email Accounts**; `/accounts` redirects).

Features: connect/reconnect OAuth redirect, status badges, settings modal, test connection, send-test modal (simple + template preview), disconnect confirmation, OAuth query toasts.

## Known limitations

- Gmail only in Phase 5
- No campaign queue, scheduling, inbox, or reply sync
- Live OAuth requires Google Cloud credentials and (often) test users
- Automated tests mock Google APIs; they do not prove live inbox delivery

## Migration

`005_email_accounts_and_oauth_state` creates `email_accounts`, `oauth_states`, and `email_test_logs`.
