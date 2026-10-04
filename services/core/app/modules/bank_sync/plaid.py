"""The Plaid port: the only place that talks to Plaid (AD-036).

Routes get a `PlaidClient` through `get_plaid_client`; tests override it with a fake. Every
method returns plain dataclasses, and every failure is a `PlaidError` carrying only Plaid's
error type, code and request ID, never the response body.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import Any, Protocol

import urllib3
from plaid import ApiClient, ApiException, Configuration, Environment
from plaid.api.plaid_api import PlaidApi
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_transactions import LinkTokenTransactions
from plaid.model.products import Products

from app.settings import get_settings

TIMEOUT_SECONDS = 15
INSTITUTION_COUNTRY_CODES = ("CA",)


class PlaidError(Exception):
    """A Plaid call failed or timed out."""

    def __init__(
        self,
        *,
        error_type: str | None,
        error_code: str | None,
        request_id: str | None,
    ) -> None:
        super().__init__(f"Plaid error {error_type}/{error_code} ({request_id})")
        self.error_type = error_type
        self.error_code = error_code
        self.request_id = request_id


@dataclass(frozen=True)
class LinkTokenRequest:
    client_user_id: str
    client_name: str
    language: str
    country_codes: tuple[str, ...]
    products: tuple[str, ...]
    days_requested: int


@dataclass(frozen=True)
class LinkToken:
    link_token: str
    expiration: datetime


@dataclass(frozen=True)
class ExchangedItem:
    item_id: str
    access_token: str = field(repr=False)


@dataclass(frozen=True)
class PlaidAccount:
    account_id: str
    name: str
    type: str
    subtype: str | None
    mask: str | None
    current: float | None
    iso_currency_code: str | None
    unofficial_currency_code: str | None


@dataclass(frozen=True)
class ItemAccounts:
    institution_id: str
    accounts: list[PlaidAccount]


class PlaidClient(Protocol):
    def create_link_token(self, request: LinkTokenRequest) -> LinkToken: ...

    def exchange_public_token(self, public_token: str) -> ExchangedItem: ...

    def get_accounts(self, access_token: str) -> ItemAccounts: ...

    def get_institution_name(self, institution_id: str) -> str: ...

    def remove_item(self, access_token: str) -> None: ...


def _error_from(exc: ApiException) -> PlaidError:
    try:
        body = json.loads(exc.body or "{}")
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    return PlaidError(
        error_type=body.get("error_type"),
        error_code=body.get("error_code"),
        request_id=body.get("request_id"),
    )


def _value(enum: Any) -> str | None:
    return None if enum is None else str(enum.value)


class SdkPlaidClient:
    """`PlaidClient` over the official `plaid-python` SDK."""

    def __init__(self, api: PlaidApi) -> None:
        self._api = api

    def _call(self, method: Any, request: Any) -> Any:
        try:
            return method(request, _request_timeout=TIMEOUT_SECONDS)
        except ApiException as exc:
            raise _error_from(exc) from None
        except urllib3.exceptions.HTTPError as exc:
            # Timeouts and connection failures; urllib3 raises them past the SDK.
            raise PlaidError(
                error_type="NETWORK", error_code=type(exc).__name__, request_id=None
            ) from None

    def create_link_token(self, request: LinkTokenRequest) -> LinkToken:
        response = self._call(
            self._api.link_token_create,
            LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=request.client_user_id),
                client_name=request.client_name,
                language=request.language,
                country_codes=[CountryCode(c) for c in request.country_codes],
                products=[Products(p) for p in request.products],
                transactions=LinkTokenTransactions(
                    days_requested=request.days_requested
                ),
            ),
        )
        return LinkToken(link_token=response.link_token, expiration=response.expiration)

    def exchange_public_token(self, public_token: str) -> ExchangedItem:
        response = self._call(
            self._api.item_public_token_exchange,
            ItemPublicTokenExchangeRequest(public_token=public_token),
        )
        return ExchangedItem(
            item_id=response.item_id, access_token=response.access_token
        )

    def get_accounts(self, access_token: str) -> ItemAccounts:
        response = self._call(
            self._api.accounts_get, AccountsGetRequest(access_token=access_token)
        )
        institution_id = response.item.get("institution_id")
        if not institution_id:
            raise PlaidError(
                error_type="INVALID_RESPONSE",
                error_code="NO_INSTITUTION",
                request_id=response.get("request_id"),
            )
        return ItemAccounts(
            institution_id=institution_id,
            accounts=[
                PlaidAccount(
                    account_id=a.account_id,
                    name=a.name,
                    type=str(_value(a.type)),
                    subtype=_value(a.get("subtype")),
                    mask=a.get("mask"),
                    current=a.balances.get("current"),
                    iso_currency_code=a.balances.get("iso_currency_code"),
                    unofficial_currency_code=a.balances.get("unofficial_currency_code"),
                )
                for a in response.accounts
            ],
        )

    def get_institution_name(self, institution_id: str) -> str:
        response = self._call(
            self._api.institutions_get_by_id,
            InstitutionsGetByIdRequest(
                institution_id=institution_id,
                country_codes=[CountryCode(c) for c in INSTITUTION_COUNTRY_CODES],
            ),
        )
        return str(response.institution.name)

    def remove_item(self, access_token: str) -> None:
        self._call(self._api.item_remove, ItemRemoveRequest(access_token=access_token))


@lru_cache
def get_plaid_client() -> PlaidClient:
    settings = get_settings()
    configuration = Configuration(
        host=(
            Environment.Sandbox
            if settings.plaid_env == "sandbox"
            else Environment.Production
        ),
        api_key={"clientId": settings.plaid_client_id, "secret": settings.plaid_secret},
    )
    return SdkPlaidClient(PlaidApi(ApiClient(configuration)))
