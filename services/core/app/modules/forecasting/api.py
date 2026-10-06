import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Member, require_member
from app.db import get_session
from app.modules.accounts.service import Role
from app.modules.forecasting import service
from app.modules.forecasting.models import Schedule
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
