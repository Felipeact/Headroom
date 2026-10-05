"""add cash columns to bank accounts

Revision ID: d546cee847e0
Revises: 5db30d28e759
Create Date: 2026-10-04 18:16:23.051399

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d546cee847e0"
down_revision: str | Sequence[str] | None = "5db30d28e759"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "bank_accounts", sa.Column("available_cents", sa.BigInteger(), nullable=True)
    )
    # Nullable first so existing rows can be backfilled: CAD checking counts as cash.
    op.add_column("bank_accounts", sa.Column("included", sa.Boolean(), nullable=True))
    op.execute(
        "UPDATE bank_accounts SET included = (type = 'checking' AND currency = 'CAD')"
    )
    op.alter_column("bank_accounts", "included", nullable=False)
    op.add_column(
        "bank_accounts",
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Each business's included checking account with the largest balance is primary.
    op.execute(
        "UPDATE bank_accounts SET is_primary = true WHERE id IN ("
        " SELECT DISTINCT ON (business_id) id FROM bank_accounts"
        " WHERE included AND type = 'checking'"
        " ORDER BY business_id, balance_cents DESC NULLS LAST, name, id)"
    )
    op.create_check_constraint(
        op.f("ck_bank_accounts_included_cash"),
        "bank_accounts",
        "NOT included OR (type IN ('checking', 'savings') AND currency = 'CAD')",
    )
    op.create_check_constraint(
        op.f("ck_bank_accounts_primary_included"),
        "bank_accounts",
        "NOT is_primary OR included",
    )
    op.create_index(
        "uq_bank_accounts_primary_business_id",
        "bank_accounts",
        ["business_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_bank_accounts_primary_business_id",
        table_name="bank_accounts",
        postgresql_where=sa.text("is_primary"),
    )
    op.drop_constraint(
        op.f("ck_bank_accounts_primary_included"), "bank_accounts", type_="check"
    )
    op.drop_constraint(
        op.f("ck_bank_accounts_included_cash"), "bank_accounts", type_="check"
    )
    op.drop_column("bank_accounts", "is_primary")
    op.drop_column("bank_accounts", "included")
    op.drop_column("bank_accounts", "available_cents")
