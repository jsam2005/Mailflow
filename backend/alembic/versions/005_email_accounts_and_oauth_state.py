"""email accounts and oauth state

Revision ID: 005
Revises: 004
Create Date: 2026-10-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("provider_account_id", sa.String(length=255), nullable=True),
        sa.Column("oauth_access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("oauth_refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("oauth_token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "oauth_scope",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("daily_send_limit", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("hourly_send_limit", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("minimum_delay_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("maximum_delay_seconds", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("sent_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_current_hour", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_daily_reset_date", sa.Date(), nullable=True),
        sa.Column("last_hourly_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connection_status", sa.String(length=32), nullable=False),
        sa.Column("last_connection_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_connection_error", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "email_address",
            name="uq_email_accounts_user_provider_email",
        ),
    )
    op.create_index(op.f("ix_email_accounts_user_id"), "email_accounts", ["user_id"], unique=False)
    op.create_index(op.f("ix_email_accounts_provider"), "email_accounts", ["provider"], unique=False)
    op.create_index(
        op.f("ix_email_accounts_email_address"),
        "email_accounts",
        ["email_address"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_accounts_connection_status"),
        "email_accounts",
        ["connection_status"],
        unique=False,
    )

    op.create_table(
        "oauth_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oauth_states_user_id"), "oauth_states", ["user_id"], unique=False)
    op.create_index(op.f("ix_oauth_states_provider"), "oauth_states", ["provider"], unique=False)
    op.create_index(op.f("ix_oauth_states_state_hash"), "oauth_states", ["state_hash"], unique=True)

    op.create_table(
        "email_test_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("provider_thread_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_account_id"], ["email_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["email_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_test_logs_user_id"), "email_test_logs", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_email_test_logs_email_account_id"),
        "email_test_logs",
        ["email_account_id"],
        unique=False,
    )
    op.create_index(op.f("ix_email_test_logs_status"), "email_test_logs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_test_logs_status"), table_name="email_test_logs")
    op.drop_index(op.f("ix_email_test_logs_email_account_id"), table_name="email_test_logs")
    op.drop_index(op.f("ix_email_test_logs_user_id"), table_name="email_test_logs")
    op.drop_table("email_test_logs")

    op.drop_index(op.f("ix_oauth_states_state_hash"), table_name="oauth_states")
    op.drop_index(op.f("ix_oauth_states_provider"), table_name="oauth_states")
    op.drop_index(op.f("ix_oauth_states_user_id"), table_name="oauth_states")
    op.drop_table("oauth_states")

    op.drop_index(op.f("ix_email_accounts_connection_status"), table_name="email_accounts")
    op.drop_index(op.f("ix_email_accounts_email_address"), table_name="email_accounts")
    op.drop_index(op.f("ix_email_accounts_provider"), table_name="email_accounts")
    op.drop_index(op.f("ix_email_accounts_user_id"), table_name="email_accounts")
    op.drop_table("email_accounts")
