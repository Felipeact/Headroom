import uuid
from datetime import date, datetime
from typing import Literal, get_args

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

AlertState = Literal["open", "dismissed", "resolved"]
ALERT_STATES: tuple[str, ...] = get_args(AlertState)
AlertItemKind = Literal["cause", "arrives_after"]
ALERT_ITEM_KINDS: tuple[str, ...] = get_args(AlertItemKind)


class Alert(Base):
    """One cash gap of one business (spec 24, AD-095).

    `business_id` and `snapshot_id` have no foreign keys: businesses belong to the
    accounts module and snapshots to forecasting. An open or dismissed alert follows its
    gap through later forecasts (AD-096); a resolved one is never reused.
    """

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            f"state IN ({', '.join(repr(s) for s in ALERT_STATES)})", name="state"
        ),
        CheckConstraint("shortfall_cents > 0", name="shortfall_positive"),
        Index("ix_alerts_business_id_state", "business_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(Text)
    # The first gap week's Monday and the last gap week's Sunday.
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    lowest_week_starts_on: Mapped[date] = mapped_column(Date)
    lowest_balance_cents: Mapped[int] = mapped_column(BigInteger)
    minimum_cents: Mapped[int] = mapped_column(BigInteger)
    shortfall_cents: Mapped[int] = mapped_column(BigInteger)
    # The shortfall last announced or dismissed: growth is measured from it.
    notified_shortfall_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text)
    # The forecast snapshot the alert was last checked against.
    snapshot_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AlertItem(Base):
    """A payment that explains an alert; replaced as a whole on every check."""

    __tablename__ = "alert_items"
    __table_args__ = (
        CheckConstraint(
            f"kind IN ({', '.join(repr(k) for k in ALERT_ITEM_KINDS)})", name="kind"
        ),
    )

    alert_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alerts.id", ondelete="CASCADE"), primary_key=True
    )
    # Causes first, then the item arriving after the gap.
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date)
    # Our sign: money in positive, money out negative.
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    counterparty: Mapped[str | None] = mapped_column(Text)
    # The forecast item's source (AD-077's words).
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    schedule: Mapped[str | None] = mapped_column(Text)
