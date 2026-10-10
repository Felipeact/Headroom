"""Sending email once, retrying it until it goes out, and each person's choices (spec 28).

A caller (spec 29's handler, spec 30's job) calls `request_email` in its own transaction,
commits, then calls `deliver` with the id it got back. The hourly `email_retries` job calls
`retry_pending` for whatever is still pending.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.modules.accounts import service as accounts_service
from app.modules.notifications import rendering, repository, senders
from app.modules.notifications.models import EmailDelivery, EmailKind, EmailPreferences
from app.settings import get_settings

log = structlog.get_logger(__name__)

Outcome = Literal["sent", "failed", "pending", "skipped"]


@dataclass(frozen=True)
class Preferences:
    alerts: bool
    weekly_digest: bool


def _view(row: EmailPreferences | None) -> Preferences:
    if row is None:
        return Preferences(alerts=True, weekly_digest=True)
    return Preferences(alerts=row.alerts, weekly_digest=row.weekly_digest)


def _wants(row: EmailPreferences | None, kind: str) -> bool:
    prefs = _view(row)
    return prefs.alerts if kind == "alert" else prefs.weekly_digest


def get_preferences(session: Session, user_id: uuid.UUID) -> Preferences:
    """The user's choices; both kinds on for someone who never changed them. Writes nothing."""
    return _view(repository.preferences(session, user_id))


def set_preferences(
    session: Session, user_id: uuid.UUID, *, alerts: bool, weekly_digest: bool
) -> Preferences:
    """Save both choices and return them. Commits the session."""
    repository.save_preferences(
        session, user_id=user_id, alerts=alerts, weekly_digest=weekly_digest
    )
    session.commit()
    session.expire_all()
    return get_preferences(session, user_id)


def unsubscribe(session: Session, token: str) -> bool:
    """Turn every email off for the token's user, at once. False for an unknown token.

    A second call changes nothing. Commits the session.
    """
    found = repository.unsubscribe(session, token)
    session.commit()
    if found:
        log.info("email.unsubscribed")
    return found


def unsubscribe_token(session: Session, user_id: uuid.UUID) -> str:
    """The user's unsubscribe token, issued on first need and never changed. Commits."""
    token = repository.ensure_token(session, user_id)
    session.commit()
    return token


def request_email(
    session: Session,
    *,
    dedup_key: str,
    user_id: uuid.UUID,
    business_id: uuid.UUID,
    kind: EmailKind,
    template: str,
    params: Mapping[str, Any],
    reason: str,
) -> uuid.UUID | None:
    """Record one email to `user_id` for `dedup_key`, in the caller's transaction.

    Returns the delivery's id for the caller to `deliver` after it commits. Returns None
    when the key was already used for this user (the event was handled before), or when
    the user turned this kind off: then the delivery is recorded `skipped`. `params` are
    JSON values; `reason` is the footer's first line.
    """
    wanted = _wants(repository.preferences(session, user_id), kind)
    state = "pending" if wanted else "skipped"
    delivery_id = repository.insert_delivery(
        session,
        dedup_key=dedup_key,
        user_id=user_id,
        business_id=business_id,
        kind=kind,
        template=template,
        params=params,
        reason=reason,
        state=state,
    )
    if delivery_id is None:
        return None
    if not wanted:
        log.info("email.skipped", delivery_id=str(delivery_id), kind=kind)
        return None
    return delivery_id


def deliver(delivery_id: uuid.UUID) -> Outcome | None:
    """Attempt one pending delivery in its own transaction, and return what became of it.

    None when it is not pending, or another process is attempting it right now.
    """
    with get_sessionmaker()() as session:
        delivery = repository.claim_pending(session, delivery_id)
        if delivery is None:
            session.rollback()
            return None
        outcome = _attempt(session, delivery)
        delivery.updated_at = func.now()
        session.commit()
        return outcome


def retry_pending() -> dict[str, int]:
    """Attempt every pending delivery once, with no cap on attempts (spec 28 AC 18)."""
    with get_sessionmaker()() as session:
        ids = repository.pending_ids(session)
    counts = {"emails_sent": 0, "emails_failed": 0, "emails_pending": 0}
    for delivery_id in ids:
        outcome = deliver(delivery_id)
        if outcome is not None and outcome != "skipped":
            counts[f"emails_{outcome}"] += 1
    return counts


def _attempt(session: Session, delivery: EmailDelivery) -> Outcome:
    if not _wants(repository.preferences(session, delivery.user_id), delivery.kind):
        delivery.state = "skipped"
        log.info("email.skipped", delivery_id=str(delivery.id), kind=delivery.kind)
        return "skipped"
    delivery.attempts += 1
    try:
        contact = accounts_service.contact(session, delivery.user_id)
    except accounts_service.ContactUnavailableError as exc:
        return _failed(delivery, f"clerk_{exc.error_type}", retryable=True)
    if contact is None:
        return _failed(delivery, "no_contact", retryable=False)

    settings = get_settings()
    token = repository.ensure_token(session, delivery.user_id)
    rendered = rendering.render(
        delivery.template,
        delivery.params,
        first_name=contact.first_name,
        footer=rendering.Footer(
            reason=delivery.reason,
            preferences_url=f"{settings.web_url}/settings/email",
            unsubscribe_url=f"{settings.web_url}/unsubscribe/{token}",
            mailing_address=settings.email_mailing_address,
        ),
    )
    email = senders.OutgoingEmail(
        to=contact.email,
        sender=settings.email_from,
        subject=rendered.subject,
        html=rendered.html,
        text=rendered.text,
        headers={
            "List-Unsubscribe": f"<{settings.api_public_url}/v1/unsubscribe/{token}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        idempotency_key=str(delivery.id),
    )
    try:
        provider_id = senders.get_email_sender().send(email)
    except senders.SendError as exc:
        return _failed(delivery, exc.error_type, retryable=exc.retryable)
    delivery.state = "sent"
    delivery.provider_id = provider_id
    delivery.sent_at = func.now()
    log.info(
        "email.sent",
        delivery_id=str(delivery.id),
        kind=delivery.kind,
        provider_id=provider_id,
    )
    return "sent"


def _failed(delivery: EmailDelivery, error_type: str, *, retryable: bool) -> Outcome:
    fields = {
        "delivery_id": str(delivery.id),
        "kind": delivery.kind,
        "error_type": error_type,
        "attempts": delivery.attempts,
    }
    if retryable:
        log.warning("email.send_failed", **fields)
        return "pending"
    delivery.state = "failed"
    log.error("email.failed", **fields)
    return "failed"
