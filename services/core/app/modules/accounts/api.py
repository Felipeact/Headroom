import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StrictBool,
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
from app.modules.notifications import service as notifications_service
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


OwnerDep = Annotated[Member, Depends(require_member(service.Role.OWNER))]
BookkeeperDep = Annotated[Member, Depends(require_member(service.Role.BOOKKEEPER))]
MemberDep = Annotated[Member, Depends(require_member(*service.Role))]

# token_urlsafe(32) is 43 characters; anything far longer is no token of ours.
TOKEN_MAX_LENGTH = 128
INVITATION_NOT_FOUND = "Invitation not found."
INVITATION_EXPIRED = "This invitation has expired."
WRONG_ADDRESS = "This invitation was sent to a different email address."
ALREADY_MEMBER = "That person is already a member of this business."
ALREADY_INVITED = "That address already has a pending invitation."
EMAIL_NOT_SENT = "The invitation email could not be sent. Try again."
MEMBER_NOT_FOUND = "Member not found."
OWNER_NOT_REMOVABLE = "Owners can't be removed."
CONTACT_UNAVAILABLE = "We couldn't check your email address. Try again."

Address = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Address


class InvitationCreated(BaseModel):
    id: uuid.UUID
    expires_at: datetime


class BusinessMember(BaseModel):
    user_id: uuid.UUID
    role: service.Role
    name: str | None
    email: str | None
    receive_alert_emails: bool


class PendingInvitation(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime


class MemberList(BaseModel):
    items: list[BusinessMember]
    invitations: list[PendingInvitation]


class InvitationPreview(BaseModel):
    business_name: str
    status: Literal["pending", "expired", "accepted"]


class AlertEmails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


@router.post(
    "/businesses/{business_id}/invitations",
    status_code=status.HTTP_201_CREATED,
    response_model=InvitationCreated,
    responses={
        **MEMBER_ERRORS,
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetails},
        status.HTTP_409_CONFLICT: {"model": ProblemDetails},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemDetails},
    },
)
def create_invitation(
    body: InvitationCreate, member: OwnerDep, session: SessionDep
) -> InvitationCreated:
    try:
        invited = service.invite(
            session,
            business_id=member.business_id,
            inviter_id=member.user_id,
            address=body.email,
            send=notifications_service.send_invitation,
        )
    except service.AlreadyMemberError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=ALREADY_MEMBER) from None
    except service.AlreadyInvitedError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=ALREADY_INVITED) from None
    except notifications_service.InvitationNotSentError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=EMAIL_NOT_SENT
        ) from None
    return InvitationCreated(id=invited.id, expires_at=invited.expires_at)


@router.get(
    "/businesses/{business_id}/members",
    response_model=MemberList,
    responses=MEMBER_ERRORS,
)
def list_members(member: MemberDep, session: SessionDep) -> MemberList:
    found = service.list_members(session, business_id=member.business_id)
    return MemberList(
        items=[
            BusinessMember.model_validate(m, from_attributes=True)
            for m in found.members
        ],
        invitations=[
            PendingInvitation.model_validate(i, from_attributes=True)
            for i in found.invitations
        ],
    )


@router.delete(
    "/businesses/{business_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **MEMBER_ERRORS,
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetails},
        status.HTTP_409_CONFLICT: {"model": ProblemDetails},
    },
)
def remove_member(user_id: uuid.UUID, member: OwnerDep, session: SessionDep) -> None:
    try:
        service.remove_member(
            session,
            business_id=member.business_id,
            actor_user_id=member.user_id,
            user_id=user_id,
        )
    except service.MemberNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=MEMBER_NOT_FOUND
        ) from None
    except service.CannotRemoveOwnerError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=OWNER_NOT_REMOVABLE
        ) from None


@router.put(
    "/businesses/{business_id}/me/alert-emails",
    response_model=BusinessMember,
    responses={
        **MEMBER_ERRORS,
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetails},
    },
)
def set_alert_emails(
    body: AlertEmails, member: BookkeeperDep, session: SessionDep
) -> BusinessMember:
    view = service.set_alert_emails(
        session,
        business_id=member.business_id,
        user_id=member.user_id,
        enabled=body.enabled,
    )
    return BusinessMember.model_validate(view, from_attributes=True)


@router.get(
    "/invitations/{token}",
    response_model=InvitationPreview,
    responses={status.HTTP_404_NOT_FOUND: {"model": ProblemDetails}},
)
def read_invitation(token: str, session: SessionDep) -> InvitationPreview:
    try:
        found = service.invitation_preview(session, token=token[:TOKEN_MAX_LENGTH])
    except service.InvitationNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=INVITATION_NOT_FOUND
        ) from None
    return InvitationPreview(business_name=found.business_name, status=found.status)


@router.post(
    "/invitations/{token}/accept",
    response_model=Business,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ProblemDetails},
        status.HTTP_404_NOT_FOUND: {"model": ProblemDetails},
        status.HTTP_409_CONFLICT: {"model": ProblemDetails},
        status.HTTP_410_GONE: {"model": ProblemDetails},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ProblemDetails},
    },
)
def accept_invitation(token: str, user: CurrentUser, session: SessionDep) -> Business:
    try:
        view = service.accept_invitation(
            session, token=token[:TOKEN_MAX_LENGTH], user_id=user.id
        )
    except service.InvitationNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=INVITATION_NOT_FOUND
        ) from None
    except service.InvitationExpiredError:
        raise HTTPException(status.HTTP_410_GONE, detail=INVITATION_EXPIRED) from None
    except service.WrongAddressError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=WRONG_ADDRESS) from None
    except service.AlreadyMemberError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=ALREADY_MEMBER) from None
    except service.ContactUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=CONTACT_UNAVAILABLE
        ) from None
    return _out(view)
