import uuid
from datetime import datetime
from typing import Any, Literal, get_args

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# The unit a preference turns on or off (spec 28): alerts (spec 29), the digest (spec 30).
EmailKind = Literal["alert", "weekly_digest"]
EMAIL_KINDS: tuple[str, ...] = get_args(EmailKind)

DeliveryState = Literal["pending", "sent", "failed", "skipped"]
DELIVERY_STATES: tuple[str, ...] = get_args(DeliveryState)


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class EmailPreferences(Base):
    """One person's email choices and their unsubscribe token. No row: both kinds on."""

    __tablename__ = "email_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), primary_key=True
    )
    alerts: Mapped[bool] = mapped_column(Boolean)
    weekly_digest: Mapped[bool] = mapped_column(Boolean)
    # Issued once and never changed: every email already sent links to it (door 3).
    unsubscribe_token: Mapped[str] = mapped_column(Text, unique=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EmailDelivery(Base):
    """One email to one user for one dedup key (door 1)."""

    __tablename__ = "email_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "dedup_key", "user_id", name="uq_email_deliveries_dedup_key_user_id"
        ),
        CheckConstraint(_one_of("state", DELIVERY_STATES), name="state"),
        CheckConstraint(_one_of("kind", EMAIL_KINDS), name="kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    dedup_key: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    template: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # The footer's first line: why this person gets this email.
    reason: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    provider_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
