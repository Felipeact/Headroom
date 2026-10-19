"""The Yodlee port: the only place that talks to Yodlee (spec 17b, door 3).

Routes get a `YodleeClient` through `get_yodlee_client`; tests override it with a fake. Every
method returns plain dataclasses, and every failure is a `YodleeError` carrying only the
HTTP status and Yodlee's error code, never the response body. Accounts and transactions come
out in the shapes `bank_sync.service` already takes from Plaid (`PlaidAccount`,
`PlaidTransaction`: positive amount is money out).

Request and response shapes were pinned against the Yodlee sandbox on 2026-10-18 and its
docs (FastLink 4, data model).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.modules.bank_sync.plaid import PlaidAccount, PlaidTransaction
from app.settings import Settings, get_settings

TIMEOUT_SECONDS = 15
API_VERSION = "1.1"
# Yodlee's answer to a token request for a loginName it does not know.
USER_NOT_REGISTERED = "Y305"
# Our error code for a provider account that needs the owner to log in again.
LOGIN_REQUIRED = "LOGIN_REQUIRED"
# The dataset `additionalStatus` values that mean the owner must act at the bank
# (Yodlee's refresh-status documentation). Anything else is an ordinary failure.
LOGIN_REQUIRED_STATUSES = frozenset(
    {
        "ACCOUNT_LOCKED",
        "ADDL_AUTHENTICATION_REQUIRED",
        "CREDENTIALS_UPDATE_NEEDED",
        "NEW_AUTHENTICATION_REQUIRED",
    }
)
TRANSACTIONS_PAGE_SIZE = 500
# A guard against an API that ignores `skip`: 100 pages is 50,000 transactions.
MAX_TRANSACTION_PAGES = 100
# Only these containers hold accounts we store (checking and savings, credit cards).
CONTAINERS = ("bank", "creditCard")


class YodleeError(Exception):
    """A Yodlee call failed or timed out; carries no response body."""

    def __init__(self, *, http_status: int | None, error_code: str | None) -> None:
        super().__init__(f"Yodlee error {http_status}/{error_code}")
        self.http_status = http_status
        self.error_code = error_code


@dataclass(frozen=True)
class FastLinkLaunch:
    """What the browser needs to open FastLink for one user."""

    fastlink_url: str
    access_token: str = field(repr=False)
    config_name: str
    expires_in: int
    # Set only to edit (re-authenticate) an existing provider account.
    provider_account_id: str | None = None


@dataclass(frozen=True)
class ProviderAccountStatus:
    provider_id: str
    # When Yodlee last retrieved data successfully; None if it never did.
    last_refreshed: datetime | None
    needs_login: bool


class YodleeClient(Protocol):
    def register_user(self, login_name: str) -> None: ...

    def launch(
        self, login_name: str, provider_account_id: str | None
    ) -> FastLinkLaunch: ...

    def provider_account(
        self, login_name: str, provider_account_id: str
    ) -> ProviderAccountStatus: ...

    def accounts(
        self, login_name: str, provider_account_id: str
    ) -> list[PlaidAccount]: ...

    def transactions(
        self, login_name: str, account_ids: frozenset[str], from_date: date
    ) -> list[PlaidTransaction]: ...

    def delete_provider_account(
        self, login_name: str, provider_account_id: str
    ) -> None: ...


def login_name_for(business_id: uuid.UUID) -> str:
    """The Yodlee loginName of a business's user: the sandbox test user when configured."""
    return get_settings().yodlee_test_login_name or f"hr-{business_id.hex}"


def yodlee_enabled(settings: Settings) -> bool:
    """Yodlee is on only when all six settings are set."""
    return all(
        (
            settings.yodlee_api_url,
            settings.yodlee_client_id,
            settings.yodlee_client_secret,
            settings.yodlee_admin_login_name,
            settings.yodlee_fastlink_url,
            settings.yodlee_fastlink_config_name,
        )
    )


def _money(value: Any) -> tuple[float | None, str | None]:
    if not isinstance(value, dict):
        return None, None
    return value.get("amount"), value.get("currency")


def _account(a: dict[str, Any]) -> PlaidAccount:
    amount, currency = _money(a.get("balance"))
    subtype: str | None
    if a.get("CONTAINER") == "creditCard":
        available, _ = _money(a.get("availableCredit"))
        type_, subtype = "credit", "credit card"
    else:
        available, _ = _money(a.get("availableBalance") or a.get("availableCash"))
        type_ = "depository"
        subtype = {"CHECKING": "checking", "SAVINGS": "savings"}.get(
            str(a.get("accountType"))
        )
    number = a.get("accountNumber")
    return PlaidAccount(
        account_id=str(a["id"]),
        name=str(a.get("accountName") or ""),
        type=type_,
        subtype=subtype,
        # Only the last four characters are kept: a full account number never leaves here.
        mask=number[-4:] if isinstance(number, str) and len(number) >= 4 else None,
        current=amount,
        available=available,
        iso_currency_code=currency,
        unofficial_currency_code=None,
    )


def _transaction(t: dict[str, Any]) -> PlaidTransaction:
    amount, currency = _money(t.get("amount"))
    if amount is None:
        raise YodleeError(http_status=None, error_code="INVALID_RESPONSE")
    description = t.get("description") or {}
    return PlaidTransaction(
        transaction_id=f"yodlee:{t['id']}",
        account_id=str(t["accountId"]),
        # Plaid's convention: positive is money out. Yodlee reports a magnitude and
        # a base type; the one flip into our own sign stays in `service._values`.
        amount=amount if t.get("baseType") == "DEBIT" else -amount,
        iso_currency_code=currency,
        unofficial_currency_code=None,
        date=date.fromisoformat(t["date"]),
        pending=False,
        pending_transaction_id=None,
        name=description.get("simple") or description.get("original") or "",
        merchant_name=None,
        counterparties=(),
        category=None,
        category_detailed=None,
    )


class HttpxYodleeClient:
    """`YodleeClient` over `httpx`."""

    def __init__(
        self, settings: Settings, transport: httpx.BaseTransport | None = None
    ) -> None:
        assert settings.yodlee_api_url is not None
        self._settings = settings
        self._http = httpx.Client(
            base_url=settings.yodlee_api_url.rstrip("/"),
            timeout=TIMEOUT_SECONDS,
            headers={"Api-Version": API_VERSION},
            transport=transport,
        )

    def _send(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        login_name: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = {} if token is None else {"Authorization": f"Bearer {token}"}
        if login_name is not None:
            headers["loginName"] = login_name
        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise YodleeError(http_status=None, error_code="NETWORK") from None
        if response.status_code >= 400:
            code = None
            try:
                body = response.json()
                if isinstance(body, dict):
                    code = body.get("errorCode")
            except ValueError:
                pass
            raise YodleeError(
                http_status=response.status_code,
                error_code=code if isinstance(code, str) else None,
            )
        if not response.content:
            return {}
        try:
            body = response.json()
        except ValueError:
            raise YodleeError(
                http_status=response.status_code, error_code="INVALID_RESPONSE"
            ) from None
        return body if isinstance(body, dict) else {}

    def _token(self, login_name: str) -> tuple[str, int]:
        """A token for `login_name`; Yodlee refuses a user token for the admin login."""
        body = self._send(
            "POST",
            "/auth/token",
            login_name=login_name,
            data={
                "clientId": self._settings.yodlee_client_id,
                "secret": self._settings.yodlee_client_secret,
            },
        )
        token = body.get("token")
        if not isinstance(token, dict) or not token.get("accessToken"):
            raise YodleeError(http_status=None, error_code="INVALID_RESPONSE")
        return str(token["accessToken"]), int(token.get("expiresIn") or 0)

    def register_user(self, login_name: str) -> None:
        """Register `login_name` unless Yodlee already knows it."""
        try:
            self._token(login_name)
            return
        except YodleeError as exc:
            if exc.error_code != USER_NOT_REGISTERED:
                raise
        assert self._settings.yodlee_admin_login_name is not None
        admin, _ = self._token(self._settings.yodlee_admin_login_name)
        self._send(
            "POST",
            "/user/register",
            token=admin,
            json={
                "user": {
                    "loginName": login_name,
                    "preferences": {
                        "currency": "CAD",
                        "timeZone": "America/Toronto",
                        "dateFormat": "yyyy-MM-dd",
                        "locale": "en_CA",
                    },
                }
            },
        )

    def launch(
        self, login_name: str, provider_account_id: str | None
    ) -> FastLinkLaunch:
        token, expires_in = self._token(login_name)
        assert self._settings.yodlee_fastlink_url is not None
        assert self._settings.yodlee_fastlink_config_name is not None
        return FastLinkLaunch(
            fastlink_url=self._settings.yodlee_fastlink_url,
            access_token=token,
            config_name=self._settings.yodlee_fastlink_config_name,
            expires_in=expires_in,
            provider_account_id=provider_account_id,
        )

    def provider_account(
        self, login_name: str, provider_account_id: str
    ) -> ProviderAccountStatus:
        token, _ = self._token(login_name)
        body = self._send(
            "GET", f"/providerAccounts/{provider_account_id}", token=token
        )
        accounts = body.get("providerAccount")
        if not isinstance(accounts, list) or not accounts:
            raise YodleeError(http_status=None, error_code="INVALID_RESPONSE")
        account = accounts[0]
        datasets = account.get("dataset") or []
        refreshed = [
            datetime.fromisoformat(d["lastUpdated"])
            for d in datasets
            if d.get("lastUpdated")
        ]
        return ProviderAccountStatus(
            provider_id=str(account.get("providerId")),
            last_refreshed=max(refreshed) if refreshed else None,
            needs_login=any(
                d.get("additionalStatus") in LOGIN_REQUIRED_STATUSES for d in datasets
            ),
        )

    def accounts(self, login_name: str, provider_account_id: str) -> list[PlaidAccount]:
        token, _ = self._token(login_name)
        body = self._send(
            "GET",
            "/accounts",
            token=token,
            params={"providerAccountId": provider_account_id},
        )
        return [
            _account(a)
            for a in body.get("account") or []
            if a.get("CONTAINER") in CONTAINERS
            and str(a.get("providerAccountId")) == provider_account_id
        ]

    def transactions(
        self, login_name: str, account_ids: frozenset[str], from_date: date
    ) -> list[PlaidTransaction]:
        token, _ = self._token(login_name)
        found: list[PlaidTransaction] = []
        skip = 0
        for _ in range(MAX_TRANSACTION_PAGES):
            body = self._send(
                "GET",
                "/transactions",
                token=token,
                params={
                    "fromDate": from_date.isoformat(),
                    "skip": skip,
                    "top": TRANSACTIONS_PAGE_SIZE,
                },
            )
            page = body.get("transaction") or []
            if not page:
                return found
            skip += len(page)
            found.extend(
                _transaction(t)
                for t in page
                if t.get("status") == "POSTED"
                and str(t.get("accountId")) in account_ids
            )
        raise YodleeError(http_status=None, error_code="TOO_MANY_PAGES")

    def delete_provider_account(
        self, login_name: str, provider_account_id: str
    ) -> None:
        token, _ = self._token(login_name)
        self._send("DELETE", f"/providerAccounts/{provider_account_id}", token=token)


@lru_cache
def get_yodlee_client() -> YodleeClient | None:
    """The shared client, or None while Yodlee is off."""
    settings = get_settings()
    return HttpxYodleeClient(settings) if yodlee_enabled(settings) else None
