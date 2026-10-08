# Google OAuth production / verification readiness

MailFlow is **not** automatically Google-verified. Complete Google’s process before inviting non-test users.

## App identity (fill with your real details)

| Field | Value |
|-------|--------|
| App name | MailFlow (or your brand) |
| Homepage | `https://YOUR_DOMAIN` |
| Privacy Policy | `PRIVACY_POLICY_URL` |
| Terms of Service | `TERMS_URL` |
| Authorized domain | `YOUR_DOMAIN` |
| OAuth client type | Web application |
| Redirect URI | `https://YOUR_DOMAIN/api/v1/email-accounts/google/callback` |

## Scopes requested

- `openid`
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/userinfo.profile`
- `https://www.googleapis.com/auth/gmail.send`

**Why `gmail.send`:** MailFlow sends campaign and test emails through the user’s connected Gmail account. It does **not** request mailbox read scopes in this phase.

## Testing mode checklist

- [ ] OAuth consent screen configured
- [ ] Gmail API enabled
- [ ] Every connecting address listed under **Test users**
- [ ] Production redirect URI added exactly
- [ ] `GOOGLE_*` env vars set on Vercel

## Verification preparation

- [ ] Privacy Policy URL live
- [ ] Terms URL live
- [ ] Demo video / screenshots of Connect Gmail + Send Test Email
- [ ] Explanation of limited sensitive scope usage
- [ ] Support email monitored

Do not claim the app is verified until Google completes review.
