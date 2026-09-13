"""Add email and OAuth identity to user accounts.

This is the keystone for two features that were both blocked on the same gap:
UserAccount stored a username and nothing else, so there was no way to email a
password reset and no way to match a Google account to a user.

Adding a column to an existing table is the one thing SQLModel's create_all
cannot do for us — it only ever creates missing tables — so this has to be a
real migration.

Email is nullable and NOT unique-constrained at the database level. Existing
accounts have none, and a partial unique index would behave differently on
SQLite and PostgreSQL. Uniqueness is enforced in the application instead, where
it can return a useful message.

Revision ID: c3a71f2e9d04
Revises: b91f6a2d0137
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3a71f2e9d04"
down_revision: Union[str, Sequence[str], None] = "b91f6a2d0137"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    """Existing columns, so re-running this migration is harmless."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return set()


def upgrade() -> None:
    existing = _columns("useraccount")

    if "email" not in existing:
        op.add_column("useraccount", sa.Column("email", sa.String(), nullable=True))
        op.create_index("ix_useraccount_email", "useraccount", ["email"])

    if "email_verified" not in existing:
        op.add_column(
            "useraccount",
            sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    # Which external identity provider owns this account, if any. "password"
    # means local credentials. Stored rather than inferred so an account linked
    # to Google cannot silently fall back to password auth.
    if "auth_provider" not in existing:
        op.add_column(
            "useraccount",
            sa.Column("auth_provider", sa.String(), nullable=False, server_default="password"),
        )

    # The provider's stable user id. Google's `sub` claim, specifically — never
    # the email, which a user can change.
    if "provider_subject" not in existing:
        op.add_column("useraccount", sa.Column("provider_subject", sa.String(), nullable=True))
        op.create_index("ix_useraccount_provider_subject", "useraccount", ["provider_subject"])


def downgrade() -> None:
    existing = _columns("useraccount")

    for index, column in (
        ("ix_useraccount_provider_subject", "provider_subject"),
        (None, "auth_provider"),
        (None, "email_verified"),
        ("ix_useraccount_email", "email"),
    ):
        if column in existing:
            if index:
                try:
                    op.drop_index(index, table_name="useraccount")
                except Exception:
                    pass
            op.drop_column("useraccount", column)
