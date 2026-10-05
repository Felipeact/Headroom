import uuid
from datetime import datetime
from typing import Literal, get_args

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

AccountType = Literal["checking", "savings", "credit_card", "line_of_credit", "other"]
ACCOUNT_TYPES: tuple[str, ...] = get_args(AccountType)
# Only these can count as cash (AGENTS.md); credit never does, and CAD only for now.
CASH_TYPES = ("checking", "savings")
CASH_CURRENCY = "CAD"


class BankConnection(Base):
    """One Plaid item: one login at one bank, for one business.

    `business_id` has no foreign key: `businesses` belongs to the accounts module.
    """

    __tablename__ = "bank_connections"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "plaid_institution_id",
            name="uq_bank_connections_business_id_plaid_institution_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    plaid_item_id: Mapped[str] = mapped_column(Text, unique=True)
    plaid_institution_id: Mapped[str] = mapped_column(Text)
    institution_name: Mapped[str] = mapped_column(Text)
    # Fernet token text; the plaintext access token is never stored.
    access_token_ciphertext: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BankAccount(Base):
    """One account inside a connection, with the balance the bank last reported."""

    __tablename__ = "bank_accounts"
    __table_args__ = (
        CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in ACCOUNT_TYPES)})", name="type"
        ),
        CheckConstraint(
            f"NOT included OR (type IN ({', '.join(repr(t) for t in CASH_TYPES)})"
            f" AND currency = '{CASH_CURRENCY}')",
            name="included_cash",
        ),
        CheckConstraint("NOT is_primary OR included", name="primary_included"),
        Index(
            "uq_bank_accounts_primary_business_id",
            "business_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_connections.id"))
    plaid_account_id: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    mask: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text)
    # As the bank reports it: for a credit card or line of credit, the amount owed.
    balance_cents: Mapped[int | None] = mapped_column(BigInteger)
    available_cents: Mapped[int | None] = mapped_column(BigInteger)
    # The owner counts this account as cash; see `ck_bank_accounts_included_cash`.
    included: Mapped[bool] = mapped_column(Boolean, default=False)
    # At most one per business, always an included account (spec 13).
    is_primary: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
