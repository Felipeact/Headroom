"""create bank transactions

Revision ID: de44856f468e
Revises: d546cee847e0
Create Date: 2026-10-05 12:10:49.343749

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "de44856f468e"
down_revision: str | Sequence[str] | None = "d546cee847e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("plaid_transaction_id", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("pending", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("counterparty", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("category_detailed", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["bank_accounts.id"],
            name=op.f("fk_bank_transactions_account_id_bank_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_transactions")),
        sa.UniqueConstraint(
            "plaid_transaction_id",
            name=op.f("uq_bank_transactions_plaid_transaction_id"),
        ),
    )
    op.add_column(
        "bank_connections", sa.Column("transactions_cursor", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("bank_connections", "transactions_cursor")
    op.drop_table("bank_transactions")
