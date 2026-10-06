"""add login and sync state to bank connections

Revision ID: bf5cd9dfe9df
Revises: b8f2b4520a41
Create Date: 2026-10-06 08:35:05.460786

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bf5cd9dfe9df"
down_revision: str | Sequence[str] | None = "b8f2b4520a41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing connections: no login problem known, never synced since spec 17 (door 1, 2).
    op.add_column(
        "bank_connections",
        sa.Column(
            "login_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "bank_connections",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("bank_connections", "last_synced_at")
    op.drop_column("bank_connections", "login_required")
