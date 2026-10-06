import uuid
from datetime import date, datetime
from typing import Literal, get_args

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
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
