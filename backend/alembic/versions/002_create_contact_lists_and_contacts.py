"""create contact_lists and contacts tables

Revision ID: 002
Revises: 001
Create Date: 2026-10-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("total_contacts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contact_lists_user_id"), "contact_lists", ["user_id"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_list_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contact_list_id"],
            ["contact_lists.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contact_list_id",
            "normalized_email",
            name="uq_contacts_list_normalized_email",
        ),
    )
    op.create_index(op.f("ix_contacts_contact_list_id"), "contacts", ["contact_list_id"], unique=False)
    op.create_index(op.f("ix_contacts_normalized_email"), "contacts", ["normalized_email"], unique=False)
    op.create_index(op.f("ix_contacts_status"), "contacts", ["status"], unique=False)
    op.create_index(op.f("ix_contacts_company"), "contacts", ["company"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_contacts_company"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_status"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_normalized_email"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_contact_list_id"), table_name="contacts")
    op.drop_table("contacts")
    op.drop_index(op.f("ix_contact_lists_user_id"), table_name="contact_lists")
    op.drop_table("contact_lists")
