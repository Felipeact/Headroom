import dataclasses
import datetime as dt
import time
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import audit, events
from app.db import get_sessionmaker
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync import service as bank_sync_service
from app.modules.forecasting import (
    detection,
    engine,
    matching,
    repository,
    strategies,
)
from app.modules.forecasting.events import FORECAST_INPUTS_CHANGED, FORECAST_UPDATED
from app.modules.forecasting.models import (
    ExpectedPayment,
    ExpectedPaymentMatch,
    ForecastItem,
    ForecastSnapshot,
    ForecastWeek,
    ItemSource,
    RecurringPattern,
    Repeats,
    Schedule,
)
from app.settings import get_settings

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
    repeats: Repeats | None


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
            repeats=p.repeats,  # type: ignore[arg-type]  # the check constraint holds it
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


# A connection that has not synced for longer than this makes the forecast incomplete.
STALE_AFTER = timedelta(hours=48)


def clock() -> datetime:
    """The event handlers' clock; tests replace it."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class ForecastItemView:
    id: uuid.UUID
    date: date
    account_id: uuid.UUID
    amount_cents: int
    currency: str
    source: ItemSource
    source_id: uuid.UUID | None
    description: str | None
    counterparty: str | None
    schedule: Schedule | None


@dataclass(frozen=True)
class ForecastWeekView:
    number: int
    starts_on: date
    ends_on: date
    end_balance_cents: int
    low_cents: int
    high_cents: int
    money_in_cents: int
    money_out_cents: int
    # By date, source, then ID.
    item_ids: list[uuid.UUID]


@dataclass(frozen=True)
class ForecastView:
    id: uuid.UUID
    as_of: date
    computed_at: datetime
    strategy: str
    currency: str
    opening_balance_cents: int
    incomplete: bool
    weeks: list[ForecastWeekView]
    # By date, source, then ID.
    items: list[ForecastItemView]


def _business_today(session: Session, business_id: uuid.UUID, now: datetime) -> date:
    zones = accounts_service.business_time_zones(session, [business_id])
    return engine.business_today(now, zones[business_id])


def forecast_inputs(
    session: Session, *, business_id: uuid.UUID, now: datetime
) -> strategies.ForecastInputs:
    """Everything a strategy reads about the business, as known at `now`."""
    today = _business_today(session, business_id, now)
    starts = engine.week_starts(today)
    accounts = [
        a
        for c in bank_sync_service.list_connections(session, business_id=business_id)
        for a in c.accounts
    ]
    return strategies.ForecastInputs(
        today=today,
        week_starts=starts,
        cash_accounts=tuple(
            strategies.CashAccount(a.id, a.currency, a.balance_cents)
            for a in accounts
            if a.included
        ),
        card_accounts=tuple(
            strategies.CardAccount(a.id, a.name, a.balance_cents)
            for a in accounts
            if a.type == "credit_card"
        ),
        transactions=tuple(
            strategies.InputTransaction(
                id=t.id,
                account_id=t.account_id,
                date=t.date,
                amount_cents=t.amount_cents,
                currency=t.currency,
                label=t.label,
                linked_transaction_id=t.linked_transaction_id,
            )
            for t in bank_sync_service.all_transactions(
                session, business_id=business_id
            )
        ),
        patterns=tuple(
            strategies.InputPattern(
                id=p.id,
                account_id=p.account_id,
                amount_cents=p.amount_cents,
                currency=p.currency,
                description=p.description,
                counterparty=p.counterparty,
                schedule=p.schedule,  # type: ignore[arg-type]  # the check constraint holds it
                next_date=p.next_date,
                transaction_ids=tuple(p.transaction_ids),
            )
            for p in repository.patterns(session, business_id=business_id)
        ),
        open_occurrences=tuple(
            strategies.InputOccurrence(
                expected_payment_id=o.expected_payment_id,
                account_id=o.account_id,
                amount_cents=o.amount_cents,
                currency=o.currency,
                description=o.description,
                date=o.date,
                repeats=o.repeats,
            )
            for o in open_occurrences(
                session,
                business_id=business_id,
                today=today,
                until=starts[-1] + timedelta(days=6),
            )
        ),
        matched_transaction_ids=frozenset(
            m.transaction_id
            for m in repository.matches(session, business_id=business_id)
        ),
    )


def recompute_forecast(event: events.Event) -> None:
    """Recompute the business's 13-week forecast, storing it if its inputs changed.

    The handler of `transactions.synced` and `forecast_inputs.changed` (AD-079): one
    transaction under the business's forecast lock. Inputs equal to the latest
    snapshot's write and publish nothing; inputs equal to an earlier one's make that
    snapshot the latest again. After the commit it publishes `forecast.updated`. A
    failure rolls back and keeps the earlier latest snapshot.
    """
    started = time.perf_counter()
    business_id = event.business_id
    with get_sessionmaker()() as session:
        repository.lock_forecast(session, business_id=business_id)
        inputs = forecast_inputs(session, business_id=business_id, now=clock())
        selected = get_settings().forecast_strategy
        inputs_sha256 = engine.fingerprint(inputs, selected)
        latest = repository.latest_snapshot(session, business_id=business_id)
        if latest is not None and latest.inputs_sha256 == inputs_sha256:
            session.commit()
            log.info("forecast.unchanged", business_id=str(business_id))
            return
        strategy, result = engine.CashFlowForecastService(selected).run(
            inputs, business_id=business_id
        )
        snapshot_id, inserted = repository.upsert_snapshot(
            session,
            snapshot=ForecastSnapshot(
                id=uuid.uuid4(),
                business_id=business_id,
                inputs_sha256=inputs_sha256,
                strategy=strategy,
                as_of=inputs.today,
                currency=strategies.CASH_CURRENCY,
                opening_balance_cents=strategies.opening_balance(inputs),
            ),
        )
        if inserted:
            repository.add_weeks_and_items(
                session,
                weeks=[
                    ForecastWeek(snapshot_id=snapshot_id, **dataclasses.asdict(w))
                    for w in result.weeks
                ],
                items=[
                    ForecastItem(snapshot_id=snapshot_id, **dataclasses.asdict(i))
                    for i in result.items
                ],
            )
        session.commit()
    log.info(
        "forecast.updated",
        business_id=str(business_id),
        snapshot_id=str(snapshot_id),
        strategy=strategy,
        items=len(result.items),
        duration_ms=round((time.perf_counter() - started) * 1000),
    )
    events.publish(
        events.Event(
            name=FORECAST_UPDATED,
            business_id=business_id,
            payload={"snapshot_id": str(snapshot_id)},
        )
    )


def is_incomplete(session: Session, *, business_id: uuid.UUID, now: datetime) -> bool:
    """A connection with an included account needs attention or is stale (AC 25)."""
    return any(
        c.status in ("login_required", "sync_failing")
        or c.last_synced_at is None
        or now - c.last_synced_at > STALE_AFTER
        for c in bank_sync_service.list_connections(session, business_id=business_id)
        if any(a.included for a in c.accounts)
    )


def _item_view(row: ForecastItem) -> ForecastItemView:
    return ForecastItemView(
        id=row.id,
        date=row.date,
        account_id=row.account_id,
        amount_cents=row.amount_cents,
        currency=row.currency,
        source=row.source,  # type: ignore[arg-type]  # the check constraint holds it
        source_id=row.source_id,
        description=row.description,
        counterparty=row.counterparty,
        schedule=row.schedule,  # type: ignore[arg-type]  # a pattern's or a payment's words
    )


def latest_forecast(
    session: Session, *, business_id: uuid.UUID, now: datetime
) -> ForecastView | None:
    """The business's latest forecast, with `incomplete` as of `now`; None if none yet."""
    snapshot = repository.latest_snapshot(session, business_id=business_id)
    if snapshot is None:
        return None
    rows = repository.snapshot_items(session, snapshot_id=snapshot.id)
    by_week: dict[int, list[uuid.UUID]] = defaultdict(list)
    for row in rows:
        by_week[row.week].append(row.id)
    return ForecastView(
        id=snapshot.id,
        as_of=snapshot.as_of,
        computed_at=snapshot.last_computed_at,
        strategy=snapshot.strategy,
        currency=snapshot.currency,
        opening_balance_cents=snapshot.opening_balance_cents,
        incomplete=is_incomplete(session, business_id=business_id, now=now),
        weeks=[
            ForecastWeekView(
                number=w.number,
                starts_on=w.starts_on,
                ends_on=w.starts_on + timedelta(days=6),
                end_balance_cents=w.end_balance_cents,
                low_cents=w.low_cents,
                high_cents=w.high_cents,
                money_in_cents=w.money_in_cents,
                money_out_cents=w.money_out_cents,
                item_ids=by_week[w.number],
            )
            for w in repository.snapshot_weeks(session, snapshot_id=snapshot.id)
        ],
        items=[_item_view(r) for r in rows],
    )


def upcoming_items(
    session: Session, *, business_id: uuid.UUID, now: datetime, days: int
) -> list[ForecastItemView] | None:
    """The latest forecast's named items from today to today + `days` - 1 (AC 26).

    Estimates are left out. None when the business has no forecast yet.
    """
    snapshot = repository.latest_snapshot(session, business_id=business_id)
    if snapshot is None:
        return None
    today = _business_today(session, business_id, now)
    last = today + timedelta(days=days - 1)
    return [
        _item_view(r)
        for r in repository.snapshot_items(session, snapshot_id=snapshot.id)
        if r.source != "estimate" and today <= r.date <= last
    ]
