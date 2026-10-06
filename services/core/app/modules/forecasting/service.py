import uuid
from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy.orm import Session

from app import events
from app.db import get_sessionmaker
from app.modules.bank_sync import service as bank_sync_service
from app.modules.forecasting import detection, repository
from app.modules.forecasting.models import RecurringPattern, Schedule

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
