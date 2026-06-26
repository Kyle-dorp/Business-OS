"""default sales tax rate on manager settings

Revision ID: c1d3e5f7a9b0
Revises: b2e4f6a8c0d1
"""

from alembic import op
import sqlalchemy as sa

revision = "c1d3e5f7a9b0"
down_revision = "b2e4f6a8c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Colorado state 2.9% + Rio Blanco County 2.0% = 4.9% base
    op.add_column("managersettings", sa.Column("default_sales_tax_rate", sa.Float(), server_default="4.9", nullable=False))


def downgrade() -> None:
    op.drop_column("managersettings", "default_sales_tax_rate")
