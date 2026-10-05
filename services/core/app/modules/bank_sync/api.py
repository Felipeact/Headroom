import uuid
from datetime import datetime
from typing import Annotated, Literal

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StrictBool,
    StrictStr,
    ValidationError,
    model_validator,
)
from sqlalchemy.orm import Session

from app.auth import Member, require_member
from app.db import get_session
from app.modules.accounts.service import Role
from app.modules.bank_sync import service, webhooks
from app.modules.bank_sync.models import AccountType
from app.modules.bank_sync.plaid import PlaidClient, PlaidError, get_plaid_client
from app.problems import ProblemDetails, ValidationProblemDetails

PROVIDER_UNAVAILABLE = "We couldn't reach our bank connection provider. Try again."
CONNECT_FAILED = "We couldn't finish connecting your bank. Try again."
ALREADY_CONNECTED = "This bank is already connected."
ACCOUNT_NOT_FOUND = "Account not found."
INVALID_SIGNATURE = "Invalid webhook signature."
ACCOUNT_CONFLICTS: dict[service.AccountConflict, str] = {
    "credit": "Credit cards and lines of credit can't count as cash.",
    "other": "This type of account can't count as cash.",
    "currency": "Only Canadian dollar accounts can count as cash for now.",
    "primary_not_included": "Only an account that counts as cash can be primary.",
    "exclude_primary": "Choose another primary account first.",
}

log = structlog.get_logger(__name__)

router = APIRouter(tags=["bank_sync"])
# Mounted outside the authenticated /v1 router (AD-049): Plaid sends no Clerk token, so
# every route here verifies the provider's signature before doing anything else.
webhook_router = APIRouter(tags=["bank_sync"])

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
    body: ConnectionCreate,
    member: OwnerDep,
    plaid: PlaidDep,
    session: SessionDep,
    background: BackgroundTasks,
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
    # The first sync after the response: it pulls the history, and Plaid sends this
    # item's webhooks only once it has been called.
    background.add_task(
        service.sync_in_background,
        plaid,
        business_id=member.business_id,
        connection_id=connection.id,
    )
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


class PlaidWebhook(BaseModel):
    # Plaid adds fields per webhook type; only these three decide anything here.
    webhook_type: StrictStr
    webhook_code: StrictStr
    item_id: StrictStr


class WebhookAck(BaseModel):
    status: Literal["ok"]


async def raw_body(request: Request) -> bytes:
    # The signature covers the exact bytes Plaid sent, so they are read before parsing.
    return await request.body()


@webhook_router.post(
    "/plaid",
    response_model=WebhookAck,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ProblemDetails},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails},
        status.HTTP_502_BAD_GATEWAY: {"model": ProblemDetails},
    },
)
def plaid_webhook(
    body: Annotated[bytes, Depends(raw_body)],
    plaid: PlaidDep,
    session: SessionDep,
    background: BackgroundTasks,
    plaid_verification: Annotated[
        str | None, Header(alias="Plaid-Verification", include_in_schema=False)
    ] = None,
) -> WebhookAck:
    try:
        webhooks.verify(plaid, plaid_verification, body)
    except webhooks.InvalidSignatureError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=INVALID_SIGNATURE
        ) from None
    except PlaidError as exc:
        log.warning(
            "plaid.request_failed",
            error_type=exc.error_type,
            error_code=exc.error_code,
            request_id=exc.request_id,
        )
        raise _unavailable() from None
    try:
        webhook = PlaidWebhook.model_validate_json(body)
    except ValidationError as exc:
        raise RequestValidationError(
            [
                {**error, "loc": ("body", *error["loc"])}
                for error in exc.errors(include_url=False, include_input=False)
            ]
        ) from None

    if (webhook.webhook_type, webhook.webhook_code) != (
        "TRANSACTIONS",
        "SYNC_UPDATES_AVAILABLE",
    ):
        return WebhookAck(status="ok")
    found = service.connection_for_item(session, plaid_item_id=webhook.item_id)
    if found is None:
        # Answered 200 so Plaid stops retrying: an item we do not store has nothing to sync.
        log.info("plaid.webhook_unknown_item", plaid_item_id=webhook.item_id)
        return WebhookAck(status="ok")
    business_id, connection_id = found
    background.add_task(
        service.sync_in_background,
        plaid,
        business_id=business_id,
        connection_id=connection_id,
    )
    return WebhookAck(status="ok")
