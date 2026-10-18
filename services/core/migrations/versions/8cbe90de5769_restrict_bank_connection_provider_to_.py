"""restrict bank connection provider to plaid

Revision ID: 8cbe90de5769
Revises: 86276e8fa7aa
Create Date: 2026-10-17

Spec 17a's Flinks provider was removed before release, so `provider` takes only `plaid`
again. Staging already ran 86276e8fa7aa, which allowed `flinks`; no Flinks connection was
ever stored, so no row can fail this constraint.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8cbe90de5769"
down_revision: str | Sequence[str] | None = "86276e8fa7aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        op.f("ck_bank_connections_provider"), "bank_connections", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_bank_connections_provider"), "bank_connections", "provider IN ('plaid')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_bank_connections_provider"), "bank_connections", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_bank_connections_provider"),
        "bank_connections",
        "provider IN ('plaid', 'flinks')",
    )
