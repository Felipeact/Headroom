"""Sending email once, retrying it until it goes out, and each person's choices (spec 28).

A caller (spec 29's handler, spec 30's job) calls `request_email` in its own transaction,
commits, then calls `deliver` with the id it got back. The hourly `email_retries` job calls
`retry_pending` for whatever is still pending. `email_alert` is spec 29's caller.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

import structlog
from jinja2 import TemplateError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import events
from app.db import get_sessionmaker
from app.modules.accounts import service as accounts_service
from app.modules.alerts import service as alerts_service
from app.modules.alerts.events import ALERT_CREATED
from app.modules.forecasting import service as forecasting_service
from app.modules.notifications import digest, rendering, repository, senders
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
    try:
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
    except (TemplateError, ValueError) as exc:
        # A row that cannot render never will (a bad template, or a currency the `money`
        # filter refuses); failing it keeps the queue behind it moving.
        return _failed(delivery, type(exc).__name__, retryable=False)
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


def _name(counterparty: str | None, description: str | None) -> str:
    # As on the dashboard: the counterparty, else the description up to its first comma.
    if counterparty is not None:
        return counterparty
    return (description or "").split(",")[0].strip()


class InvitationNotSentError(Exception):
    """The invitation email could not be handed to the provider."""


def send_invitation(
    address: str, business_name: str, inviter_first_name: str | None, token: str
) -> None:
    """Email a bookkeeper invitation link, once, straight through the sender (spec 31).

    There is no `email_deliveries` row and no retry: the address is not stored (AD-020),
    and the footer has no unsubscribe link because the recipient has no account yet.
    Raises `InvitationNotSentError` when the provider refuses it.
    """
    settings = get_settings()
    inviter = inviter_first_name or "An owner"
    rendered = rendering.render(
        "invitation",
        {"business_name": business_name, "inviter": inviter, "token": token},
        first_name=None,
        footer=rendering.Footer(
            reason=(
                f"You're getting this email because {inviter} invited you to"
                f" {business_name} on Headroom."
            ),
            preferences_url=None,
            unsubscribe_url=None,
            mailing_address=settings.email_mailing_address,
        ),
    )
    email = senders.OutgoingEmail(
        to=address,
        sender=settings.email_from,
        subject=rendered.subject,
        html=rendered.html,
        text=rendered.text,
        headers={},
        idempotency_key=str(uuid.uuid4()),
    )
    try:
        senders.get_email_sender().send(email)
    except senders.SendError as exc:
        log.warning("invitation.email_failed", error_type=exc.error_type)
        raise InvitationNotSentError from None


def alert_params(
    alert: alerts_service.AlertView, *, business_name: str, change: str
) -> dict[str, Any]:
    """The params of an `alert` email (spec 29, door 3): JSON values, no account data.

    Causes largest first, ties by earlier date; amounts unsigned. The top fix is the first
    in kind order (AD-101).
    """
    causes = sorted(
        (i for i in alert.items if i.kind == "cause"),
        key=lambda i: (-abs(i.amount_cents), i.date),
    )
    top = alert.fixes[0] if alert.fixes else None
    return {
        "alert_id": str(alert.id),
        "business_name": business_name,
        "change": change,
        "currency": alert.currency,
        "minimum_cents": alert.minimum_cents,
        "lowest_balance_cents": alert.lowest_balance_cents,
        "lowest_week_starts_on": alert.lowest_week_starts_on.isoformat(),
        "causes": [
            {
                "name": _name(c.counterparty, c.description),
                "amount_cents": abs(c.amount_cents),
                "date": c.date.isoformat(),
            }
            for c in causes
        ],
        "top_fix": None
        if top is None
        else {
            "kind": top.kind,
            # A draw names the line of credit, which is the fix's description.
            "name": (top.description or "")
            if top.kind == "draw_credit"
            else _name(top.counterparty, top.description),
            "amount_cents": abs(top.amount_cents),
            "keeps_above": top.new_lowest_balance_cents >= alert.minimum_cents,
        },
        "fix_count": len(alert.fixes),
    }


def email_alert(event: events.Event) -> None:
    """Email every owner (and each opted-in bookkeeper) of the business about a new or grown cash gap (spec 29).

    The handler of `alert.created` and `alert.updated`. In one transaction it records one
    `alert` delivery per owner, keyed `alert:{alert_id}:{notified_shortfall_cents}`, so
    handling the same event twice emails once; after the commit it attempts each. An alert
    that is no longer open, or isn't the event's business's, sends nothing.
    """
    alert_id = uuid.UUID(str(event.payload["alert_id"]))
    pending: list[uuid.UUID] = []
    with get_sessionmaker()() as session:
        try:
            alert = alerts_service.get_alert(
                session, business_id=event.business_id, alert_id=alert_id
            )
        except alerts_service.AlertNotFoundError:
            log.info("email.alert_skipped", alert_id=str(alert_id), state="not_found")
            return
        if alert.state != "open":
            log.info("email.alert_skipped", alert_id=str(alert_id), state=alert.state)
            return
        business = accounts_service.get_business(
            session, business_id=event.business_id, role=accounts_service.Role.OWNER
        )
        params = alert_params(
            alert,
            business_name=business.name,
            change="created" if event.name == ALERT_CREATED else "updated",
        )
        for recipient in accounts_service.alert_recipients(
            session, business_id=event.business_id
        ):
            role = (
                "a bookkeeper for"
                if recipient.role == accounts_service.Role.BOOKKEEPER
                else "an owner of"
            )
            reason = (
                f"You're getting this email because you're {role}"
                f" {business.name} on Headroom."
            )
            delivery_id = request_email(
                session,
                dedup_key=f"alert:{alert.id}:{alert.notified_shortfall_cents}",
                user_id=recipient.user_id,
                business_id=event.business_id,
                kind="alert",
                template="alert",
                params=params,
                reason=reason,
            )
            if delivery_id is not None:
                pending.append(delivery_id)
        session.commit()
    log.info(
        "email.alert_requested",
        alert_id=str(alert_id),
        event_name=event.name,
        deliveries=len(pending),
    )
    for delivery_id in pending:
        deliver(delivery_id)


# The local hour of Monday in which the weekly digest goes out (spec 30, door 1).
DIGEST_HOUR = 8


def _request_digest(
    business_id: uuid.UUID, now: datetime, time_zone: str
) -> list[uuid.UUID] | None:
    """Record the business's digest deliveries; None when it has nothing to send yet."""
    zone = ZoneInfo(time_zone)
    monday = now.astimezone(zone).date()
    with get_sessionmaker()() as session:
        forecast = forecasting_service.latest_forecast(
            session, business_id=business_id, now=now
        )
        if forecast is None:
            log.info(
                "email.digest_skipped",
                business_id=str(business_id),
                reason="no_forecast",
            )
            return None
        minimum = forecasting_service.minimum_balance_amount(
            session, business_id=business_id
        )
        if minimum is None:
            log.info(
                "email.digest_skipped",
                business_id=str(business_id),
                reason="no_minimum",
            )
            return None
        business = accounts_service.get_business(
            session, business_id=business_id, role=accounts_service.Role.OWNER
        )
        last_monday = monday - timedelta(days=7)
        params = digest.digest_params(
            business_name=business.name,
            monday=monday,
            minimum_cents=minimum[0],
            forecast=forecast,
            open_alerts=alerts_service.list_alerts(
                session, business_id=business_id, state="open"
            ),
            last_week=forecasting_service.pinned_forecast(
                session, business_id=business_id, week_start=last_monday
            ),
            new_payments=forecasting_service.expected_payments_added_since(
                session,
                business_id=business_id,
                since=datetime.combine(last_monday, time.min, tzinfo=zone),
                now=now,
            ),
        )
        reason = (
            "You're getting this email because you're an owner of"
            f" {business.name} on Headroom."
        )
        pending: list[uuid.UUID] = []
        for user_id in accounts_service.owner_ids(session, business_id=business_id):
            delivery_id = request_email(
                session,
                dedup_key=f"weekly_digest:{business_id}:{monday.isoformat()}",
                user_id=user_id,
                business_id=business_id,
                kind="weekly_digest",
                template="weekly_digest",
                params=params,
                reason=reason,
            )
            if delivery_id is not None:
                pending.append(delivery_id)
        session.commit()
    log.info(
        "email.digest_requested",
        business_id=str(business_id),
        monday=monday.isoformat(),
        deliveries=len(pending),
    )
    return pending


def send_weekly_digests(now: datetime) -> dict[str, int]:
    """Email the owners of every business whose local time at `now` is Monday, 8 AM hour.

    The weekly digest job (spec 30). Each business runs in its own transaction, keyed
    `weekly_digest:{business_id}:{local Monday}`, so a second run in the hour sends
    nothing more; after the commit each new delivery is attempted. A business with no
    forecast or no minimum balance is skipped. A failing business is logged and the rest
    go on. Returns `digests_requested` (deliveries recorded) and `digests_failed`.
    """
    counts = {"digests_requested": 0, "digests_failed": 0}
    with get_sessionmaker()() as session:
        zones = accounts_service.all_business_zones(session)
    for business_id, time_zone in sorted(zones.items()):
        local = now.astimezone(ZoneInfo(time_zone))
        if local.weekday() != 0 or local.hour != DIGEST_HOUR:
            continue
        try:
            pending = _request_digest(business_id, now, time_zone) or []
        except Exception as exc:  # noqa: BLE001 - one business never stops the rest
            log.error(
                "email.digest_failed",
                business_id=str(business_id),
                error_type=type(exc).__name__,
            )
            counts["digests_failed"] += 1
            continue
        for delivery_id in pending:
            deliver(delivery_id)
        counts["digests_requested"] += len(pending)
    return counts
