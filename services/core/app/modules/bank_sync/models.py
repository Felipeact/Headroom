import uuid
from datetime import date, datetime
from typing import Literal, get_args

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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

# Who fetches a connection's data (spec 17a): Plaid, or Flinks where Plaid can't sign in.
Provider = Literal["plaid", "flinks"]
PROVIDERS: tuple[str, ...] = get_args(Provider)

TransactionLabel = Literal[
    "internal_transfer",
    "in_transit",
    "card_purchase",
    "card_payment",
    "credit_draw",
    "credit_repayment",
    "normal",
]
TRANSACTION_LABELS: tuple[str, ...] = get_args(TransactionLabel)
# The labels of a transaction paired with its other half (spec 16).
LINKED_LABELS = ("internal_transfer", "card_payment", "credit_draw", "credit_repayment")


class BankConnection(Base):
    """One login at one bank, for one business: a Plaid item or a Flinks login.

    `business_id` has no foreign key: `businesses` belongs to the accounts module.
    """

    __tablename__ = "bank_connections"
    __table_args__ = (
        CheckConstraint("failed_nights >= 0", name="failed_nights"),
        CheckConstraint(
            f"provider IN ({', '.join(repr(p) for p in PROVIDERS)})", name="provider"
        ),
        UniqueConstraint(
            "provider",
            "provider_item_id",
            name="uq_bank_connections_provider_provider_item_id",
        ),
        UniqueConstraint(
            "business_id",
            "provider",
            "provider_institution_id",
            name="uq_bank_connections_business_provider_institution",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    provider: Mapped[str] = mapped_column(
        Text, default="plaid", server_default=text("'plaid'")
    )
    # Plaid's item ID; for Flinks, the SHA-256 hex of the loginId, which is a secret.
    provider_item_id: Mapped[str] = mapped_column(Text)
    provider_institution_id: Mapped[str] = mapped_column(Text)
    institution_name: Mapped[str] = mapped_column(Text)
    # Fernet token text: Plaid's access token or the Flinks loginId; never stored plain.
    access_token_ciphertext: Mapped[str] = mapped_column(Text)
    # Plaid's /transactions/sync cursor; None until the first sync (spec 14). Always None
    # for Flinks, which has no cursor.
    transactions_cursor: Mapped[str | None] = mapped_column(Text)
    # Nightly sync state (spec 15). The business-local date of the last night whose sync
    # finished, whether it succeeded or ran out of attempts.
    nightly_synced_on: Mapped[date | None] = mapped_column(Date)
    # Failed attempts in the current night, and when the next one may run.
    nightly_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    next_nightly_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    # Consecutive nights whose sync never succeeded; any successful sync resets it.
    failed_nights: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    # The bank asked the owner to log in again (Plaid ITEM_LOGIN_REQUIRED, spec 17).
    # Cleared only by a sync that succeeds.
    login_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    # When a sync last succeeded; None until the first one (spec 17).
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    provider_account_id: Mapped[str] = mapped_column(Text, unique=True)
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


class BankTransaction(Base):
    """One bank transaction, stored once per provider transaction ID (spec 14).

    `amount_cents` is signed our way: money in is positive, money out negative.
    `label` and `linked_transaction_id` are recomputed by every sync (spec 16).
    """

    __tablename__ = "bank_transactions"
    __table_args__ = (
        CheckConstraint(
            f"label IN ({', '.join(repr(t) for t in TRANSACTION_LABELS)})",
            name="label",
        ),
        CheckConstraint(
            "linked_transaction_id IS NULL OR label IN "
            f"({', '.join(repr(t) for t in LINKED_LABELS)})",
            name="linked_label",
        ),
        CheckConstraint("linked_transaction_id <> id", name="linked_not_self"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"))
    provider_transaction_id: Mapped[str] = mapped_column(Text, unique=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date)
    pending: Mapped[bool] = mapped_column(Boolean)
    description: Mapped[str] = mapped_column(Text)
    counterparty: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    category_detailed: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str] = mapped_column(
        Text, default="normal", server_default=text("'normal'")
    )
    # The other half of a pair; both halves point at each other.
    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
