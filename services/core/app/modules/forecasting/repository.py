import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.forecasting.models import (
    ExpectedPayment,
    ExpectedPaymentMatch,
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
