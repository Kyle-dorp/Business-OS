"""ui config per business

Revision ID: b2e4f6a8c0d1
Revises: a1f9c3d7e2b0
"""

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "b2e4f6a8c0d1"
down_revision = "a1f9c3d7e2b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uiconfig",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("config_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id"),
    )
    op.create_index("ix_uiconfig_business_id", "uiconfig", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_uiconfig_business_id", table_name="uiconfig")
    op.drop_table("uiconfig")
