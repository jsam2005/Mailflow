"""production hardening: storage fields + suppression list

Revision ID: 008
Revises: 007
Create Date: 2026-10-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "template_assets",
        sa.Column("storage_provider", sa.String(length=32), nullable=False, server_default="local"),
    )
    op.add_column(
        "template_assets",
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "template_assets",
        sa.Column("public_url", sa.String(length=2048), nullable=True),
    )
    # Backfill storage_key from legacy stored_filename
    op.execute(
        """
        UPDATE template_assets
        SET storage_key = 'template-images/' || stored_filename
        WHERE storage_key IS NULL
        """
    )

    op.create_table(
        "suppression_list",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "normalized_email", name="uq_suppression_user_email"),
    )
    op.create_index("ix_suppression_list_user_id", "suppression_list", ["user_id"])
    op.create_index("ix_suppression_list_normalized_email", "suppression_list", ["normalized_email"])

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bucket_key", sa.String(length=255), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_rate_limit_buckets_bucket_key", "rate_limit_buckets", ["bucket_key"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_bucket_key", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
    op.drop_index("ix_suppression_list_normalized_email", table_name="suppression_list")
    op.drop_index("ix_suppression_list_user_id", table_name="suppression_list")
    op.drop_table("suppression_list")
    op.drop_column("template_assets", "public_url")
    op.drop_column("template_assets", "storage_key")
    op.drop_column("template_assets", "storage_provider")
