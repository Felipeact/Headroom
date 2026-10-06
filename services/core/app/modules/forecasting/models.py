import datetime as dt
import uuid
from datetime import date, datetime
from typing import Literal, get_args

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

Schedule = Literal["weekly", "biweekly", "semimonthly", "monthly", "quarterly"]
SCHEDULE_NAMES: tuple[str, ...] = get_args(Schedule)


class RecurringPattern(Base):
    """A payment that repeats on a schedule, detected from the bank history (spec 19).

    `business_id`, `account_id` and `transaction_ids` have no foreign keys: accounts and
    transactions belong to the bank_sync module. A business's patterns are replaced as a
    whole set on every refresh, so IDs are not stable across refreshes.
    """

    __tablename__ = "recurring_patterns"
    __table_args__ = (
        CheckConstraint(
            f"schedule IN ({', '.join(repr(s) for s in SCHEDULE_NAMES)})",
            name="schedule",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 100", name="confidence"),
        CheckConstraint("amount_cents <> 0", name="amount_nonzero"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    counterparty: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    schedule: Mapped[str] = mapped_column(Text)
    # Our sign: money in positive, money out negative.
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text)
    next_date: Mapped[date] = mapped_column(Date)
    confidence: Mapped[int] = mapped_column(SmallInteger)
    # The transactions the pattern came from, oldest first.
    transaction_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# How an expected payment repeats; None (a null column) means it happens once.
Repeats = Literal["weekly", "biweekly", "monthly", "quarterly"]
REPEATS_NAMES: tuple[str, ...] = get_args(Repeats)


class ExpectedPayment(Base):
    """A payment the owner says is coming, once or on a repeat schedule (spec 20, AD-073).

    `business_id` and `account_id` have no foreign keys: accounts belong to bank_sync.
    `date` is the first occurrence.
    """

    __tablename__ = "expected_payments"
    __table_args__ = (
        CheckConstraint(
            f"repeats IN ({', '.join(repr(r) for r in REPEATS_NAMES)})",
            name="repeats",
        ),
        CheckConstraint("amount_cents <> 0", name="amount_nonzero"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    description: Mapped[str] = mapped_column(Text)
    # Our sign: money in positive, money out negative.
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text)
    # `dt.date`: inside this class body, `date` names the column.
    date: Mapped[dt.date] = mapped_column(Date)
    repeats: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExpectedPaymentMatch(Base):
    """A real transaction matched to one occurrence of an expected payment (AD-074).

    A business's matches are replaced as a whole set whenever its payments or its
    transactions change. `transaction_id` has no foreign key: transactions belong to
    bank_sync.
    """

    __tablename__ = "expected_payment_matches"

    expected_payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("expected_payments.id", ondelete="CASCADE"), primary_key=True
    )
    occurrence_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
