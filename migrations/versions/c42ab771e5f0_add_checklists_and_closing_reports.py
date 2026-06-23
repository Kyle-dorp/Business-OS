"""add checklists and closing reports

Revision ID: c42ab771e5f0
Revises: b91f6a2d0137
"""

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "c42ab771e5f0"
down_revision = "b91f6a2d0137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("checklisttemplate",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("items_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("created_at", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_checklisttemplate_business_id", "checklisttemplate", ["business_id"])
    op.create_table("checklistrun",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("business_id", sa.Integer(), nullable=False), sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("run_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("items_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("completed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("completed_at", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.PrimaryKeyConstraint("id"))
    for column in ("business_id", "template_id", "run_date", "created_by_user_id", "completed_by_user_id"):
        op.create_index(f"ix_checklistrun_{column}", "checklistrun", [column])
    op.create_table("closingreport",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("business_id", sa.Integer(), nullable=False), sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("report_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("sales_cents", sa.Integer(), nullable=False),
        sa.Column("cash_expected_cents", sa.Integer(), nullable=False), sa.Column("cash_actual_cents", sa.Integer(), nullable=False),
        sa.Column("labor_cost_cents", sa.Integer(), nullable=False), sa.Column("waste_cents", sa.Integer(), nullable=False),
        sa.Column("issues", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=False), sa.Column("created_at", sqlmodel.sql.sqltypes.AutoString(), nullable=False), sa.PrimaryKeyConstraint("id"))
    for column in ("business_id", "location_id", "report_date", "submitted_by_user_id"):
        op.create_index(f"ix_closingreport_{column}", "closingreport", [column])


def downgrade() -> None:
    op.drop_table("closingreport")
    op.drop_table("checklistrun")
    op.drop_table("checklisttemplate")
