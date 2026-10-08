# Gmail OAuth setup for MailFlow

MailFlow connects Gmail with **OAuth 2.0 only**. Never enter a Gmail password into MailFlow.

## Scopes requested (Phase 5)

| Scope | Purpose |
|-------|---------|
| `openid` | OpenID Connect |
| `https://www.googleapis.com/auth/userinfo.email` | Identify the connected Gmail address |
| `https://www.googleapis.com/auth/userinfo.profile` | Optional display name |
| `https://www.googleapis.com/auth/gmail.send` | Send test emails via Gmail API |

**Not requested:** mailbox read, modify, full Gmail access. Reply-tracking scopes will be added in a later phase.

## Step-by-step Google Cloud configuration

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or select an existing one).
3. Enable **Gmail API** (APIs & Services → Library → Gmail API → Enable).
4. Configure the **OAuth consent screen**:
   - User type: External (typical for personal Gmail) or Internal (Workspace-only).
   - App name: MailFlow (or your preference).
   - Add your email as developer contact.
   - Scopes: add the four scopes listed above (or let the app request them at runtime).
5. If the app is in **Testing** mode, add every Gmail address you will connect under **Test users**.
6. Create credentials → **OAuth client ID**.
7. Application type: **Web application**.
8. Authorized redirect URI:

   ```text
   http://localhost:8000/api/v1/email-accounts/google/callback
   ```

9. Copy the **Client ID**.
10. Copy the **Client secret**.
11. Put values in your backend `.env` (never commit real values):

    ```env
    GOOGLE_CLIENT_ID=...
    GOOGLE_CLIENT_SECRET=...
    GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/email-accounts/google/callback
    FRONTEND_URL=http://localhost:5173
    TOKEN_ENCRYPTION_KEY=...
    ```

12. Generate `TOKEN_ENCRYPTION_KEY`:

    ```bash
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```

13. Start the backend (`alembic upgrade head` then `uvicorn`).
14. Open MailFlow → **Email Accounts** → **Connect Gmail**.
15. Complete Google consent and return to MailFlow.

## Testing / production consent modes

During development Google often keeps the OAuth app in **Testing**. Only test users listed on the consent screen can connect. Promote to production when you complete Google’s verification requirements. Do not hardcode environment assumptions into application code.

## Common OAuth errors

| Symptom | Likely cause |
|---------|--------------|
| `redirect_uri_mismatch` | Redirect URI in Cloud Console does not exactly match `GOOGLE_REDIRECT_URI` |
| `access_denied` | User cancelled consent, or address not added as a test user |
| No refresh token | Previously granted access without `prompt=consent`; revoke MailFlow in Google Account → Security → Third-party access, then reconnect |
| `invalid_client` | Wrong client ID/secret |
| Callback lands with `?error=oauth_failed` | Invalid/expired/reused state, token exchange failure, or missing profile email |

## Security notes

- OAuth access and refresh tokens are encrypted at rest with Fernet (`TOKEN_ENCRYPTION_KEY`).
- Tokens are never returned to the frontend or written to logs.
- OAuth `state` is stored hashed server-side, bound to the initiating user, single-use, and expires (~10 minutes).
