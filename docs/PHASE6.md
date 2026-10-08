# Phase 6 — Campaign creation & planning

## Summary

Phase 6 adds campaign drafts, recipient audience snapshots, content/account/settings configuration, preview, validation, and **Mark Ready**. **No campaign emails are sent.** Sending/queue starts in Phase 7.

## Campaign model

Table `campaigns` stores planning state:

- Statuses used: `draft`, `ready`, `cancelled`
- Reserved: `running`, `paused`, `completed`
- Links: `email_account_id`, `template_id`, `contact_list_id` (nullable until selected)
- Overrides: `subject_override`, `html_override`, `plain_text_override` (campaign-only; never mutate templates)
- Snapshots: `snapshot_subject`, `snapshot_html`, `snapshot_plain_text` (set on Mark Ready)
- Limits + `stop_on_reply` / `skip_suppressed`

## Recipient snapshot strategy

When the user confirms a contact list (`POST .../recipients/snapshot`):

1. Previous draft recipients for that campaign are deleted in the same transaction
2. All contacts from the list are classified and inserted in batches
3. The audience is **frozen** as `campaign_recipients` rows

Later changes to the source contact list do **not** change a campaign’s recipients.

Statuses in Phase 6:

| Status | Meaning |
|--------|---------|
| `pending` | Eligible to send later |
| `invalid` | Contact status invalid |
| `suppressed` | Unsubscribed, suppressed, or bounced |
| `excluded` | Other non-eligible |

Reserved later: `queued`, `sending`, `sent`, `failed`, `replied`, `unsubscribed`.

## Audience exclusion rules

Eligible only when `contact.status == active`.

Excluded as:

- `invalid` → recipient status `invalid`
- `unsubscribed` / `suppressed` / `bounced` → recipient status `suppressed`

No separate suppression_list table yet.

## Content snapshot behavior

On **Mark Ready**:

1. Resolve effective subject/HTML/plain (overrides → template)
2. Sanitize HTML
3. Store into `snapshot_*` fields
4. Freeze effective sending limits onto the campaign row

Ready previews always use snapshot content. Editing the original template afterward does not change a ready campaign.

## Draft / ready / cancelled

| Action | Behavior |
|--------|----------|
| Create | `draft` |
| Edit | Only `draft` (ready must `POST .../edit` first) |
| Delete | Hard-delete **draft** only (recipients cascade) |
| Mark ready | Validation + content/limit freeze → `ready` |
| Cancel | Ready → `cancelled` (keep recipients) |
| Return to draft | Ready → `draft`; snapshot copied into overrides for editing |

## Account / template relationships

- Account must be owned, active, and `connected` to mark ready
- Template must be owned; optional campaign overrides never write back to the template
- Foreign account/template/list/contact references are rejected (404)

## Validation rules

Errors (block ready):

- Missing name
- Missing/disconnected account
- Missing subject/content
- No recipient snapshot or zero eligible
- Invalid limits / campaign limits exceeding account caps

Warnings (non-blocking):

- Large audience
- No personalization variables
- Missing first_name/company/etc. for used variables
- Auto-generated plain text

## Sending settings inheritance

If campaign limits are unset, effective values inherit from the selected EmailAccount. Campaign values must be ≤ account safety limits.

## Preview flow

`POST /campaigns/{id}/preview` renders for a specific eligible contact (default: first). Response includes previous/next contact ids for wizard navigation without loading the full list.

## API endpoints

| Method | Path |
|--------|------|
| GET/POST | `/api/v1/campaigns` |
| GET/PUT/DELETE | `/api/v1/campaigns/{id}` |
| POST | `/api/v1/campaigns/{id}/cancel` |
| POST | `/api/v1/campaigns/{id}/edit` |
| POST | `/api/v1/campaigns/{id}/recipients/snapshot` |
| GET | `/api/v1/campaigns/{id}/recipients` |
| GET | `/api/v1/campaigns/{id}/stats` |
| POST | `/api/v1/campaigns/{id}/validate` |
| POST | `/api/v1/campaigns/{id}/ready` |
| POST | `/api/v1/campaigns/{id}/preview` |
| GET | `/api/v1/campaigns/{id}/review` |

## Frontend

- `/campaigns` — list
- `/campaigns/new`, `/campaigns/:id/edit` — wizard (details → recipients → account → content → settings → preview → review)
- `/campaigns/:id` — detail with ready banner

Draft progress is persisted to the backend between steps.

## Known limitations

- No sending, queue, scheduler, or reply handling
- `stop_on_reply` is stored only
- Performance tests use a large batch (2.5k+) rather than a full 10k live UI load; snapshot API is batch-oriented for 10k+
