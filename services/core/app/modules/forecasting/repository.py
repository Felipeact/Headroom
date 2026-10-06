import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.forecasting.models import RecurringPattern


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
