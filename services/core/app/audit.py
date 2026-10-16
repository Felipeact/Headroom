import re
import uuid
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base
from app.log import redact

# noun.past_tense_verb, the same shape as event names. Postgres enforces it too.
ACTION_PATTERN = re.compile(r"[a-z][a-z_]*\.[a-z][a-z_]*")


class AuditLog(Base):
    """One audit entry. Append-only: a Postgres trigger rejects UPDATE, DELETE and TRUNCATE."""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            r"action ~ '^[a-z][a-z_]*\.[a-z][a-z_]*$'", name="action_format"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    business_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_user_id: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, object]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )


def record(
    session: Session,
    *,
    action: str,
    business_id: uuid.UUID | None,
    actor_user_id: str | None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: Mapping[str, object] | None = None,
) -> None:
    """Add an audit entry to the caller's session; it commits or rolls back with it."""
    if not ACTION_PATTERN.fullmatch(action):
        raise ValueError(
            f"audit action must look like noun.past_tense_verb: {action!r}"
        )
    session.add(
        AuditLog(
            action=action,
            business_id=business_id,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            details=redact(details or {}),
        )
    )
    session.flush()
