# Phase 2 — Contacts & Contact Lists

## Design decisions

### List delete behavior

Deleting a contact list **permanently deletes all contacts in that list**.

- Enforced by PostgreSQL `ON DELETE CASCADE` on `contacts.contact_list_id`
- ORM relationship uses `cascade="all, delete-orphan"`
- UI confirmation explains this before delete

### Email storage

- `email`: validated display form from `email-validator`
- `normalized_email`: trimmed + lowercased uniqueness key
- Unique per list: `(contact_list_id, normalized_email)`
- Same email may exist in different lists

### Metadata column

SQLAlchemy maps the DB column `metadata` to Python attribute `contact_metadata` (SQLAlchemy reserves `metadata` on the declarative base). API JSON still uses `"metadata"`.

### Ownership

All contact list and contact queries are scoped to `current_user.id`. Cross-user access returns **404** (not 403) to avoid resource enumeration.
