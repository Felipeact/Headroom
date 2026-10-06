import datetime as dt
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import audit, events
from app.db import get_sessionmaker
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync import service as bank_sync_service
from app.modules.forecasting import detection, matching, repository
from app.modules.forecasting.events import FORECAST_INPUTS_CHANGED
from app.modules.forecasting.models import (
    ExpectedPayment,
    ExpectedPaymentMatch,
    RecurringPattern,
    Repeats,
    Schedule,
)

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PatternView:
    id: uuid.UUID
    account_id: uuid.UUID
    counterparty: str
    description: str
    schedule: Schedule
    amount_cents: int
    currency: str
    next_date: date
    confidence: int
    transaction_ids: list[uuid.UUID]


def refresh_recurring_patterns(event: events.Event) -> None:
    """Replace the business's recurring patterns with those its transactions show now.

    The `transactions.synced` handler (AD-071): one transaction under the business's
    pattern lock, so overlapping refreshes leave one set. A failure rolls back and keeps
    the earlier patterns.
    """
    business_id = event.business_id
    with get_sessionmaker()() as session:
        repository.lock_patterns(session, business_id=business_id)
        found = detection.detect(
            bank_sync_service.all_transactions(session, business_id=business_id)
        )
        repository.replace_patterns(
            session,
            business_id=business_id,
            patterns=[
                RecurringPattern(
                    business_id=business_id,
                    account_id=p.account_id,
                    counterparty=p.counterparty,
                    description=p.description,
                    schedule=p.schedule,
                    amount_cents=p.amount_cents,
                    currency=p.currency,
                    next_date=p.next_date,
                    confidence=p.confidence,
                    transaction_ids=list(p.transaction_ids),
                )
                for p in found
            ],
        )
        session.commit()
    log.info(
        "recurring_patterns.refreshed",
        business_id=str(business_id),
        patterns=len(found),
    )


def list_patterns(session: Session, *, business_id: uuid.UUID) -> list[PatternView]:
    """The business's recurring patterns by next date, then counterparty, then ID."""
    return [
        PatternView(
            id=r.id,
            account_id=r.account_id,
            counterparty=r.counterparty,
            description=r.description,
            schedule=r.schedule,  # type: ignore[arg-type]  # the check constraint holds it
            amount_cents=r.amount_cents,
            currency=r.currency,
            next_date=r.next_date,
            confidence=r.confidence,
            transaction_ids=list(r.transaction_ids),
        )
        for r in repository.patterns(session, business_id=business_id)
    ]


# An expected payment's date may be up to 90 days back and 730 days ahead (AC 5).
PAST_DAYS = 90
FUTURE_DAYS = 730

AccountChoice = Literal["not_cash", "no_primary"]


class ExpectedPaymentNotFoundError(Exception):
    """No expected payment with this ID in this business."""


class AccountChoiceError(Exception):
    """The account is not one of the business's cash accounts, or it has no primary."""

    def __init__(self, reason: AccountChoice) -> None:
        super().__init__(reason)
        self.reason: AccountChoice = reason


class DateOutOfRangeError(Exception):
    """The payment's date is more than 90 days back or 730 days ahead of today."""


@dataclass(frozen=True)
class ExpectedPaymentView:
    id: uuid.UUID
    account_id: uuid.UUID
    description: str
    amount_cents: int
    currency: str
    date: date
    repeats: Repeats | None
    # None once a one-off is matched; earlier than today when overdue.
    next_date: dt.date | None
    overdue: bool


@dataclass(frozen=True)
class OpenOccurrence:
    expected_payment_id: uuid.UUID
    account_id: uuid.UUID
    description: str
    amount_cents: int
    currency: str
    date: date


def _today(session: Session, business_id: uuid.UUID, now: datetime) -> date:
    zones = accounts_service.business_time_zones(session, [business_id])
    return now.astimezone(ZoneInfo(zones[business_id])).date()


def _window_open(day: date, today: date) -> bool:
    return day + timedelta(days=matching.LATE_DAYS) >= today


def _next_date(
    payment: ExpectedPayment, matched: set[date], today: date
) -> date | None:
    if payment.repeats is None:
        return None if payment.date in matched else payment.date
    for day in matching.occurrences(payment.date, payment.repeats):
        if _window_open(day, today) and day not in matched:
            return day
    raise AssertionError("a repeating payment always has a later occurrence")


def _matched_dates(
    found: Sequence[matching.Match | ExpectedPaymentMatch],
) -> dict[uuid.UUID, set[date]]:
    dates: dict[uuid.UUID, set[date]] = defaultdict(set)
    for m in found:
        dates[m.expected_payment_id].add(m.occurrence_date)
    return dates


def _payment_view(
    payment: ExpectedPayment, matched: set[date], today: date
) -> ExpectedPaymentView:
    next_date = _next_date(payment, matched, today)
    return ExpectedPaymentView(
        id=payment.id,
        account_id=payment.account_id,
        description=payment.description,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        date=payment.date,
        repeats=payment.repeats,  # type: ignore[arg-type]  # the check constraint holds it
        next_date=next_date,
        overdue=next_date is not None and next_date < today,
    )


def _rematch(session: Session, business_id: uuid.UUID) -> list[matching.Match]:
    """Recompute and store every match of the business; the caller holds the lock."""
    found = matching.match(
        repository.expected_payments(session, business_id=business_id),
        bank_sync_service.all_transactions(session, business_id=business_id),
    )
    repository.replace_matches(
        session,
        business_id=business_id,
        matches=[
            ExpectedPaymentMatch(
                expected_payment_id=m.expected_payment_id,
                occurrence_date=m.occurrence_date,
                business_id=business_id,
                transaction_id=m.transaction_id,
            )
            for m in found
        ],
    )
    return found


def _log_matched(business_id: uuid.UUID, found: list[matching.Match]) -> None:
    log.info(
        "expected_payments.matched", business_id=str(business_id), matches=len(found)
    )


def match_expected_payments(event: events.Event) -> None:
    """Rematch the business's expected payments against its transactions now.

    The `transactions.synced` handler (AD-074): one transaction under the business's
    expected-payments lock. A failure rolls back and keeps the earlier matches. It
    publishes nothing, because the forecast recomputes on the same event.
    """
    business_id = event.business_id
    with get_sessionmaker()() as session:
        repository.lock_expected_payments(session, business_id=business_id)
        found = _rematch(session, business_id)
        session.commit()
    _log_matched(business_id, found)


def list_expected_payments(
    session: Session, *, business_id: uuid.UUID, now: datetime
) -> list[ExpectedPaymentView]:
    """The payments with an upcoming occurrence, by next date, description, then ID."""
    today = _today(session, business_id, now)
    matched = _matched_dates(repository.matches(session, business_id=business_id))
    views = [
        _payment_view(p, matched[p.id], today)
        for p in repository.expected_payments(session, business_id=business_id)
    ]
    upcoming = [(v.next_date, v) for v in views if v.next_date is not None]
    return [
        v for _, v in sorted(upcoming, key=lambda x: (x[0], x[1].description, x[1].id))
    ]


def open_occurrences(
    session: Session, *, business_id: uuid.UUID, today: date, until: date
) -> list[OpenOccurrence]:
    """The occurrences still to be counted, dated on or before `until` (AC 23).

    A matched occurrence is never one of them, so its money is counted once: in the bank
    balance. A one-off stays until it is matched; a repeating occurrence drops out once
    its late window has closed.
    """
    matched = _matched_dates(repository.matches(session, business_id=business_id))
    found = [
        OpenOccurrence(
            expected_payment_id=p.id,
            account_id=p.account_id,
            description=p.description,
            amount_cents=p.amount_cents,
            currency=p.currency,
            date=day,
        )
        for p in repository.expected_payments(session, business_id=business_id)
        for day in matching.occurrences_until(p.date, p.repeats, until)
        if day not in matched[p.id] and (p.repeats is None or _window_open(day, today))
    ]
    return sorted(found, key=lambda o: (o.date, o.description, o.expected_payment_id))


def _cash_account(
    session: Session, business_id: uuid.UUID, account_id: uuid.UUID | None
) -> bank_sync_service.AccountView:
    accounts = [
        a
        for c in bank_sync_service.list_connections(session, business_id=business_id)
        for a in c.accounts
        if a.included
    ]
    if account_id is None:
        primary = next((a for a in accounts if a.primary), None)
        if primary is None:
            raise AccountChoiceError("no_primary")
        return primary
    chosen = next((a for a in accounts if a.id == account_id), None)
    if chosen is None:
        raise AccountChoiceError("not_cash")
    return chosen


def _check_date(day: date, today: date) -> None:
    earliest = today - timedelta(days=PAST_DAYS)
    if not earliest <= day <= today + timedelta(days=FUTURE_DAYS):
        raise DateOutOfRangeError


def _audit(
    session: Session,
    action: str,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    payment_id: uuid.UUID,
) -> None:
    audit.record(
        session,
        action=action,
        business_id=business_id,
        actor_user_id=str(user_id),
        target_type="expected_payment",
        target_id=str(payment_id),
    )


def _announce(
    action: str,
    business_id: uuid.UUID,
    payment_id: uuid.UUID,
    found: list[matching.Match],
) -> None:
    """After the commit: log the change and the matches, and tell the forecast (AD-076)."""
    log.info(action, business_id=str(business_id), expected_payment_id=str(payment_id))
    _log_matched(business_id, found)
    events.publish(
        events.Event(
            name=FORECAST_INPUTS_CHANGED,
            business_id=business_id,
            payload={
                "source": "expected_payments",
                "expected_payment_id": str(payment_id),
            },
        )
    )


def save_expected_payment(
    session: Session,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    payment_id: uuid.UUID | None,
    account_id: uuid.UUID | None,
    description: str,
    amount_cents: int,
    day: date,
    repeats: Repeats | None,
    now: datetime,
) -> ExpectedPaymentView:
    """Create an expected payment (`payment_id` None), or replace an existing one's values.

    `account_id` None means the business's primary account. Rematches the business,
    writes an audit entry and commits, then publishes `forecast_inputs.changed`.
    Raises `ExpectedPaymentNotFoundError`, `AccountChoiceError` or `DateOutOfRangeError`
    after rolling back, so nothing is stored.
    """
    action = (
        "expected_payment.created" if payment_id is None else "expected_payment.updated"
    )
    try:
        repository.lock_expected_payments(session, business_id=business_id)
        today = _today(session, business_id, now)
        if payment_id is None:
            payment = ExpectedPayment(business_id=business_id)
        else:
            existing = repository.expected_payment(
                session, business_id=business_id, payment_id=payment_id
            )
            if existing is None:
                raise ExpectedPaymentNotFoundError
            payment = existing
        _check_date(day, today)
        account = _cash_account(session, business_id, account_id)
        payment.account_id = account.id
        payment.currency = account.currency
        payment.description = description
        payment.amount_cents = amount_cents
        payment.date = day
        payment.repeats = repeats
        if payment_id is None:
            session.add(payment)
        else:
            payment.updated_at = func.now()
        session.flush()
        # Loads the server-side `created_at`, which orders the matching (AC 15).
        session.refresh(payment)
        _audit(session, action, business_id, user_id, payment.id)
        found = _rematch(session, business_id)
        view = _payment_view(payment, _matched_dates(found)[payment.id], today)
        session.commit()
    except BaseException:
        session.rollback()
        raise
    _announce(action, business_id, view.id, found)
    return view


def delete_expected_payment(
    session: Session,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    payment_id: uuid.UUID,
) -> None:
    """Delete the payment and its matches, rematch, audit and commit, then publish.

    Raises `ExpectedPaymentNotFoundError` after rolling back.
    """
    try:
        repository.lock_expected_payments(session, business_id=business_id)
        payment = repository.expected_payment(
            session, business_id=business_id, payment_id=payment_id
        )
        if payment is None:
            raise ExpectedPaymentNotFoundError
        session.delete(payment)
        session.flush()
        _audit(session, "expected_payment.deleted", business_id, user_id, payment_id)
        found = _rematch(session, business_id)
        session.commit()
    except BaseException:
        session.rollback()
        raise
    _announce("expected_payment.deleted", business_id, payment_id, found)
