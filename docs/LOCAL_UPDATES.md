# Local MailFlow updates (GitHub → client launcher)

This document covers publishing an update from a development machine and installing it on a client via the local launcher.

## Data that stays put

These live in the **install root** and are **never overwritten** by an update package:

| Item | Location |
|------|----------|
| Secrets / config | `.env`, `backend/.env` |
| Uploads / assets | `storage/`, `backend/storage/` |
| Update metadata / backups | `.mailflow/` |
| Postgres data | Docker volume (`docker compose`) |

`TOKEN_ENCRYPTION_KEY` in `.env` must remain unchanged so stored Gmail OAuth tokens stay readable.

Updates **do not** enable `CAMPAIGN_SENDING_ENABLED` or billing.

## Client update config

On first check, the launcher creates:

```text
.mailflow/update-config.json
```

```json
{
  "github_owner": "jsam2005",
  "github_repo": "Mailflow",
  "release_ref": "main",
  "remote_url": "https://github.com/jsam2005/Mailflow.git"
}
```

- **`release_ref`**: branch (`main`) or a publish tag (`mailflow-YYYYMMDD-HHMMSS`).
- Clients originally installed from a **ZIP** can still update: the updater downloads a GitHub zipball of the target commit when `git fetch` is unavailable.
- Put Git credentials in the OS / git credential helper if the repo is private. **Never** put tokens in HTML, committed files, or launcher logs.

## Publishing (development)

Intentional only — nothing auto-commits your whole working tree.

```bash
# Already committed and tested:
python scripts/publish-mailflow-update.py --tag-only --message "Describe the client-facing fix"

# Or commit only selected paths, validate, tag, push (no force):
python scripts/publish-mailflow-update.py \
  --paths launcher docs/LOCAL_UPDATES.md scripts/publish-mailflow-update.py \
  --message "Describe the client-facing fix"
```

Creates an annotated tag `mailflow-YYYYMMDD-HHMMSS` and pushes branch + tag.

Clients tracking `main` pick up the tip. To pin a release, set client `release_ref` to that tag.

Excluded automatically from publish paths: `.env`, venvs, `node_modules`, storage, secrets, `.mailflow` runtime.

## Installing on a client

1. Start the launcher (`MailFlow.command` or `Start-MailFlow-Windows.cmd`).
2. Click **Check for updates**.
3. Review installed vs available commit.
4. Click **Update now** and confirm.

What the updater does:

1. Refuses if a git checkout has **local source modifications** (recovery: stash/commit/copy edits first).
2. Downloads into `.mailflow/releases/<sha>/` (not a blind `git pull` in the live tree).
3. Installs lockfile deps and builds in staging.
4. Stops **launcher-owned** services (graceful API/scheduler shutdown).
5. Backs up `.env` copies + `pg_dump` into `.mailflow/backups/update-…/` and verifies the dump.
6. Runs `alembic upgrade head` **once** against localhost using existing env (sending forced off).
7. Copies new application files into the install root **excluding** preserved paths.
8. Reinstalls runtime deps, restarts, verifies readiness.

## Failure / recovery (honest limits)

| Failure point | Behavior |
|---------------|----------|
| Download / build before migration | Previous install left usable; no schema change |
| Backup failed | Update aborted; no migration; no file switch |
| Migration failed | Files not switched; backup retained; fix forward |
| Startup failed **after** migration | Files already switched; schema may be newer. **Do not** blindly restore an old dump if the new app may have written data. Keep backup; see recovery below |

**There is no absolute zero data-loss guarantee.** A crash mid-write, disk failure, or restoring an old dump over newer rows can lose or duplicate data. Backups reduce risk; they do not eliminate it.

### Manual recovery (tested procedure outline)

1. Read `.mailflow/update-state.json` and the latest `.mailflow/backups/update-*/backup-meta.json`.
2. If migration **did not** run: fix the error and retry **Update now**, or keep using the previous install.
3. If migration **did** run and the new app will not start:
   - Prefer fixing forward (deps, missing env keys documented in release notes).
   - Restoring `mailflow.dump` is a last resort into a **new** database name for inspection, not an automatic overwrite of a live DB that may have newer writes.
4. Re-check that `.env` `TOKEN_ENCRYPTION_KEY` is unchanged before expecting Gmail tokens to decrypt.

Queued campaign messages and lease/uncertain-delivery rules are preserved; updates never auto-retry uncertain sends as successful.

## ZIP installs

1. First install via Setup scripts / ZIP extract as documented.
2. Ensure network access to GitHub.
3. Use launcher Check / Update (zipball path).
4. Keep `.env` and Docker volumes intact across updates.

## Security

- Loopback-only control API with session token + Origin checks.
- Allowlisted actions only (`check` / `apply` plus existing start/stop/open).
- Update lock file prevents overlapping updates across clicks/restarts.
