# MailFlow.exe (Windows desktop build)

MailFlow as a normal Windows app: no Docker, no PostgreSQL, no Node.js on the PC
that runs it. Everything is stored in local files.

## Where data lives

All data is in `%LOCALAPPDATA%\MailFlow` (for example `C:\Users\you\AppData\Local\MailFlow`):

| Path | What it is |
|------|------------|
| `mailflow.db` | SQLite database (contacts, templates, campaigns, users) |
| `storage\imports` | Uploaded contact spreadsheets |
| `storage\template-images` | Images used in email templates |
| `storage\attachments` | Campaign attachments |
| `app.env` | Settings (secrets, admin login, Google OAuth, sending switch) |

The data folder is separate from the exe, so you can replace the exe with a newer
build without losing anything. **Back up the whole `MailFlow` folder** to keep your data.

## Get the exe

**Option A: GitHub (no Windows build tools needed)**
On GitHub open **Actions → Windows exe → Run workflow**. When it finishes, download
the `MailFlow-windows` artifact from the run page and unzip it.

**Option B: build on a Windows PC** (needs Python 3.12 and Node.js 20+)

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1
```

Output: `packaging\windows\dist\MailFlow\MailFlow.exe`. Copy the whole `MailFlow` folder;
the exe needs the `_internal` folder next to it.

## Run it

1. Double-click `MailFlow.exe`. A console window opens and your browser opens
   `http://127.0.0.1:8000`.
2. On the first run the console shows the admin email and a generated password
   (also saved in `app.env`). Keep that file private.
3. Keep the console window open while you use MailFlow. Close it to stop.

Double-clicking the exe again while it is running just reopens the browser.

## Settings (`app.env`)

Stop MailFlow, edit `%LOCALAPPDATA%\MailFlow\app.env`, start it again.

- Gmail: set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. In Google Cloud, add
  `http://127.0.0.1:8000/api/v1/email-accounts/google/callback` as an authorized redirect URI.
- Sending: campaigns are not sent until you set `CAMPAIGN_SENDING_ENABLED=true`.
  Optionally limit recipients with `CAMPAIGN_TEST_RECIPIENT_ALLOWLIST=you@example.com`.

Do not change `JWT_SECRET` or `TOKEN_ENCRYPTION_KEY` after first run: connected Gmail
accounts are encrypted with that key and sessions are signed with that secret.

## Notes

- The app listens on `127.0.0.1` only, so other computers cannot reach it.
- Windows SmartScreen may warn about an unsigned app. Choose **More info → Run anyway**.
- The database schema is created on first start. A future version that changes the
  schema may need a migration step; back up the data folder before upgrading.
