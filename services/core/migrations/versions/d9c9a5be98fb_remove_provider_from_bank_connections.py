"""remove provider from bank connections

Revision ID: d9c9a5be98fb
Revises: c4ab8ce7a820
Create Date: 2026-10-23 09:12:43.160867

Specs 17a and 17b are rolled back to Plaid only. Their migrations already ran on staging
and production, so this one undoes them forward: the `provider_*` ID columns get their
`plaid_*` names back (no data moves) and the `provider` column is dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9c9a5be98fb"
down_revision: str | Sequence[str] | None = "c4ab8ce7a820"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, plaid column, provider column, plaid unique, provider unique).
RENAMES = (
    (
        "bank_accounts",
        "plaid_account_id",
        "provider_account_id",
        "uq_bank_accounts_plaid_account_id",
        "uq_bank_accounts_provider_account_id",
    ),
    (
        "bank_transactions",
        "plaid_transaction_id",
        "provider_transaction_id",
        "uq_bank_transactions_plaid_transaction_id",
        "uq_bank_transactions_provider_transaction_id",
    ),
)


def upgrade() -> None:
    """Upgrade schema. Fails if a non-Plaid connection exists, which is deliberate: the
    Plaid-only schema cannot say what its IDs mean."""
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM bank_connections WHERE provider <> 'plaid')"
        " THEN RAISE EXCEPTION 'disconnect every non-Plaid connection first'; END IF;"
        " END $$"
    )
    op.drop_constraint(
        "uq_bank_connections_business_provider_institution",
        "bank_connections",
        type_="unique",
    )
    op.drop_constraint(
        "uq_bank_connections_provider_provider_item_id",
        "bank_connections",
        type_="unique",
    )
    op.alter_column(
        "bank_connections", "provider_item_id", new_column_name="plaid_item_id"
    )
    op.alter_column(
        "bank_connections",
        "provider_institution_id",
        new_column_name="plaid_institution_id",
    )
    op.create_unique_constraint(
        "uq_bank_connections_plaid_item_id", "bank_connections", ["plaid_item_id"]
    )
    op.create_unique_constraint(
        "uq_bank_connections_business_id_plaid_institution_id",
        "bank_connections",
        ["business_id", "plaid_institution_id"],
    )
    op.drop_constraint(
        op.f("ck_bank_connections_provider"), "bank_connections", type_="check"
    )
    op.drop_column("bank_connections", "provider")

    for table, plaid, provider, plaid_uq, provider_uq in RENAMES:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {provider_uq} TO {plaid_uq}")
        op.alter_column(table, provider, new_column_name=plaid)


def downgrade() -> None:
    """Downgrade schema."""
    for table, plaid, provider, plaid_uq, provider_uq in RENAMES:
        op.alter_column(table, plaid, new_column_name=provider)
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {plaid_uq} TO {provider_uq}")

    op.add_column(
        "bank_connections",
        sa.Column(
            "provider", sa.Text(), server_default=sa.text("'plaid'"), nullable=False
        ),
    )
    op.create_check_constraint(
        op.f("ck_bank_connections_provider"),
        "bank_connections",
        "provider IN ('plaid', 'yodlee')",
    )
    op.alter_column(
        "bank_connections", "plaid_item_id", new_column_name="provider_item_id"
    )
    op.alter_column(
        "bank_connections",
        "plaid_institution_id",
        new_column_name="provider_institution_id",
    )
    op.drop_constraint(
        "uq_bank_connections_plaid_item_id", "bank_connections", type_="unique"
    )
    op.drop_constraint(
        "uq_bank_connections_business_id_plaid_institution_id",
        "bank_connections",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_bank_connections_provider_provider_item_id",
        "bank_connections",
        ["provider", "provider_item_id"],
    )
    op.create_unique_constraint(
        "uq_bank_connections_business_provider_institution",
        "bank_connections",
        ["business_id", "provider", "provider_institution_id"],
    )
