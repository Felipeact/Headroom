import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.forecasting.models import (
    ExpectedPayment,
    ExpectedPaymentMatch,
    ForecastAccuracy,
    ForecastItem,
    ForecastPin,
    ForecastSnapshot,
    ForecastWeek,
    MinimumBalance,
    RecurringPattern,
)


def lock_patterns(session: Session, *, business_id: uuid.UUID) -> None:
    """Hold the business's pattern lock until the transaction ends (AD-071).

    Two refreshes of one business would otherwise each delete only the rows they can see
    and both insert, leaving two sets.
    """
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(f"recurring_patterns:{business_id}", 0)
            )
        )
    )


def replace_patterns(
    session: Session,
    *,
    business_id: uuid.UUID,
    patterns: Sequence[RecurringPattern],
) -> None:
    """Delete every pattern of the business, then add `patterns`."""
    session.execute(
        delete(RecurringPattern).where(RecurringPattern.business_id == business_id)
    )
    session.add_all(patterns)
    session.flush()


def patterns(session: Session, *, business_id: uuid.UUID) -> list[RecurringPattern]:
    """The business's patterns by next date, then counterparty, then ID."""
    return list(
        session.scalars(
            select(RecurringPattern)
            .where(RecurringPattern.business_id == business_id)
            .order_by(
                RecurringPattern.next_date,
                RecurringPattern.counterparty,
                RecurringPattern.id,
            )
        )
    )


def lock_expected_payments(session: Session, *, business_id: uuid.UUID) -> None:
    """Hold the business's expected-payments lock until the transaction ends (AD-074).

    Every write of a payment and every rematch takes it, so two of them never leave two
    sets of matches.
    """
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(f"expected_payments:{business_id}", 0)
            )
        )
    )


def expected_payments(
    session: Session, *, business_id: uuid.UUID
) -> list[ExpectedPayment]:
    """Every expected payment of the business, in no particular order."""
    return list(
        session.scalars(
            select(ExpectedPayment).where(ExpectedPayment.business_id == business_id)
        )
    )


def expected_payment(
    session: Session, *, business_id: uuid.UUID, payment_id: uuid.UUID
) -> ExpectedPayment | None:
    """The business's payment with this ID, or None."""
    return session.scalar(
        select(ExpectedPayment).where(
            ExpectedPayment.business_id == business_id,
            ExpectedPayment.id == payment_id,
        )
    )


def matches(session: Session, *, business_id: uuid.UUID) -> list[ExpectedPaymentMatch]:
    """Every match of the business."""
    return list(
        session.scalars(
            select(ExpectedPaymentMatch).where(
                ExpectedPaymentMatch.business_id == business_id
            )
        )
    )


def replace_matches(
    session: Session,
    *,
    business_id: uuid.UUID,
    matches: Sequence[ExpectedPaymentMatch],
) -> None:
    """Delete every match of the business, then add `matches`."""
    session.execute(
        delete(ExpectedPaymentMatch).where(
            ExpectedPaymentMatch.business_id == business_id
        )
    )
    session.add_all(matches)
    session.flush()


def lock_forecast(session: Session, *, business_id: uuid.UUID) -> None:
    """Hold the business's forecast lock until the transaction ends (AD-079).

    Two recomputes of one business run one after the other, so the latest snapshot is
    always the last one computed.
    """
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(f"forecast:{business_id}", 0)
            )
        )
    )


def latest_snapshot(
    session: Session, *, business_id: uuid.UUID
) -> ForecastSnapshot | None:
    """The business's snapshot with the greatest `(last_computed_at, id)`, or None."""
    return session.scalar(
        select(ForecastSnapshot)
        .where(ForecastSnapshot.business_id == business_id)
        .order_by(ForecastSnapshot.last_computed_at.desc(), ForecastSnapshot.id.desc())
        .limit(1)
    )


def upsert_snapshot(
    session: Session, *, snapshot: ForecastSnapshot
) -> tuple[uuid.UUID, bool]:
    """Insert `snapshot`, or make the business's one with its fingerprint the latest.

    Returns the stored snapshot's ID, and whether it was inserted. `last_computed_at`
    is the clock at this statement, after the forecast lock was taken.
    """
    snapshot_id: uuid.UUID
    inserted: bool
    snapshot_id, inserted = session.execute(
        insert(ForecastSnapshot)
        .values(
            id=snapshot.id,
            business_id=snapshot.business_id,
            inputs_sha256=snapshot.inputs_sha256,
            strategy=snapshot.strategy,
            as_of=snapshot.as_of,
            currency=snapshot.currency,
            opening_balance_cents=snapshot.opening_balance_cents,
            last_computed_at=func.clock_timestamp(),
        )
        .on_conflict_do_update(
            constraint="uq_forecast_snapshots_business_id_inputs_sha256",
            set_={"last_computed_at": func.clock_timestamp()},
        )
        # A row inserted by this statement has no deleting transaction yet.
        .returning(ForecastSnapshot.id, literal_column("xmax = 0"))
    ).one()
    return snapshot_id, inserted


def add_weeks_and_items(
    session: Session, *, weeks: Sequence[ForecastWeek], items: Sequence[ForecastItem]
) -> None:
    """Store a new snapshot's weeks and items."""
    session.add_all(weeks)
    session.add_all(items)
    session.flush()


def snapshot_weeks(session: Session, *, snapshot_id: uuid.UUID) -> list[ForecastWeek]:
    """The snapshot's weeks, 1 to 13."""
    return list(
        session.scalars(
            select(ForecastWeek)
            .where(ForecastWeek.snapshot_id == snapshot_id)
            .order_by(ForecastWeek.number)
        )
    )


def snapshot_items(session: Session, *, snapshot_id: uuid.UUID) -> list[ForecastItem]:
    """The snapshot's items by date, source, then ID."""
    return list(
        session.scalars(
            select(ForecastItem)
            .where(ForecastItem.snapshot_id == snapshot_id)
            .order_by(ForecastItem.date, ForecastItem.source, ForecastItem.id)
        )
    )


def snapshot_business_ids(session: Session) -> list[uuid.UUID]:
    """Every business with a stored forecast, for the accuracy job (AD-085)."""
    return list(
        session.scalars(
            select(ForecastSnapshot.business_id)
            .distinct()
            .order_by(ForecastSnapshot.business_id)
        )
    )


def add_pin(
    session: Session,
    *,
    business_id: uuid.UUID,
    week_start: date,
    snapshot_id: uuid.UUID,
) -> bool:
    """Pin `snapshot_id` to the week unless the week has a pin; True when inserted."""
    inserted = session.execute(
        insert(ForecastPin)
        .values(business_id=business_id, week_start=week_start, snapshot_id=snapshot_id)
        .on_conflict_do_nothing()
        .returning(ForecastPin.week_start)
    ).first()
    return inserted is not None


def pins_since(
    session: Session, *, business_id: uuid.UUID, since: date
) -> list[ForecastPin]:
    """The business's pins from `since` on, oldest first."""
    return list(
        session.scalars(
            select(ForecastPin)
            .where(ForecastPin.business_id == business_id)
            .where(ForecastPin.week_start >= since)
            .order_by(ForecastPin.week_start)
        )
    )


def recorded_horizons(
    session: Session, *, business_id: uuid.UUID, since: date
) -> set[tuple[date, int]]:
    """`(week_start, horizon)` of the business's accuracy rows from `since` on."""
    return {
        (week_start, horizon)
        for week_start, horizon in session.execute(
            select(ForecastAccuracy.week_start, ForecastAccuracy.horizon)
            .where(ForecastAccuracy.business_id == business_id)
            .where(ForecastAccuracy.week_start >= since)
        )
    }


def add_accuracy(session: Session, *, row: ForecastAccuracy) -> bool:
    """Store `row` unless its pin and horizon have one; True when inserted."""
    inserted = session.execute(
        insert(ForecastAccuracy)
        .values(
            business_id=row.business_id,
            week_start=row.week_start,
            horizon=row.horizon,
            target_week_start=row.target_week_start,
            snapshot_id=row.snapshot_id,
            currency=row.currency,
            forecast_cents=row.forecast_cents,
            actual_cents=row.actual_cents,
            error_cents=row.error_cents,
        )
        .on_conflict_do_nothing()
        .returning(ForecastAccuracy.horizon)
    ).first()
    return inserted is not None


def accuracy_rows(
    session: Session, *, horizon: int, since: date
) -> list[ForecastAccuracy]:
    """Every business's rows at `horizon` from `since` on, by week, then business."""
    return list(
        session.scalars(
            select(ForecastAccuracy)
            .where(ForecastAccuracy.horizon == horizon)
            .where(ForecastAccuracy.week_start >= since)
            .order_by(ForecastAccuracy.week_start, ForecastAccuracy.business_id)
        )
    )


def minimum_balance(
    session: Session, *, business_id: uuid.UUID, lock: bool = False
) -> MinimumBalance | None:
    """The business's minimum balance row, locked for update when `lock`."""
    query = select(MinimumBalance).where(MinimumBalance.business_id == business_id)
    return session.scalar(query.with_for_update() if lock else query)


def save_minimum_balance(
    session: Session,
    *,
    business_id: uuid.UUID,
    amount_cents: int,
    currency: str,
    user_id: uuid.UUID,
) -> None:
    """Insert the business's minimum balance, or replace the one it has."""
    values = {
        "amount_cents": amount_cents,
        "currency": currency,
        "updated_by": user_id,
        "updated_at": func.now(),
    }
    session.execute(
        insert(MinimumBalance)
        .values(business_id=business_id, **values)
        .on_conflict_do_update(index_elements=["business_id"], set_=values)
    )
    session.expire_all()
