"""create invitations and the bookkeeper role

Revision ID: e31b0c7a5d42
Revises: 4471d55a961b
Create Date: 2026-10-15 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e31b0c7a5d42"
down_revision: str | Sequence[str] | None = "4471d55a961b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("email_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_id"],
            ["users.id"],
            name=op.f("fk_invitations_accepted_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_invitations_business_id_businesses"),
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name=op.f("fk_invitations_invited_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitations_token_hash")),
    )
    op.create_index(
        "uq_invitations_pending_business_id_email_hash",
        "invitations",
        ["business_id", "email_hash"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL"),
    )
    op.add_column(
        "memberships",
        sa.Column(
            "receive_alert_emails",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.drop_constraint(op.f("ck_memberships_role"), "memberships", type_="check")
    op.create_check_constraint(
        op.f("ck_memberships_role"),
        "memberships",
        "role IN ('owner', 'bookkeeper')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_memberships_role"), "memberships", type_="check")
    op.create_check_constraint(
        op.f("ck_memberships_role"), "memberships", "role IN ('owner')"
    )
    op.drop_column("memberships", "receive_alert_emails")
    op.drop_index(
        "uq_invitations_pending_business_id_email_hash",
        table_name="invitations",
        postgresql_where=sa.text("accepted_at IS NULL"),
    )
    op.drop_table("invitations")
