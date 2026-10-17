"""The Flinks port: the only place that talks to Flinks (spec 17a, AD-144).

Routes get a `FlinksClient` through `get_flinks_client`, which is None while Flinks is not
configured; tests override it with a fake. Every method returns plain dataclasses, and
every failure is a `FlinksError` carrying only the HTTP status and Flinks' code, never the
response body. A loginId is a permanent token (Flinks docs), so it is never logged.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any, Literal, Protocol
from urllib.parse import urlencode

import httpx

from app.settings import get_settings

TIMEOUT_SECONDS = 15
# Flinks: retry GetAccountsDetailAsync every 10 seconds while it answers 202.
POLL_INTERVAL_SECONDS = 10
CONNECT_POLLS = 3
SYNC_POLLS = 30
SANDBOX_INSTANCE = "toolbox"
PENDING = "OPERATION_PENDING"

Days = Literal["Days90", "Days365"]

# Flinks account `Type` -> our account type. Anything not listed is `other`, which never
# counts as cash (AD-040).
# TODO(question): confirm these strings against the Flinks sandbox (plan assumption).
ACCOUNT_TYPES: dict[str, str] = {
    "Chequing": "checking",
    "Savings": "savings",
    "CreditCard": "credit_card",
    "LineOfCredit": "line_of_credit",
}


class FlinksError(Exception):
    """A Flinks call failed, timed out, or was still processing past the poll budget."""

    def __init__(self, *, http_status: int | None, flinks_code: str | None) -> None:
        super().__init__(f"Flinks error {http_status}/{flinks_code}")
        self.http_status = http_status
        self.flinks_code = flinks_code


@dataclass(frozen=True)
class ConnectUrl:
    url: str
    # The iframe's origin: the only sender whose messages the web app accepts.
    origin: str


@dataclass(frozen=True)
class FlinksAccount:
    account_id: str
    name: str
    type: str
    mask: str | None
    currency: str | None
    current: float | None
    available: float | None


@dataclass(frozen=True)
class FlinksTransaction:
    transaction_id: str
    account_id: str
    date: date
    description: str
    # As Flinks reports them: both positive, at most one set.
    debit: float | None
    credit: float | None


@dataclass(frozen=True)
class FlinksSnapshot:
    institution_id: str
    institution_name: str
    accounts: list[FlinksAccount]
    transactions: list[FlinksTransaction]
    # When Flinks last read the bank; None when it doesn't say.
    last_refresh: datetime | None


class FlinksClient(Protocol):
    def connect_url(self) -> ConnectUrl: ...

    def accounts(
        self, login_id: str, *, with_transactions: bool, days: Days, polls: int
    ) -> FlinksSnapshot: ...

    def enable_nightly_refresh(self, login_id: str) -> None: ...

    def delete(self, login_id: str) -> None: ...


def account_type(flinks_type: str | None) -> str:
    """Our account type for a Flinks account `Type`; `other` when there is no match."""
    return ACCOUNT_TYPES.get(flinks_type or "", "other")


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


def _date(value: str) -> date:
    # Flinks writes dates as yyyy/MM/dd.
    return date.fromisoformat(value[:10].replace("/", "-"))


def _datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _snapshot(body: dict[str, Any]) -> FlinksSnapshot:
    accounts: list[FlinksAccount] = []
    transactions: list[FlinksTransaction] = []
    for a in body.get("Accounts") or []:
        balance = a.get("Balance") or {}
        account_id = str(a["Id"])
        # `AccountNumber` and the holder fields are never read (AD-145).
        accounts.append(
            FlinksAccount(
                account_id=account_id,
                name=a.get("Title") or "",
                type=account_type(a.get("Type")),
                mask=a.get("LastFourDigits"),
                currency=a.get("Currency"),
                current=_float(balance.get("Current")),
                available=_float(balance.get("Available")),
            )
        )
        for t in a.get("Transactions") or []:
            transactions.append(
                FlinksTransaction(
                    transaction_id=str(t["Id"]),
                    account_id=account_id,
                    date=_date(t["Date"]),
                    description=t.get("Description") or "",
                    debit=_float(t.get("Debit")),
                    credit=_float(t.get("Credit")),
                )
            )
    login = body.get("Login") or {}
    return FlinksSnapshot(
        institution_id=str(body.get("InstitutionId") or body.get("Institution") or ""),
        institution_name=str(body.get("Institution") or ""),
        accounts=accounts,
        transactions=transactions,
        last_refresh=_datetime(login.get("LastRefresh")),
    )


class HttpxFlinksClient:
    """`FlinksClient` over the Flinks REST API (docs.flinks.com), on `httpx`."""

    def __init__(
        self,
        *,
        instance: str,
        customer_id: str,
        auth_key: str,
        api_key: str,
        redirect_url: str,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._instance = instance
        self._base = (
            f"https://{instance}-api.private.fin.ag/v3/{customer_id}/BankingServices"
        )
        self._auth_key = auth_key
        self._api_key = api_key
        self._redirect_url = redirect_url
        self._http = http or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._sleep = sleep

    def _send(
        self, method: str, path: str, *, headers: dict[str, str], json: object = None
    ) -> httpx.Response:
        try:
            response = self._http.request(
                method,
                f"{self._base}/{path}",
                headers={"Accept": "application/json", **headers},
                json=json,
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            # Timeouts and connection failures.
            raise FlinksError(
                http_status=None, flinks_code=type(exc).__name__
            ) from None
        if response.status_code >= 400:
            raise FlinksError(
                http_status=response.status_code, flinks_code=_code(response)
            )
        return response

    def _authorize_token(self) -> str:
        response = self._send(
            "POST",
            "GenerateAuthorizeToken",
            headers={"flinks-auth-key": self._auth_key},
        )
        return str(response.json()["Token"])

    def _request_id(self, login_id: str) -> str:
        response = self._send(
            "POST",
            "Authorize",
            headers={"flinks-auth-key": self._authorize_token()},
            # Cached: the data from Flinks' last read, without logging in to the bank.
            json={"LoginId": login_id, "MostRecentCached": True},
        )
        if response.status_code != 200:
            # 203 asks for MFA answers, which a cached read never should.
            raise FlinksError(
                http_status=response.status_code, flinks_code=_code(response)
            )
        return str(response.json()["RequestId"])

    def connect_url(self) -> ConnectUrl:
        origin = f"https://{self._instance}-iframe.private.fin.ag"
        query = {
            "authorizeToken": self._authorize_token(),
            "redirectUrl": self._redirect_url,
            "jsRedirect": "true",
            "daysOfTransactions": "Days365",
            "language": "en",
            "institutionFilterEnable": "true",
        }
        if self._instance == SANDBOX_INSTANCE:
            query["demo"] = "true"
        return ConnectUrl(url=f"{origin}/v2/?{urlencode(query)}", origin=origin)

    def accounts(
        self, login_id: str, *, with_transactions: bool, days: Days, polls: int
    ) -> FlinksSnapshot:
        request_id = self._request_id(login_id)
        # TODO(question): Flinks docs give data endpoints `x-api-key`; confirm in the sandbox.
        headers = {"x-api-key": self._api_key}
        response = self._send(
            "POST",
            "GetAccountsDetail",
            headers=headers,
            json={
                "RequestId": request_id,
                "WithAccountIdentity": False,
                "WithKYC": False,
                "WithTransactions": with_transactions,
                "DaysOfTransactions": days,
            },
        )
        for _ in range(polls):
            if response.status_code != 202:
                break
            self._sleep(POLL_INTERVAL_SECONDS)
            response = self._send(
                "GET", f"GetAccountsDetailAsync/{request_id}", headers=headers
            )
        if response.status_code == 202:
            raise FlinksError(http_status=202, flinks_code=PENDING)
        return _snapshot(response.json())

    def enable_nightly_refresh(self, login_id: str) -> None:
        self._send(
            "PATCH",
            "SetScheduledRefresh",
            headers={"flinks-auth-key": self._authorize_token()},
            json={"loginId": login_id, "isActivated": True},
        )

    def delete(self, login_id: str) -> None:
        self._send(
            "DELETE", f"DeleteCard/{login_id}", headers={"x-api-key": self._api_key}
        )


def _code(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    code = body.get("FlinksCode") if isinstance(body, dict) else None
    return code if isinstance(code, str) else None


@lru_cache
def get_flinks_client() -> FlinksClient | None:
    """The Flinks client, or None unless every `FLINKS_*` setting is set."""
    settings = get_settings()
    if not (
        settings.flinks_instance
        and settings.flinks_customer_id
        and settings.flinks_auth_key
        and settings.flinks_api_key
    ):
        return None
    return HttpxFlinksClient(
        instance=settings.flinks_instance,
        customer_id=settings.flinks_customer_id,
        auth_key=settings.flinks_auth_key,
        api_key=settings.flinks_api_key,
        redirect_url=f"{settings.web_url.rstrip('/')}/onboarding/bank",
    )
