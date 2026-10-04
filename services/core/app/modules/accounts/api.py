import uuid
from datetime import datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StringConstraints,
    model_validator,
)
from pydantic_core import PydanticCustomError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Member, require_member
from app.db import get_session
from app.modules.accounts import service
from app.modules.accounts.models import (
    NAME_MAX_LENGTH,
    UNAVAILABLE_PROVINCES,
    Province,
    TimeZone,
)
from app.problems import ProblemDetails, ValidationProblemDetails

ALREADY_OWNS_BUSINESS = "You already own a business."
QUEBEC_UNAVAILABLE = "Headroom isn't available in Quebec yet."

router = APIRouter(tags=["accounts"])

SessionDep = Annotated[Session, Depends(get_session)]


class Me(BaseModel):
    id: uuid.UUID
    clerk_user_id: str
    created_at: datetime


@router.get("/me", response_model=Me)
def read_me(user: CurrentUser) -> Me:
    return Me(id=user.id, clerk_user_id=user.clerk_user_id, created_at=user.created_at)


def _available(province: str) -> str:
    if province in UNAVAILABLE_PROVINCES:
        raise PydanticCustomError("province_not_available", QUEBEC_UNAVAILABLE)
    return province


Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX_LENGTH),
]
AvailableProvince = Annotated[Province, AfterValidator(_available)]


class BusinessCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    province: AvailableProvince
    time_zone: TimeZone


class BusinessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    province: AvailableProvince | None = None
    time_zone: TimeZone | None = None

    @model_validator(mode="after")
    def no_nulls(self) -> Self:
        # Omit a field to keep it; null would erase a required value.
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise PydanticCustomError("null_not_allowed", f"{field} cannot be null")
        return self


class Business(BaseModel):
    id: uuid.UUID
    name: str
    province: Province
    time_zone: TimeZone
    country: str
    currency: str
    role: service.Role
    created_at: datetime


class BusinessList(BaseModel):
    items: list[Business]


def _out(business: service.MemberBusiness) -> Business:
    return Business.model_validate(business, from_attributes=True)


@router.post(
    "/businesses",
    status_code=status.HTTP_201_CREATED,
    response_model=Business,
    responses={
        status.HTTP_409_CONFLICT: {"model": ProblemDetails},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails},
    },
)
def create_business(
    body: BusinessCreate, user: CurrentUser, session: SessionDep
) -> Business:
    try:
        business = service.create_business(
            session,
            user_id=user.id,
            name=body.name,
            province=body.province,
            time_zone=body.time_zone,
        )
    except service.AlreadyOwnsBusinessError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=ALREADY_OWNS_BUSINESS
        ) from None
    return _out(business)


@router.get("/businesses", response_model=BusinessList)
def list_businesses(user: CurrentUser, session: SessionDep) -> BusinessList:
    return BusinessList(
        items=[_out(b) for b in service.list_businesses(session, user.id)]
    )


MEMBER_ERRORS: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetails},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails},
}


@router.get(
    "/businesses/{business_id}", response_model=Business, responses=MEMBER_ERRORS
)
def read_business(
    member: Annotated[Member, Depends(require_member(*service.Role))],
    session: SessionDep,
) -> Business:
    return _out(
        service.get_business(session, business_id=member.business_id, role=member.role)
    )


@router.patch(
    "/businesses/{business_id}",
    response_model=Business,
    responses=MEMBER_ERRORS,
)
def update_business(
    body: BusinessUpdate,
    member: Annotated[Member, Depends(require_member(service.Role.OWNER))],
    session: SessionDep,
) -> Business:
    return _out(
        service.update_business(
            session,
            business_id=member.business_id,
            user_id=member.user_id,
            role=member.role,
            changes=body.model_dump(exclude_unset=True),
        )
    )
