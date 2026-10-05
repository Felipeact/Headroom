import uuid
from datetime import datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StrictBool,
    model_validator,
)
from sqlalchemy.orm import Session

from app.auth import Member, require_member
from app.db import get_session
from app.modules.accounts.service import Role
from app.modules.bank_sync import service
from app.modules.bank_sync.models import AccountType
from app.modules.bank_sync.plaid import PlaidClient, PlaidError, get_plaid_client
from app.problems import ProblemDetails, ValidationProblemDetails

PROVIDER_UNAVAILABLE = "We couldn't reach our bank connection provider. Try again."
CONNECT_FAILED = "We couldn't finish connecting your bank. Try again."
ALREADY_CONNECTED = "This bank is already connected."
ACCOUNT_NOT_FOUND = "Account not found."
ACCOUNT_CONFLICTS: dict[service.AccountConflict, str] = {
    "credit": "Credit cards and lines of credit can't count as cash.",
    "other": "This type of account can't count as cash.",
    "currency": "Only Canadian dollar accounts can count as cash for now.",
    "primary_not_included": "Only an account that counts as cash can be primary.",
    "exclude_primary": "Choose another primary account first.",
}

log = structlog.get_logger(__name__)

router = APIRouter(tags=["bank_sync"])

SessionDep = Annotated[Session, Depends(get_session)]
PlaidDep = Annotated[PlaidClient, Depends(get_plaid_client)]
OwnerDep = Annotated[Member, Depends(require_member(Role.OWNER))]

OWNER_ERRORS: dict[int | str, dict[str, object]] = {
    status.HTTP_403_FORBIDDEN: {"model": ProblemDetails},
    status.HTTP_404_NOT_FOUND: {"model": ProblemDetails},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails},
    status.HTTP_502_BAD_GATEWAY: {"model": ProblemDetails},
}


class LinkToken(BaseModel):
    link_token: str
    expiration: datetime


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # SecretStr: the token never shows in a repr, a log line or an error report.
    public_token: Annotated[SecretStr, Field(min_length=1)]


class Account(BaseModel):
    id: uuid.UUID
    name: str
    type: AccountType
    mask: str | None
    currency: str
    balance_cents: int | None
    available_cents: int | None
    included: bool
    primary: bool


class Connection(BaseModel):
    id: uuid.UUID
    institution_name: str
    created_at: datetime
    accounts: list[Account]


class ConnectionList(BaseModel):
    items: list[Connection]


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Strict: "yes" or 1 is a malformed body, not a choice.
    included: StrictBool | None = None
    # Only true: a business never chooses to have no primary account.
    primary: Literal[True] | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "AccountUpdate":
        if self.included is None and self.primary is None:
            raise ValueError("Send included, primary, or both.")
        return self


def _plaid_failed(exc: PlaidError, *, business_id: uuid.UUID) -> None:
    log.warning(
        "plaid.request_failed",
        business_id=str(business_id),
        error_type=exc.error_type,
        error_code=exc.error_code,
        request_id=exc.request_id,
    )


def _unavailable() -> HTTPException:
    return HTTPException(status.HTTP_502_BAD_GATEWAY, detail=PROVIDER_UNAVAILABLE)


@router.post(
    "/businesses/{business_id}/bank/link-token",
    response_model=LinkToken,
    responses=OWNER_ERRORS,
)
def create_link_token(member: OwnerDep, plaid: PlaidDep) -> LinkToken:
    try:
        token = service.create_link_token(plaid, user_id=member.user_id)
    except PlaidError as exc:
        _plaid_failed(exc, business_id=member.business_id)
        raise _unavailable() from None
    return LinkToken(link_token=token.link_token, expiration=token.expiration)


@router.post(
    "/businesses/{business_id}/bank/connections",
    status_code=status.HTTP_201_CREATED,
    response_model=Connection,
    responses={
        **OWNER_ERRORS,
        status.HTTP_400_BAD_REQUEST: {"model": ProblemDetails},
        status.HTTP_409_CONFLICT: {"model": ProblemDetails},
    },
)
def create_connection(
    body: ConnectionCreate, member: OwnerDep, plaid: PlaidDep, session: SessionDep
) -> Connection:
    try:
        connection = service.connect_bank(
            session,
            plaid,
            business_id=member.business_id,
            user_id=member.user_id,
            public_token=body.public_token.get_secret_value(),
        )
    except service.DuplicateBankError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=ALREADY_CONNECTED
        ) from None
    except PlaidError as exc:
        _plaid_failed(exc, business_id=member.business_id)
        if exc.error_type == "INVALID_INPUT":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=CONNECT_FAILED
            ) from None
        raise _unavailable() from None
    return Connection.model_validate(connection, from_attributes=True)


@router.get(
    "/businesses/{business_id}/bank/connections",
    response_model=ConnectionList,
    responses={
        k: v for k, v in OWNER_ERRORS.items() if k != status.HTTP_502_BAD_GATEWAY
    },
)
def list_connections(member: OwnerDep, session: SessionDep) -> ConnectionList:
    connections = service.list_connections(session, business_id=member.business_id)
    return ConnectionList.model_validate({"items": connections}, from_attributes=True)


@router.patch(
    "/businesses/{business_id}/bank/accounts/{account_id}",
    response_model=Account,
    responses={
        **{k: v for k, v in OWNER_ERRORS.items() if k != status.HTTP_502_BAD_GATEWAY},
        status.HTTP_409_CONFLICT: {"model": ProblemDetails},
    },
)
def update_account(
    account_id: uuid.UUID, body: AccountUpdate, member: OwnerDep, session: SessionDep
) -> Account:
    try:
        account = service.update_account(
            session,
            business_id=member.business_id,
            account_id=account_id,
            user_id=member.user_id,
            included=body.included,
            primary=body.primary is True,
        )
    except service.AccountNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=ACCOUNT_NOT_FOUND
        ) from None
    except service.AccountRuleError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=ACCOUNT_CONFLICTS[exc.reason]
        ) from None
    return Account.model_validate(account, from_attributes=True)
