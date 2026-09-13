"""Add deposit policy to services and no-show tracking to bookings.

No-show protection is the one place a dedicated booking tool still genuinely
beats this product. Two pieces are needed and neither fits in an existing
column: a per-service deposit policy, and somewhere to record that a booking
was not honoured.

Revision ID: d8b24c1a7f36
Revises: c3a71f2e9d04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8b24c1a7f36"
down_revision: Union[str, Sequence[str], None] = "c3a71f2e9d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    try:
        return {c["name"] for c in sa.inspect(bind).get_columns(table)}
    except Exception:
        return set()


def upgrade() -> None:
    service = _columns("service")

    if "requires_deposit" not in service:
        op.add_column(
            "service",
            sa.Column("requires_deposit", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    # Stored in cents like the rest of the money in this schema. Service.price
    # is a float for historical reasons; new money columns do not repeat that.
    if "deposit_cents" not in service:
        op.add_column(
            "service",
            sa.Column("deposit_cents", sa.Integer(), nullable=False, server_default="0"),
        )
    # How long before the slot a customer may cancel without forfeiting.
    if "cancellation_hours" not in service:
        op.add_column(
            "service",
            sa.Column("cancellation_hours", sa.Integer(), nullable=False, server_default="24"),
        )

    booking = _columns("booking")

    if "no_show_at" not in booking:
        op.add_column("booking", sa.Column("no_show_at", sa.String(), nullable=True))
    if "cancelled_at" not in booking:
        op.add_column("booking", sa.Column("cancelled_at", sa.String(), nullable=True))
    if "deposit_cents" not in booking:
        op.add_column(
            "booking",
            sa.Column("deposit_cents", sa.Integer(), nullable=False, server_default="0"),
        )
    # Held until the appointment happens, then either applied to the bill or
    # forfeited. Recorded separately from payment_status, which tracks the
    # balance rather than the deposit.
    if "deposit_status" not in booking:
        op.add_column(
            "booking",
            sa.Column("deposit_status", sa.String(), nullable=False, server_default="none"),
        )


def downgrade() -> None:
    for table, column in (
        ("booking", "deposit_status"),
        ("booking", "deposit_cents"),
        ("booking", "cancelled_at"),
        ("booking", "no_show_at"),
        ("service", "cancellation_hours"),
        ("service", "deposit_cents"),
        ("service", "requires_deposit"),
    ):
        if column in _columns(table):
            op.drop_column(table, column)
