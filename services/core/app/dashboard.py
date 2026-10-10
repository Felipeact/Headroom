"""The dashboard's one read (spec 26, AD-102, AD-103).

An app-level read router: it owns no tables and no events, and reads the modules only
through their `service.py`. Its response models are its own, so a module's API can change
without changing this contract by accident.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Member, require_member
from app.db import get_session
from app.modules.accounts import service as accounts_service
from app.modules.alerts import service as alerts_service
from app.modules.bank_sync import service as bank_sync_service
from app.modules.forecasting import service as forecasting_service
from app.problems import ProblemDetails, ValidationProblemDetails

router = APIRouter(tags=["dashboard"])

SessionDep = Annotated[Session, Depends(get_session)]
# Every role may read; spec 31 adds roles beside the owner.
MemberDep = Annotated[Member, Depends(require_member(*accounts_service.Role))]

UPCOMING_DAYS = 14
CASH_TYPES = ("checking", "savings")


def get_now() -> datetime:
    return datetime.now(UTC)


NowDep = Annotated[datetime, Depends(get_now)]


class DashboardAccount(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    institution_name: str
    name: str
    type: bank_sync_service.AccountType
    mask: str | None
    currency: str
    # A card's amount owed, or a cash account's balance; null when the bank sent none.
    balance_cents: int | None
    available_cents: int | None
    included: bool
    primary: bool
    # The card's next forecast payment; null for every other type.
    next_payment_on: date | None


class DashboardConnection(BaseModel):
    id: uuid.UUID
    institution_name: str
    status: bank_sync_service.ConnectionStatus
    last_synced_at: datetime | None


class DashboardWeek(BaseModel):
    number: int
    starts_on: date
    ends_on: date
    end_balance_cents: int
    low_cents: int
    high_cents: int


class DashboardForecast(BaseModel):
    id: uuid.UUID
    computed_at: datetime
    opening_balance_cents: int
    incomplete: bool
    weeks: list[DashboardWeek]


class ProjectedLow(BaseModel):
    week_starts_on: date
    balance_cents: int


class NextCardPayment(BaseModel):
    # The card being paid.
    account_id: uuid.UUID
    date: date
    # Our sign: negative, money going out.
    amount_cents: int


class DashboardAlertItem(BaseModel):
    kind: alerts_service.AlertItemKind
    date: date
    amount_cents: int
    currency: str
    description: str | None
    counterparty: str | None
    source: str
    schedule: str | None


class DashboardFix(BaseModel):
    kind: alerts_service.FixKind
    amount_cents: int
    currency: str
    original_date: date | None
    repay_on: date | None
    date: date
    description: str | None
    counterparty: str | None
    available_cents: int | None
    new_lowest_balance_cents: int


class DashboardAlert(BaseModel):
    id: uuid.UUID
    state: alerts_service.AlertState
    starts_on: date
    ends_on: date
    lowest_week_starts_on: date
    lowest_balance_cents: int
    minimum_cents: int
    shortfall_cents: int
    currency: str
    created_at: datetime
    updated_at: datetime
    dismissed_at: datetime | None
    resolved_at: datetime | None
    items: list[DashboardAlertItem]
    fixes: list[DashboardFix]


class DashboardItem(BaseModel):
    id: uuid.UUID
    date: date
    account_id: uuid.UUID
    # Our sign: money in positive, money out negative.
    amount_cents: int
    currency: str
    source: forecasting_service.ItemSource
    source_id: uuid.UUID | None
    description: str | None
    counterparty: str | None
    schedule: forecasting_service.Schedule | None


class Dashboard(BaseModel):
    # The business-local today.
    as_of: date
    currency: str
    cash_on_hand_cents: int
    # Null when the business has no line of credit.
    available_credit_cents: int | None
    # Null while unset.
    minimum_balance_cents: int | None
    projected_low: ProjectedLow | None
    next_card_payment: NextCardPayment | None
    accounts: list[DashboardAccount]
    connections: list[DashboardConnection]
    forecast: DashboardForecast | None
    # Open alerts only, by `starts_on` then `id`.
    alerts: list[DashboardAlert]
    # The next 14 days' named payments.
    upcoming: list[DashboardItem]


def _cash_on_hand(accounts: list[bank_sync_service.AccountView]) -> int:
    return sum(
        a.balance_cents or 0 for a in accounts if a.included and a.type in CASH_TYPES
    )


def _available_credit(
    accounts: list[bank_sync_service.AccountView], currency: str
) -> int | None:
    lines = [a for a in accounts if a.type == "line_of_credit"]
    if not lines:
        return None
    return sum(a.available_cents or 0 for a in lines if a.currency == currency)


@router.get(
    "/businesses/{business_id}/dashboard",
    response_model=Dashboard,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetails},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails},
    },
)
def get_dashboard(member: MemberDep, session: SessionDep, now: NowDep) -> Dashboard:
    business_id = member.business_id
    business = accounts_service.get_business(
        session, business_id=business_id, role=member.role
    )
    today = now.astimezone(ZoneInfo(business.time_zone)).date()
    connections = bank_sync_service.list_connections(session, business_id=business_id)
    accounts = [a for c in connections for a in c.accounts]
    forecast = forecasting_service.latest_forecast(
        session, business_id=business_id, now=now
    )
    minimum = forecasting_service.minimum_balance_amount(
        session, business_id=business_id
    )

    card_payments = sorted(
        (
            i
            for i in (forecast.items if forecast else [])
            if i.source == "card_payment" and i.date >= today
        ),
        key=lambda i: (i.date, i.id),
    )
    next_on: dict[uuid.UUID, date] = {}
    for item in card_payments:
        if item.source_id is not None:
            next_on.setdefault(item.source_id, item.date)
    low = min(forecast.weeks, key=lambda w: w.end_balance_cents) if forecast else None
    first_card = card_payments[0] if card_payments else None

    return Dashboard(
        as_of=today,
        currency=business.currency,
        cash_on_hand_cents=_cash_on_hand(accounts),
        available_credit_cents=_available_credit(accounts, business.currency),
        minimum_balance_cents=None if minimum is None else minimum[0],
        projected_low=None
        if low is None
        else ProjectedLow(
            week_starts_on=low.starts_on, balance_cents=low.end_balance_cents
        ),
        next_card_payment=None
        if first_card is None or first_card.source_id is None
        else NextCardPayment(
            account_id=first_card.source_id,
            date=first_card.date,
            amount_cents=first_card.amount_cents,
        ),
        accounts=[
            DashboardAccount(
                id=a.id,
                connection_id=c.id,
                institution_name=c.institution_name,
                name=a.name,
                type=a.type,
                mask=a.mask,
                currency=a.currency,
                balance_cents=a.balance_cents,
                available_cents=a.available_cents,
                included=a.included,
                primary=a.primary,
                next_payment_on=next_on.get(a.id) if a.type == "credit_card" else None,
            )
            for c in connections
            for a in c.accounts
        ],
        connections=[
            DashboardConnection.model_validate(c, from_attributes=True)
            for c in connections
        ],
        forecast=None
        if forecast is None
        else DashboardForecast.model_validate(forecast, from_attributes=True),
        alerts=[
            DashboardAlert.model_validate(a, from_attributes=True)
            for a in alerts_service.list_alerts(
                session, business_id=business_id, state="open"
            )
        ],
        upcoming=[
            DashboardItem.model_validate(i, from_attributes=True)
            for i in forecasting_service.upcoming_items(
                session, business_id=business_id, now=now, days=UPCOMING_DAYS
            )
            or []
        ],
    )
