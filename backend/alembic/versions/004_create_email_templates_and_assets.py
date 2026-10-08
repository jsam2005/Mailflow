"""create email_templates and template_assets

Revision ID: 004
Revises: 003
Create Date: 2026-10-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("html_content", sa.Text(), nullable=False),
        sa.Column("plain_text_content", sa.Text(), nullable=True),
        sa.Column("plain_text_customized", sa.Boolean(), nullable=False, server_default="false"),
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
    )
    op.create_index(op.f("ix_email_templates_user_id"), "email_templates", ["user_id"], unique=False)
    op.create_index(op.f("ix_email_templates_name"), "email_templates", ["name"], unique=False)
    op.create_index("ix_email_templates_created_at", "email_templates", ["created_at"], unique=False)

    op.create_table(
        "template_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("stored_filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("content_id", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(["template_id"], ["email_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_template_assets_user_id"), "template_assets", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_template_assets_template_id"),
        "template_assets",
        ["template_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_template_assets_template_id"), table_name="template_assets")
    op.drop_index(op.f("ix_template_assets_user_id"), table_name="template_assets")
    op.drop_table("template_assets")
    op.drop_index("ix_email_templates_created_at", table_name="email_templates")
    op.drop_index(op.f("ix_email_templates_name"), table_name="email_templates")
    op.drop_index(op.f("ix_email_templates_user_id"), table_name="email_templates")
    op.drop_table("email_templates")
