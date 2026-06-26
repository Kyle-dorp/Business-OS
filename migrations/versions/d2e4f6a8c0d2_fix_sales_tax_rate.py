"""fix sales tax rate to 6.5% (CO 2.9% + Rio Blanco County 3.6%)

Revision ID: d2e4f6a8c0d2
Revises: c1d3e5f7a9b0
"""

from alembic import op

revision = "d2e4f6a8c0d2"
down_revision = "c1d3e5f7a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE managersettings SET default_sales_tax_rate = 6.5 WHERE default_sales_tax_rate = 4.9 OR default_sales_tax_rate = 4.900000095367432")


def downgrade() -> None:
    op.execute("UPDATE managersettings SET default_sales_tax_rate = 4.9 WHERE default_sales_tax_rate = 6.5")
