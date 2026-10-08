"""email messages and delivery fields

Revision ID: 007
Revises: 006
Create Date: 2026-10-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "email_accounts",
        sa.Column("next_send_allowed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("to_name", sa.String(length=512), nullable=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=False),
        sa.Column("rendered_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("provider_thread_id", sa.String(length=255), nullable=True),
        sa.Column("rfc_message_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["campaign_recipient_id"],
            ["campaign_recipients.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_account_id"], ["email_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_recipient_id",
            name="uq_email_messages_campaign_recipient",
        ),
    )
    op.create_index(op.f("ix_email_messages_user_id"), "email_messages", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_email_messages_campaign_id"),
        "email_messages",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(op.f("ix_email_messages_status"), "email_messages", ["status"], unique=False)
    op.create_index(
        op.f("ix_email_messages_email_account_id"),
        "email_messages",
        ["email_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_messages_next_attempt_at"),
        "email_messages",
        ["next_attempt_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_messages_sent_at"),
        "email_messages",
        ["sent_at"],
        unique=False,
    )
    op.create_index(
        "ix_email_messages_status_next_attempt",
        "email_messages",
        ["status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_email_messages_account_status",
        "email_messages",
        ["email_account_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_email_messages_campaign_status",
        "email_messages",
        ["campaign_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_messages_campaign_status", table_name="email_messages")
    op.drop_index("ix_email_messages_account_status", table_name="email_messages")
    op.drop_index("ix_email_messages_status_next_attempt", table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_sent_at"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_next_attempt_at"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_email_account_id"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_status"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_campaign_id"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_user_id"), table_name="email_messages")
    op.drop_table("email_messages")

    op.drop_column("email_accounts", "next_send_allowed_at")
    op.drop_column("campaigns", "last_activity_at")
    op.drop_column("campaigns", "completed_at")
    op.drop_column("campaigns", "paused_at")
    op.drop_column("campaigns", "started_at")
