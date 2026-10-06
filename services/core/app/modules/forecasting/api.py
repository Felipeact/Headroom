import datetime as dt
import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.modules.forecasting.models import Repeats, Schedule
from app.problems import ProblemDetails, ValidationProblemDetails

router = APIRouter(tags=["forecasting"])

SessionDep = Annotated[Session, Depends(get_session)]
OwnerDep = Annotated[Member, Depends(require_member(Role.OWNER))]


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
