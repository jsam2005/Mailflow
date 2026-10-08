"""create campaigns and campaign recipients

Revision ID: 006
Revises: 005
Create Date: 2026-10-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("email_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contact_list_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_override", sa.String(length=255), nullable=True),
        sa.Column("html_override", sa.Text(), nullable=True),
        sa.Column("plain_text_override", sa.Text(), nullable=True),
        sa.Column("snapshot_subject", sa.String(length=255), nullable=True),
        sa.Column("snapshot_html", sa.Text(), nullable=True),
        sa.Column("snapshot_plain_text", sa.Text(), nullable=True),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("hourly_limit", sa.Integer(), nullable=True),
        sa.Column("minimum_delay_seconds", sa.Integer(), nullable=True),
        sa.Column("maximum_delay_seconds", sa.Integer(), nullable=True),
        sa.Column("stop_on_reply", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("skip_suppressed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["email_account_id"], ["email_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["email_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_list_id"], ["contact_lists.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaigns_user_id"), "campaigns", ["user_id"], unique=False)
    op.create_index(op.f("ix_campaigns_status"), "campaigns", ["status"], unique=False)
    op.create_index(
        op.f("ix_campaigns_email_account_id"),
        "campaigns",
        ["email_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaigns_contact_list_id"),
        "campaigns",
        ["contact_list_id"],
        unique=False,
    )
    op.create_index("ix_campaigns_created_at", "campaigns", ["created_at"], unique=False)

    op.create_table(
        "campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id",
            "contact_id",
            name="uq_campaign_recipients_campaign_contact",
        ),
    )
    op.create_index(
        op.f("ix_campaign_recipients_campaign_id"),
        "campaign_recipients",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_recipients_contact_id"),
        "campaign_recipients",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_recipients_status"),
        "campaign_recipients",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_campaign_recipients_status"), table_name="campaign_recipients")
    op.drop_index(op.f("ix_campaign_recipients_contact_id"), table_name="campaign_recipients")
    op.drop_index(op.f("ix_campaign_recipients_campaign_id"), table_name="campaign_recipients")
    op.drop_table("campaign_recipients")

    op.drop_index("ix_campaigns_created_at", table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_contact_list_id"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_email_account_id"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_status"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_user_id"), table_name="campaigns")
    op.drop_table("campaigns")
