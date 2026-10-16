"""add labels to bank_transactions

Revision ID: b8f2b4520a41
Revises: c183e89c1a74
Create Date: 2026-10-05 19:34:42.403177

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8f2b4520a41"
down_revision: str | Sequence[str] | None = "c183e89c1a74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LABELS = (
    "'internal_transfer', 'in_transit', 'card_purchase', 'card_payment', "
    "'credit_draw', 'credit_repayment', 'normal'"
)
LINKED_LABELS = "'internal_transfer', 'card_payment', 'credit_draw', 'credit_repayment'"


def upgrade() -> None:
    """Upgrade schema."""
    # Existing rows start as `normal`; the next sync of their business relabels them.
    op.add_column(
        "bank_transactions",
        sa.Column(
            "label", sa.Text(), server_default=sa.text("'normal'"), nullable=False
        ),
    )
    op.add_column(
        "bank_transactions",
        sa.Column("linked_transaction_id", sa.Uuid(), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_bank_transactions_linked_transaction_id"),
        "bank_transactions",
        ["linked_transaction_id"],
    )
    op.create_foreign_key(
        op.f("fk_bank_transactions_linked_transaction_id_bank_transactions"),
        "bank_transactions",
        "bank_transactions",
        ["linked_transaction_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_bank_transactions_label"), "bank_transactions", f"label IN ({LABELS})"
    )
    op.create_check_constraint(
        op.f("ck_bank_transactions_linked_label"),
        "bank_transactions",
        f"linked_transaction_id IS NULL OR label IN ({LINKED_LABELS})",
    )
    op.create_check_constraint(
        op.f("ck_bank_transactions_linked_not_self"),
        "bank_transactions",
        "linked_transaction_id <> id",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_bank_transactions_linked_not_self"), "bank_transactions", type_="check"
    )
    op.drop_constraint(
        op.f("ck_bank_transactions_linked_label"), "bank_transactions", type_="check"
    )
    op.drop_constraint(
        op.f("ck_bank_transactions_label"), "bank_transactions", type_="check"
    )
    op.drop_constraint(
        op.f("fk_bank_transactions_linked_transaction_id_bank_transactions"),
        "bank_transactions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("uq_bank_transactions_linked_transaction_id"),
        "bank_transactions",
        type_="unique",
    )
    op.drop_column("bank_transactions", "linked_transaction_id")
    op.drop_column("bank_transactions", "label")
