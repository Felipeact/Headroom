"""add provider to bank connections

Revision ID: 86276e8fa7aa
Revises: e31b0c7a5d42
Create Date: 2026-10-16 18:59:05.057790

Spec 17a: a connection's data comes from Plaid or Flinks. The `plaid_*` ID columns are
renamed in place (no data moves), and every existing connection becomes `plaid`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "86276e8fa7aa"
down_revision: str | Sequence[str] | None = "e31b0c7a5d42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, old column, new column, old unique, new unique) for the single-column uniques.
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
    """Upgrade schema."""
    for table, old, new, old_uq, new_uq in RENAMES:
        op.alter_column(table, old, new_column_name=new)
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old_uq} TO {new_uq}")

    op.add_column(
        "bank_connections",
        sa.Column(
            "provider", sa.Text(), server_default=sa.text("'plaid'"), nullable=False
        ),
    )
    op.create_check_constraint(
        op.f("ck_bank_connections_provider"),
        "bank_connections",
        "provider IN ('plaid', 'flinks')",
    )
    op.alter_column(
        "bank_connections", "plaid_item_id", new_column_name="provider_item_id"
    )
    op.alter_column(
        "bank_connections",
        "plaid_institution_id",
        new_column_name="provider_institution_id",
    )
    # The item and institution uniques widen to include the provider; existing rows are
    # all `plaid`, so neither can fail on them.
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


def downgrade() -> None:
    """Downgrade schema. Fails if a Flinks connection exists, which is deliberate: the old
    schema cannot say what its IDs mean."""
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM bank_connections WHERE provider <> 'plaid')"
        " THEN RAISE EXCEPTION 'disconnect every Flinks connection first'; END IF; END $$"
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

    for table, old, new, old_uq, new_uq in RENAMES:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {new_uq} TO {old_uq}")
        op.alter_column(table, new, new_column_name=old)
