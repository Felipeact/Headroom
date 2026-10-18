"""A fake Flinks for spec 17a's tests: it behaves like Flinks and calls nothing."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest

from app.main import app
from app.modules.bank_sync.flinks import (
    PENDING,
    ConnectUrl,
    Days,
    FlinksAccount,
    FlinksError,
    FlinksSnapshot,
    FlinksTransaction,
    get_flinks_client,
)

FLINKS_ORIGIN = "https://toolbox-iframe.private.fin.ag"
INSTITUTION_ID = "14"
INSTITUTION_NAME = "RBC Royal Bank"
# Holder data a real response can carry; none of it may reach a log or a response.
ACCOUNT_NUMBER = "00012345678901"
HOLDER_NAME = "Dana Holder"


def flinks_account(
    title: str = "Business Chequing",
    *,
    type: str = "checking",
    mask: str | None = "6789",
    current: float | None = 4200.25,
    available: float | None = 4100.25,
    currency: str | None = "CAD",
    account_id: str | None = None,
) -> FlinksAccount:
    return FlinksAccount(
        account_id=account_id or str(uuid.uuid4()),
        name=title,
        type=type,
        mask=mask,
        currency=currency,
        current=current,
        available=available,
    )


def flinks_tx(
    account: FlinksAccount,
    *,
    debit: float | None = None,
    credit: float | None = None,
    day: date = date(2026, 10, 1),
    description: str = "PAYROLL",
    transaction_id: str | None = None,
) -> FlinksTransaction:
    return FlinksTransaction(
        transaction_id=transaction_id or str(uuid.uuid4()),
        account_id=account.account_id,
        date=day,
        description=description,
        debit=debit,
        credit=credit,
    )


@dataclass
class AccountsCall:
    login_id: str
    with_transactions: bool
    days: Days
    polls: int


@dataclass
class FakeFlinks:
    """Records every call; `fail` maps a method name to the error it raises."""

    institution_id: str = INSTITUTION_ID
    accounts_list: list[FlinksAccount] = field(
        default_factory=lambda: [flinks_account()]
    )
    transactions: list[FlinksTransaction] = field(default_factory=list)
    last_refresh: datetime | None = None
    fail: dict[str, FlinksError] = field(default_factory=dict)
    # How many `accounts` calls answer "still processing" before one succeeds.
    pending_calls: int = 0
    calls: list[str] = field(default_factory=list)
    accounts_calls: list[AccountsCall] = field(default_factory=list)
    refresh_enabled: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if name in self.fail:
            raise self.fail[name]

    def connect_url(self) -> ConnectUrl:
        self._call("connect_url")
        return ConnectUrl(
            url=f"{FLINKS_ORIGIN}/v2/?authorizeToken=token-1&demo=true",
            origin=FLINKS_ORIGIN,
        )

    def accounts(
        self, login_id: str, *, with_transactions: bool, days: Days, polls: int
    ) -> FlinksSnapshot:
        self.accounts_calls.append(
            AccountsCall(login_id, with_transactions, days, polls)
        )
        self._call("accounts")
        if self.pending_calls:
            self.pending_calls -= 1
            raise FlinksError(http_status=202, flinks_code=PENDING)
        return FlinksSnapshot(
            institution_id=self.institution_id,
            institution_name=INSTITUTION_NAME,
            accounts=list(self.accounts_list),
            transactions=list(self.transactions) if with_transactions else [],
            last_refresh=self.last_refresh,
        )

    def enable_nightly_refresh(self, login_id: str) -> None:
        self._call("enable_nightly_refresh")
        self.refresh_enabled.append(login_id)

    def delete(self, login_id: str) -> None:
        self.deleted.append(login_id)
        self._call("delete")


def login_error(code: str) -> FlinksError:
    return FlinksError(http_status=401, flinks_code=code)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]


@pytest.fixture
def flinks() -> Iterator[FakeFlinks]:
    fake = FakeFlinks()
    app.dependency_overrides[get_flinks_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_flinks_client, None)


@pytest.fixture
def no_flinks() -> Iterator[None]:
    app.dependency_overrides[get_flinks_client] = lambda: None
    yield
    app.dependency_overrides.pop(get_flinks_client, None)
