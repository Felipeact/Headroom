import secrets
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.notifications.models import EmailDelivery, EmailPreferences


def preferences(session: Session, user_id: uuid.UUID) -> EmailPreferences | None:
    return session.get(EmailPreferences, user_id)


def save_preferences(
    session: Session, *, user_id: uuid.UUID, alerts: bool, weekly_digest: bool
) -> None:
    session.execute(
        insert(EmailPreferences)
        .values(
            user_id=user_id,
            alerts=alerts,
            weekly_digest=weekly_digest,
            unsubscribe_token=secrets.token_urlsafe(32),
        )
        .on_conflict_do_update(
            index_elements=[EmailPreferences.user_id],
            set_={
                "alerts": alerts,
                "weekly_digest": weekly_digest,
                "updated_at": func.now(),
            },
        )
    )


def ensure_token(session: Session, user_id: uuid.UUID) -> str:
    """The user's unsubscribe token, creating their row (both kinds on) on first need."""
    session.execute(
        insert(EmailPreferences)
        .values(
            user_id=user_id,
            alerts=True,
            weekly_digest=True,
            unsubscribe_token=secrets.token_urlsafe(32),
        )
        .on_conflict_do_nothing(index_elements=[EmailPreferences.user_id])
    )
    return session.scalars(
        select(EmailPreferences.unsubscribe_token).where(
            EmailPreferences.user_id == user_id
        )
    ).one()


def unsubscribe(session: Session, token: str) -> bool:
    """Turn every kind off for the token's user; False when no user has the token."""
    session.execute(
        update(EmailPreferences)
        .where(
            EmailPreferences.unsubscribe_token == token,
            or_(EmailPreferences.alerts, EmailPreferences.weekly_digest),
        )
        .values(alerts=False, weekly_digest=False, updated_at=func.now())
    )
    return (
        session.scalar(
            select(EmailPreferences.user_id).where(
                EmailPreferences.unsubscribe_token == token
            )
        )
        is not None
    )


def insert_delivery(
    session: Session,
    *,
    dedup_key: str,
    user_id: uuid.UUID,
    business_id: uuid.UUID,
    kind: str,
    template: str,
    params: Mapping[str, Any],
    reason: str,
    state: str,
) -> uuid.UUID | None:
    """Insert the delivery; None when one exists for (dedup_key, user) already (door 1)."""
    return session.scalar(
        insert(EmailDelivery)
        .values(
            id=uuid.uuid4(),
            dedup_key=dedup_key,
            user_id=user_id,
            business_id=business_id,
            kind=kind,
            template=template,
            params=dict(params),
            reason=reason,
            state=state,
            attempts=0,
        )
        .on_conflict_do_nothing(constraint="uq_email_deliveries_dedup_key_user_id")
        .returning(EmailDelivery.id)
    )


def claim_pending(session: Session, delivery_id: uuid.UUID) -> EmailDelivery | None:
    """Lock the delivery while it is pending; None when it isn't, or another process has it.

    `SKIP LOCKED`, as the nightly claim (AD-053): two processes never send it twice.
    """
    return session.scalars(
        select(EmailDelivery)
        .where(EmailDelivery.id == delivery_id, EmailDelivery.state == "pending")
        .with_for_update(skip_locked=True)
    ).one_or_none()


def pending_ids(session: Session) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(EmailDelivery.id)
            .where(EmailDelivery.state == "pending")
            .order_by(EmailDelivery.created_at, EmailDelivery.id)
        )
    )
