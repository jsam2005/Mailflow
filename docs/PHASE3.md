# Phase 3 — Contact dataset import

## Supported formats

- `.csv` (UTF-8 / UTF-8 BOM, latin-1 fallback)
- `.xlsx` (first sheet by default; multi-sheet selection supported)
- Max size: `MAX_IMPORT_FILE_MB` (default **10**)
- Legacy `.xls` is not supported

## Import lifecycle

`uploaded` → `validated` → `importing` → `completed`

Also: `cancelled`, `failed`

Uploaded files are retained under `storage/imports/` with UUID filenames. Original names are metadata only.

## Mapping

- Email mapping is required
- Exclusive targets: email, first/last/full name, company, phone, website
- Custom Field columns are stored in `contacts.metadata` JSON
- Ignore drops a column
- Full Name splits as: first token → `first_name`, remainder → `last_name`

## Email rules

Uses the same `email-validator` path as manual contact creation.

- Trim + normalize
- No SMTP / mailbox probing

## Duplicates

1. **In file:** first valid occurrence importable; later rows skipped
2. **Existing in list:** batched lookup by `normalized_email`; skipped
3. Same email in a **different list** is allowed

## Validation totals

Categories are mutually exclusive for a given row:

- missing email
- invalid email
- duplicate in file
- duplicate existing
- importable

`skipped_rows = missing + invalid + dup_file + dup_existing`

## API

| Method | Path |
|--------|------|
| POST | `/api/v1/imports/upload` |
| GET | `/api/v1/imports` |
| GET | `/api/v1/imports/{id}` |
| GET | `/api/v1/imports/{id}/preview` |
| POST | `/api/v1/imports/{id}/validate` |
| POST | `/api/v1/imports/{id}/execute` |
| POST | `/api/v1/imports/{id}/cancel` |

## Performance (local smoke)

Synthetic CSV with **10,000** rows (not committed):

- Parse ≈ **0.07s**
- Validate ≈ **0.32s**
- Importable count matched expected total

Frontend only receives preview (≤20 rows) and issue samples (≤100 / category).

## Known limitations

- Only values are read from XLSX (`data_only=True`); formulas are not evaluated
- Entire dataset is parsed in memory for validation (fine for ~10k rows MVP)
- Password-protected workbooks are rejected with a friendly error
