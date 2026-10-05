"""add nightly sync state to bank connections

Revision ID: c183e89c1a74
Revises: de44856f468e
Create Date: 2026-10-05 13:15:11.482333

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c183e89c1a74"
down_revision: str | Sequence[str] | None = "de44856f468e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing connections start as "never synced nightly, no failures" (spec 15).
    op.add_column(
        "bank_connections", sa.Column("nightly_synced_on", sa.Date(), nullable=True)
    )
    op.add_column(
        "bank_connections",
        sa.Column(
            "nightly_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "bank_connections",
        sa.Column("next_nightly_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "bank_connections",
        sa.Column(
            "failed_nights",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_bank_connections_failed_nights"),
        "bank_connections",
        "failed_nights >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_bank_connections_failed_nights"), "bank_connections", type_="check"
    )
    op.drop_column("bank_connections", "failed_nights")
    op.drop_column("bank_connections", "next_nightly_attempt_at")
    op.drop_column("bank_connections", "nightly_attempts")
    op.drop_column("bank_connections", "nightly_synced_on")
