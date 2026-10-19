"""Spec 17b: a fake Yodlee client and the fixtures the Yodlee tests share."""

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime

import pytest

from app.main import app
from app.modules.bank_sync.plaid import PlaidAccount, PlaidTransaction
from app.modules.bank_sync.yodlee import (
    FastLinkLaunch,
    ProviderAccountStatus,
    YodleeError,
    get_yodlee_client,
)
from app.settings import get_settings

PROVIDER_ID = "16441"
PROVIDER_NAME = "Royal Bank of Canada"
ACCESS_TOKEN = "yodlee-user-token-SECRET-1"
FASTLINK_URL = "https://fastlink.test/fastlink"
CONFIG_NAME = "HeadroomTest"


def yodlee_account(
    name: str,
    *,
    subtype: str | None = "checking",
    type: str = "depository",
    mask: str | None = "1234",
    current: float | None = 100.0,
    iso: str | None = "CAD",
) -> PlaidAccount:
    return PlaidAccount(
        account_id=str(uuid.uuid4().int % 10**9),
        name=name,
        type=type,
        subtype=subtype,
        mask=mask,
        current=current,
        iso_currency_code=iso,
        unofficial_currency_code=None,
    )


def default_yodlee_accounts() -> list[PlaidAccount]:
    return [
        yodlee_account("Chequing", current=1234.56),
        yodlee_account("Savings", subtype="savings", current=20000.0),
    ]


def yodlee_transaction(
    transaction_id: str, account_id: str, *, amount: float, day: date
) -> PlaidTransaction:
    """`amount` as the client returns it: positive is money out."""
    return PlaidTransaction(
        transaction_id=f"yodlee:{transaction_id}",
        account_id=account_id,
        amount=amount,
        iso_currency_code="CAD",
        unofficial_currency_code=None,
        date=day,
        pending=False,
        pending_transaction_id=None,
        name=f"Payment {transaction_id}",
        merchant_name=None,
        counterparties=(),
        category=None,
        category_detailed=None,
    )


class FakeYodlee:
    """Behaves like the Yodlee port for the calls spec 17b makes, and records them."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.registered: list[str] = []
        self.launches: list[tuple[str, str | None]] = []
        self.deleted: list[tuple[str, str]] = []
        self.fail: dict[str, YodleeError] = {}
        self.fail_after_calls: dict[str, int] = {}
        self.provider_id = PROVIDER_ID
        self.accounts_list: Callable[[], list[PlaidAccount]] = default_yodlee_accounts
        self.transaction_list: list[PlaidTransaction] = []
        self.needs_login = False
        self.last_refreshed: datetime | None = datetime(2099, 1, 1, tzinfo=UTC)
        self.transaction_from_dates: list[date] = []
        self.status_logins: list[str] = []

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if name in self.fail:
            error = self.fail[name]
            remaining = self.fail_after_calls.get(name)
            if remaining is None:
                raise error
            if remaining <= 0:
                raise error
            self.fail_after_calls[name] = remaining - 1

    def register_user(self, login_name: str) -> None:
        self._call("register")
        self.registered.append(login_name)

    def launch(
        self, login_name: str, provider_account_id: str | None
    ) -> FastLinkLaunch:
        self._call("launch")
        self.launches.append((login_name, provider_account_id))
        return FastLinkLaunch(
            fastlink_url=FASTLINK_URL,
            access_token=ACCESS_TOKEN,
            config_name=CONFIG_NAME,
            expires_in=1800,
            provider_account_id=provider_account_id,
        )

    def provider_account(
        self, login_name: str, provider_account_id: str
    ) -> ProviderAccountStatus:
        self._call("provider_account")
        self.status_logins.append(login_name)
        return ProviderAccountStatus(
            provider_id=self.provider_id,
            last_refreshed=self.last_refreshed,
            needs_login=self.needs_login,
        )

    def institution_name(self, login_name: str, provider_id: str) -> str:
        self._call("institution")
        return PROVIDER_NAME

    def accounts(self, login_name: str, provider_account_id: str) -> list[PlaidAccount]:
        self._call("accounts")
        return self.accounts_list()

    def transactions(
        self, login_name: str, account_ids: frozenset[str], from_date: date
    ) -> list[PlaidTransaction]:
        self._call("transactions")
        self.transaction_from_dates.append(from_date)
        return [t for t in self.transaction_list if t.account_id in account_ids]

    def delete_provider_account(
        self, login_name: str, provider_account_id: str
    ) -> None:
        self._call("delete")
        self.deleted.append((login_name, provider_account_id))


@pytest.fixture
def no_test_login(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run as production does: no sandbox test user, so `hr-<business id>` is used."""
    monkeypatch.setenv("YODLEE_TEST_LOGIN_NAME", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def yodlee(no_test_login: None) -> Iterator[FakeYodlee]:
    fake = FakeYodlee()
    app.dependency_overrides[get_yodlee_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_yodlee_client, None)
