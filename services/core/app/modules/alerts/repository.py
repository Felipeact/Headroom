import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.alerts.models import Alert, AlertItem, AlertState


def lock_alerts(session: Session, *, business_id: uuid.UUID) -> None:
    """Hold the business's alerts lock until the transaction ends (AD-096).

    Two checks, or a check and a dismissal, of one business run one after the other, so
    each sees the other's alerts and a gap never gets a second one.
    """
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(f"alerts:{business_id}", 0)
            )
        )
    )


def live_alerts(session: Session, *, business_id: uuid.UUID) -> list[Alert]:
    """The business's open and dismissed alerts, by `starts_on` then `id`."""
    return list(
        session.scalars(
            select(Alert)
            .where(
                Alert.business_id == business_id,
                Alert.state.in_(("open", "dismissed")),
            )
            .order_by(Alert.starts_on, Alert.id)
        )
    )


def alerts_in_state(
    session: Session, *, business_id: uuid.UUID, state: AlertState
) -> list[Alert]:
    return list(
        session.scalars(
            select(Alert)
            .where(Alert.business_id == business_id, Alert.state == state)
            .order_by(Alert.starts_on, Alert.id)
        )
    )


def alert(
    session: Session, *, business_id: uuid.UUID, alert_id: uuid.UUID
) -> Alert | None:
    return session.scalar(
        select(Alert).where(Alert.business_id == business_id, Alert.id == alert_id)
    )


def items_of(
    session: Session, *, alert_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[AlertItem]]:
    """Each alert's items, by position."""
    found: dict[uuid.UUID, list[AlertItem]] = defaultdict(list)
    for row in session.scalars(
        select(AlertItem)
        .where(AlertItem.alert_id.in_(alert_ids))
        .order_by(AlertItem.alert_id, AlertItem.position)
    ):
        found[row.alert_id].append(row)
    return found


def replace_items(
    session: Session, *, alert_id: uuid.UUID, items: Sequence[AlertItem]
) -> None:
    session.execute(delete(AlertItem).where(AlertItem.alert_id == alert_id))
    session.add_all(items)
