import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.forecasting.models import (
    ExpectedPayment,
    ExpectedPaymentMatch,
    ForecastItem,
    ForecastSnapshot,
    ForecastWeek,
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
