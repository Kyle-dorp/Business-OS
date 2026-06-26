"""sub shop bookkeeping — sales tax, card sales on closing report

Revision ID: a1f9c3d7e2b0
Revises: c42ab771e5f0
"""

from alembic import op
import sqlalchemy as sa

revision = "a1f9c3d7e2b0"
down_revision = "c42ab771e5f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("closingreport", sa.Column("card_sales_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("closingreport", sa.Column("sales_tax_cents", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("closingreport", "sales_tax_cents")
    op.drop_column("closingreport", "card_sales_cents")
