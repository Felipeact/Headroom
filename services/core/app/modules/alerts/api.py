import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Member, require_member
from app.db import get_session
from app.modules.accounts.service import Role
from app.modules.alerts import service
from app.modules.alerts.models import AlertItemKind, AlertState, FixKind
from app.problems import ProblemDetails, ValidationProblemDetails

router = APIRouter(tags=["alerts"])

SessionDep = Annotated[Session, Depends(get_session)]
OwnerDep = Annotated[Member, Depends(require_member(Role.OWNER))]
# Every role may read; spec 31 adds roles beside the owner.
MemberDep = Annotated[Member, Depends(require_member(*Role))]

ALERT_NOT_FOUND = "Alert not found."
ALERT_RESOLVED = "This alert is already resolved."

READ_ERRORS: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetails},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails},
}
DISMISS_ERRORS: dict[int | str, dict[str, object]] = {
    status.HTTP_403_FORBIDDEN: {"model": ProblemDetails},
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetails},
    status.HTTP_409_CONFLICT: {"model": ProblemDetails},
}


def get_now() -> datetime:
    return datetime.now(UTC)


NowDep = Annotated[datetime, Depends(get_now)]


class AlertItem(BaseModel):
    # `cause`: a large payment going out during the gap or the week before it.
    # `arrives_after`: the largest payment arriving in the 7 days after it.
    kind: AlertItemKind
    date: date
    # Our sign: money in positive, money out negative.
    amount_cents: int
    currency: str
    description: str | None
    counterparty: str | None
    # The forecast item's source: `recurring_pattern`, `expected_payment`, `card_payment`.
    source: str
    schedule: str | None


class Fix(BaseModel):
    # `pay_early`: ask for the payment arriving after the gap a week early.
    # `move_payment`: ask to move the largest cause a week later.
    # `draw_credit`: borrow on a line of credit. `financing`: short-term financing.
    kind: FixKind
    # The payment moved, in our sign; or the amount borrowed, positive.
    amount_cents: int
    currency: str
    # The payment's current date; null when borrowing.
    original_date: date | None
    # When borrowed money is repaid; null for a moved payment.
    repay_on: date | None
    # The payment's new date, or the day the money is borrowed.
    date: date
    # The payment's, or the line of credit's name.
    description: str | None
    counterparty: str | None
    # The line of credit's available credit; `draw_credit` only.
    available_cents: int | None
    # The lowest of the 13 weekly balances if the fix were applied.
    new_lowest_balance_cents: int


class Alert(BaseModel):
    id: uuid.UUID
    state: AlertState
    # The first gap week's Monday and the last gap week's Sunday.
    starts_on: date
    ends_on: date
    lowest_week_starts_on: date
    lowest_balance_cents: int
    minimum_cents: int
    # The minimum minus the lowest balance; always positive.
    shortfall_cents: int
    currency: str
    created_at: datetime
    updated_at: datetime
    dismissed_at: datetime | None
    resolved_at: datetime | None
    # Causes first, by date, then the item arriving after the gap.
    items: list[AlertItem]
    # In kind order: pay_early, move_payment, draw_credit, financing.
    fixes: list[Fix]


class AlertList(BaseModel):
    items: list[Alert]


def _alert(view: service.AlertView) -> Alert:
    return Alert.model_validate(view, from_attributes=True)


@router.get(
    "/businesses/{business_id}/alerts",
    response_model=AlertList,
    responses=READ_ERRORS,
)
def list_alerts(
    member: MemberDep,
    session: SessionDep,
    state: Annotated[AlertState, Query()] = "open",
) -> AlertList:
    views = service.list_alerts(session, business_id=member.business_id, state=state)
    return AlertList(items=[_alert(v) for v in views])


@router.get(
    "/businesses/{business_id}/alerts/{alert_id}",
    response_model=Alert,
    responses=READ_ERRORS,
)
def get_alert(alert_id: uuid.UUID, member: MemberDep, session: SessionDep) -> Alert:
    try:
        view = service.get_alert(
            session, business_id=member.business_id, alert_id=alert_id
        )
    except service.AlertNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=ALERT_NOT_FOUND) from None
    return _alert(view)


@router.post(
    "/businesses/{business_id}/alerts/{alert_id}/dismiss",
    response_model=Alert,
    responses=DISMISS_ERRORS,
)
def dismiss_alert(
    alert_id: uuid.UUID, member: OwnerDep, session: SessionDep, now: NowDep
) -> Alert:
    try:
        view = service.dismiss_alert(
            session, business_id=member.business_id, alert_id=alert_id, now=now
        )
    except service.AlertNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=ALERT_NOT_FOUND) from None
    except service.AlertResolvedError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=ALERT_RESOLVED) from None
    return _alert(view)
