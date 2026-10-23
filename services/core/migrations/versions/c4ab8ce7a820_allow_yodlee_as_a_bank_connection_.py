"""allow yodlee as a bank connection provider

Revision ID: c4ab8ce7a820
Revises: 8cbe90de5769
Create Date: 2026-10-18

Spec 17b's Yodlee provider widens `provider` to `plaid` and `yodlee`. No row changes. The
downgrade restores `provider IN ('plaid')`, which Postgres refuses while a `yodlee` row
exists, so it fails and deletes nothing.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4ab8ce7a820"
down_revision: str | Sequence[str] | None = "8cbe90de5769"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        op.f("ck_bank_connections_provider"), "bank_connections", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_bank_connections_provider"),
        "bank_connections",
        "provider IN ('plaid', 'yodlee')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_bank_connections_provider"), "bank_connections", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_bank_connections_provider"),
        "bank_connections",
        "provider IN ('plaid')",
    )
