"""add configurable departments

Revision ID: b91f6a2d0137
Revises: fa85cd14eb04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "b91f6a2d0137"
down_revision: Union[str, Sequence[str], None] = "fa85cd14eb04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "department",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_department_business_id", "department", ["business_id"])
    op.create_index("ix_department_name", "department", ["name"])


def downgrade() -> None:
    op.drop_index("ix_department_name", table_name="department")
    op.drop_index("ix_department_business_id", table_name="department")
    op.drop_table("department")
