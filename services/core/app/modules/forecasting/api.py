import datetime as dt
import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    field_validator,
)
from sqlalchemy.orm import Session

from app.auth import Member, require_member
from app.db import get_session
from app.modules.accounts.service import Role
from app.modules.forecasting import service
from app.modules.forecasting.models import ItemSource, Repeats, Schedule
from app.problems import ProblemDetails, ValidationProblemDetails

router = APIRouter(tags=["forecasting"])

SessionDep = Annotated[Session, Depends(get_session)]
OwnerDep = Annotated[Member, Depends(require_member(Role.OWNER))]
# Every role may read; spec 31 adds roles beside the owner.
MemberDep = Annotated[Member, Depends(require_member(*Role))]


class RecurringPattern(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    counterparty: str
    description: str
    schedule: Schedule
    # Our sign: money in positive, money out negative.
    amount_cents: int
    currency: str
    next_date: date
    # 0 to 100.
    confidence: int
    # The transactions the pattern came from, oldest first.
    transaction_ids: list[uuid.UUID]


class RecurringPatternList(BaseModel):
    items: list[RecurringPattern]


@router.get(
    "/businesses/{business_id}/recurring-patterns",
    response_model=RecurringPatternList,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetails},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetails},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails},
    },
)
def list_recurring_patterns(
    member: OwnerDep, session: SessionDep
) -> RecurringPatternList:
    return RecurringPatternList(
        items=[
            RecurringPattern.model_validate(p, from_attributes=True)
            for p in service.list_patterns(session, business_id=member.business_id)
        ]
    )


# The clock for "today" in the business's time zone; tests override it.
def get_now() -> datetime:
    return datetime.now(UTC)


NowDep = Annotated[datetime, Depends(get_now)]

PAYMENT_NOT_FOUND = "Expected payment not found."
ACCOUNT_CHOICES: dict[service.AccountChoice, str] = {
    "not_cash": "Choose an account you count as cash.",
    "no_primary": "Connect a bank before adding expected payments.",
}
MAX_AMOUNT_CENTS = 9_999_999_999


class ExpectedPayment(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    description: str
    # Our sign: money in positive, money out negative.
    amount_cents: int
    currency: str
    # The first occurrence.
    date: date
    repeats: Repeats | None
    # The earliest occurrence still to come; null once a one-off is matched.
    next_date: dt.date | None
    # `next_date` is earlier than today.
    overdue: bool


class ExpectedPaymentList(BaseModel):
    items: list[ExpectedPayment]


class ExpectedPaymentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The business's primary account when left out.
    account_id: uuid.UUID | None = None
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    amount_cents: StrictInt = Field(ge=-MAX_AMOUNT_CENTS, le=MAX_AMOUNT_CENTS)
    date: date
    repeats: Repeats | None = None

    @field_validator("amount_cents")
    @classmethod
    def _nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("The amount can't be zero.")
        return value


PAYMENT_ERRORS: dict[int | str, dict[str, object]] = {
    status.HTTP_403_FORBIDDEN: {"model": ProblemDetails},
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetails},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails},
}
WRITE_ERRORS: dict[int | str, dict[str, object]] = {
    **PAYMENT_ERRORS,
    status.HTTP_409_CONFLICT: {"model": ProblemDetails},
}


def _save(
    session: Session,
    member: Member,
    now: datetime,
    body: ExpectedPaymentBody,
    payment_id: uuid.UUID | None,
) -> ExpectedPayment:
    try:
        view = service.save_expected_payment(
            session,
            business_id=member.business_id,
            user_id=member.user_id,
            payment_id=payment_id,
            account_id=body.account_id,
            description=body.description,
            amount_cents=body.amount_cents,
            day=body.date,
            repeats=body.repeats,
            now=now,
        )
    except service.ExpectedPaymentNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=PAYMENT_NOT_FOUND
        ) from None
    except service.AccountChoiceError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=ACCOUNT_CHOICES[exc.reason]
        ) from None
    except service.DateOutOfRangeError:
        raise RequestValidationError(
            [
                {
                    "loc": ("body", "date"),
                    "msg": "The date must be within 90 days before and 730 days after today.",
                    "type": "value_error",
                }
            ]
        ) from None
    return ExpectedPayment.model_validate(view, from_attributes=True)


@router.get(
    "/businesses/{business_id}/expected-payments",
    response_model=ExpectedPaymentList,
    responses=PAYMENT_ERRORS,
)
def list_expected_payments(
    member: OwnerDep, session: SessionDep, now: NowDep
) -> ExpectedPaymentList:
    return ExpectedPaymentList(
        items=[
            ExpectedPayment.model_validate(p, from_attributes=True)
            for p in service.list_expected_payments(
                session, business_id=member.business_id, now=now
            )
        ]
    )


@router.post(
    "/businesses/{business_id}/expected-payments",
    response_model=ExpectedPayment,
    status_code=status.HTTP_201_CREATED,
    responses=WRITE_ERRORS,
)
def create_expected_payment(
    body: ExpectedPaymentBody, member: OwnerDep, session: SessionDep, now: NowDep
) -> ExpectedPayment:
    return _save(session, member, now, body, None)


@router.put(
    "/businesses/{business_id}/expected-payments/{payment_id}",
    response_model=ExpectedPayment,
    responses=WRITE_ERRORS,
)
def update_expected_payment(
    payment_id: uuid.UUID,
    body: ExpectedPaymentBody,
    member: OwnerDep,
    session: SessionDep,
    now: NowDep,
) -> ExpectedPayment:
    return _save(session, member, now, body, payment_id)


FORECAST_NOT_READY = "Forecast not ready."
UPCOMING_DAYS = 14
MAX_UPCOMING_DAYS = 90


class ForecastItem(BaseModel):
    id: uuid.UUID
    date: date
    account_id: uuid.UUID
    # Our sign: money in positive, money out negative.
    amount_cents: int
    currency: str
    source: ItemSource
    # The pattern, expected payment or card account; null for an estimate.
    source_id: uuid.UUID | None
    # Null only for an estimate.
    description: str | None
    counterparty: str | None
    schedule: Schedule | None


class ForecastWeek(BaseModel):
    number: int
    # A Monday, and the Sunday after it.
    starts_on: date
    ends_on: date
    end_balance_cents: int
    low_cents: int
    high_cents: int
    money_in_cents: int
    # 0 or less.
    money_out_cents: int
    # By date, source, then ID.
    item_ids: list[uuid.UUID]


class Forecast(BaseModel):
    id: uuid.UUID
    # The business-local day the forecast was made on.
    as_of: date
    computed_at: datetime
    strategy: str
    currency: str
    opening_balance_cents: int
    # An included bank needs attention or hasn't synced for 48 hours.
    incomplete: bool
    # Weeks 1 to 13.
    weeks: list[ForecastWeek]
    # By date, source, then ID.
    items: list[ForecastItem]


class ForecastItemList(BaseModel):
    items: list[ForecastItem]


@router.get(
    "/businesses/{business_id}/forecast",
    response_model=Forecast,
    responses=PAYMENT_ERRORS,
)
def get_forecast(member: OwnerDep, session: SessionDep, now: NowDep) -> Forecast:
    view = service.latest_forecast(session, business_id=member.business_id, now=now)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=FORECAST_NOT_READY)
    return Forecast.model_validate(view, from_attributes=True)


@router.get(
    "/businesses/{business_id}/upcoming",
    response_model=ForecastItemList,
    responses=PAYMENT_ERRORS,
)
def list_upcoming(
    member: OwnerDep,
    session: SessionDep,
    now: NowDep,
    days: Annotated[int, Query(ge=1, le=MAX_UPCOMING_DAYS)] = UPCOMING_DAYS,
) -> ForecastItemList:
    items = service.upcoming_items(
        session, business_id=member.business_id, now=now, days=days
    )
    if items is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=FORECAST_NOT_READY)
    return ForecastItemList(
        items=[ForecastItem.model_validate(i, from_attributes=True) for i in items]
    )


@router.delete(
    "/businesses/{business_id}/expected-payments/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=PAYMENT_ERRORS,
)
def delete_expected_payment(
    payment_id: uuid.UUID, member: OwnerDep, session: SessionDep
) -> None:
    try:
        service.delete_expected_payment(
            session,
            business_id=member.business_id,
            user_id=member.user_id,
            payment_id=payment_id,
        )
    except service.ExpectedPaymentNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=PAYMENT_NOT_FOUND
        ) from None


MAX_MINIMUM_CENTS = 1_000_000_000


class MinimumBalance(BaseModel):
    # Null until the owner sets one.
    amount_cents: int | None
    currency: str
    # About two weeks of typical spending; null without a complete week of history.
    suggested_cents: int | None
    updated_at: datetime | None


class MinimumBalanceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: StrictInt = Field(ge=0, le=MAX_MINIMUM_CENTS)


@router.get(
    "/businesses/{business_id}/minimum-balance",
    response_model=MinimumBalance,
    responses=PAYMENT_ERRORS,
)
def get_minimum_balance(
    member: MemberDep, session: SessionDep, now: NowDep
) -> MinimumBalance:
    view = service.get_minimum_balance(session, business_id=member.business_id, now=now)
    return MinimumBalance.model_validate(view, from_attributes=True)


@router.put(
    "/businesses/{business_id}/minimum-balance",
    response_model=MinimumBalance,
    responses=PAYMENT_ERRORS,
)
def put_minimum_balance(
    body: MinimumBalanceBody, member: OwnerDep, session: SessionDep, now: NowDep
) -> MinimumBalance:
    view = service.set_minimum_balance(
        session,
        business_id=member.business_id,
        user_id=member.user_id,
        amount_cents=body.amount_cents,
        now=now,
    )
    return MinimumBalance.model_validate(view, from_attributes=True)


class ForecastStatus(BaseModel):
    # needs_attention: an included bank needs a new login.
    state: service.ForecastState
    # Oldest connection first.
    institution_names: list[str]
    # Every bank with an included account has synced at least once.
    transactions_read: bool
    # Whole months back to the oldest transaction; null with none.
    history_months: int | None
    recurring_count: int
    # At most 2, the largest first.
    recurring_names: list[str]


@router.get(
    "/businesses/{business_id}/forecast/status",
    response_model=ForecastStatus,
    responses=PAYMENT_ERRORS,
)
def get_forecast_status(
    member: MemberDep, session: SessionDep, now: NowDep
) -> ForecastStatus:
    view = service.forecast_status(session, business_id=member.business_id, now=now)
    return ForecastStatus.model_validate(view, from_attributes=True)
