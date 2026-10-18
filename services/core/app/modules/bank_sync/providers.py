"""The bank-data providers behind a connection: Plaid and Flinks (spec 17a, AD-143).

Each provider's answer becomes one provider-neutral `Update` here, in our terms (integer
cents, money in positive), so `service` applies a sync the same way whoever fetched it.
This is the only place that branches on `connection.provider` to fetch or remove a login,
and the only place each provider's amount gets our sign (AGENTS.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal

import structlog

from app.modules.bank_sync.flinks import (
    SYNC_POLLS,
    FlinksAccount,
    FlinksClient,
    FlinksError,
    FlinksSnapshot,
    FlinksTransaction,
)
from app.modules.bank_sync.models import BankConnection
from app.modules.bank_sync.plaid import (
    PlaidAccount,
    PlaidClient,
    PlaidError,
    PlaidTransaction,
    SyncPage,
)
from app.modules.bank_sync.tokens import decrypt_access_token

log = structlog.get_logger(__name__)


# Plaid asks for the whole update to restart when the data changes while paging.
MUTATION_DURING_PAGINATION = "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"


SYNC_ATTEMPTS = 3


ITEM_NOT_FOUND = "ITEM_NOT_FOUND"


FLINKS_NOT_CONFIGURED = "NOT_CONFIGURED"


# Plaid (type, subtype) -> our account type. Anything not listed is `other`.
ACCOUNT_TYPES: dict[tuple[str, str | None], str] = {
    ("depository", "checking"): "checking",
    ("depository", "savings"): "savings",
    ("credit", "credit card"): "credit_card",
    ("credit", "line of credit"): "line_of_credit",
    ("loan", "line of credit"): "line_of_credit",
}


def account_type(plaid_type: str, plaid_subtype: str | None) -> str:
    """Our account type for a Plaid type and subtype; `other` when there is no match."""
    return ACCOUNT_TYPES.get((plaid_type, plaid_subtype), "other")


def to_cents(amount: float | None) -> int | None:
    """A Plaid amount in dollars as integer cents, rounded half-even; None stays None."""
    if amount is None:
        return None
    # str() first: Decimal(1234.565) would carry the float's binary error.
    cents = Decimal(str(amount)) * 100
    return int(cents.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


@dataclass(frozen=True)
class ReportedAccount:
    """An account as a provider reports it, in our terms: our type and integer cents."""

    account_id: str
    name: str
    type: str
    mask: str | None
    currency: str
    balance_cents: int | None
    available_cents: int | None


@dataclass(frozen=True)
class ReportedTransaction:
    """A transaction as a provider reports it, in our terms: money in is positive."""

    transaction_id: str
    account_id: str
    amount_cents: int
    currency: str
    date: date
    pending: bool
    description: str
    counterparty: str | None
    category: str | None
    category_detailed: str | None
    # The pending transaction this posted one replaces (Plaid only).
    replaces: str | None = None


@dataclass(frozen=True)
class Batch:
    changes: list[ReportedTransaction]
    removed: list[str]


@dataclass(frozen=True)
class Update:
    """Everything one sync fetched from a provider, ready to apply."""

    # Every account report in fetch order; the last report of an account holds its
    # balance.
    accounts: list[ReportedAccount]
    batches: list[Batch]
    # Plaid's next cursor; None for Flinks, which has none.
    cursor: str | None
    # Flinks: when it last read the bank. None for Plaid.
    refreshed_at: datetime | None = None


def plaid_account(account: PlaidAccount) -> ReportedAccount:
    currency = account.iso_currency_code or account.unofficial_currency_code
    if currency is None:
        raise PlaidError(
            error_type="INVALID_RESPONSE", error_code="NO_CURRENCY", request_id=None
        )
    return ReportedAccount(
        account_id=account.account_id,
        name=account.name,
        type=account_type(account.type, account.subtype),
        mask=account.mask,
        currency=currency,
        balance_cents=to_cents(account.current),
        available_cents=to_cents(account.available),
    )


def flinks_account(account: FlinksAccount) -> ReportedAccount:
    if account.currency is None:
        raise FlinksError(http_status=None, flinks_code="NO_CURRENCY")
    return ReportedAccount(
        account_id=account.account_id,
        name=account.name,
        type=account.type,
        mask=account.mask,
        currency=account.currency,
        balance_cents=to_cents(account.current),
        available_cents=to_cents(account.available),
    )


def invalid_response(error_code: str) -> PlaidError:
    return PlaidError(
        error_type="INVALID_RESPONSE", error_code=error_code, request_id=None
    )


def _fetch_pages(
    plaid: PlaidClient, access_token: str, cursor: str | None
) -> list[SyncPage]:
    """Every page of the update after `cursor`.

    When Plaid reports that the data changed while paging, the whole update restarts
    from `cursor`, up to `SYNC_ATTEMPTS` times (Plaid's documented rule).
    """
    for attempt in range(1, SYNC_ATTEMPTS + 1):
        pages: list[SyncPage] = []
        next_cursor = cursor
        try:
            while True:
                page = plaid.sync_transactions(access_token, next_cursor)
                pages.append(page)
                next_cursor = page.next_cursor
                if not page.has_more:
                    return pages
        except PlaidError as exc:
            if exc.error_code != MUTATION_DURING_PAGINATION or attempt == SYNC_ATTEMPTS:
                raise
    raise AssertionError("unreachable")


def _plaid_transaction(transaction: PlaidTransaction) -> ReportedTransaction:
    """A Plaid transaction in our terms: cents, money in positive, one currency code.

    The only place a Plaid amount's sign is flipped (AGENTS.md).
    """
    currency = transaction.iso_currency_code or transaction.unofficial_currency_code
    if currency is None:
        raise invalid_response("NO_CURRENCY")
    cents = to_cents(transaction.amount)
    assert cents is not None
    counterparty = (
        transaction.counterparties[0]
        if transaction.counterparties
        else transaction.merchant_name
    )
    pending_id = transaction.pending_transaction_id
    return ReportedTransaction(
        transaction_id=transaction.transaction_id,
        account_id=transaction.account_id,
        amount_cents=-cents,
        currency=currency,
        date=transaction.date,
        pending=transaction.pending,
        description=transaction.name,
        counterparty=counterparty,
        category=transaction.category,
        category_detailed=transaction.category_detailed,
        replaces=pending_id if pending_id != transaction.transaction_id else None,
    )


def _plaid_update(pages: list[SyncPage]) -> Update:
    return Update(
        accounts=[plaid_account(a) for page in pages for a in page.accounts],
        batches=[
            Batch(
                changes=[_plaid_transaction(t) for t in [*page.added, *page.modified]],
                removed=list(page.removed),
            )
            for page in pages
        ],
        cursor=pages[-1].next_cursor,
    )


def _flinks_transaction(
    transaction: FlinksTransaction, currencies: Mapping[str, str]
) -> ReportedTransaction:
    """A Flinks transaction in our terms: a credit is money in, a debit money out.

    The only place a Flinks amount gets its sign (AGENTS.md). Flinks returns posted
    transactions only, so none is pending.
    """
    amount_cents = (to_cents(transaction.credit) or 0) - (
        to_cents(transaction.debit) or 0
    )
    return ReportedTransaction(
        transaction_id=transaction.transaction_id,
        account_id=transaction.account_id,
        amount_cents=amount_cents,
        currency=currencies[transaction.account_id],
        date=transaction.date,
        pending=False,
        description=transaction.description,
        counterparty=None,
        category=None,
        category_detailed=None,
    )


def _flinks_update(snapshot: FlinksSnapshot) -> Update:
    accounts = [flinks_account(a) for a in snapshot.accounts]
    currencies = {a.account_id: a.currency for a in accounts}
    if any(t.account_id not in currencies for t in snapshot.transactions):
        raise FlinksError(http_status=None, flinks_code="UNKNOWN_ACCOUNT")
    # One snapshot of the window: a transaction missing from it is kept, not removed.
    return Update(
        accounts=accounts,
        batches=[
            Batch(
                changes=[
                    _flinks_transaction(t, currencies) for t in snapshot.transactions
                ],
                removed=[],
            )
        ],
        cursor=None,
        refreshed_at=snapshot.last_refresh,
    )


def fetch(
    plaid: PlaidClient, flinks: FlinksClient | None, connection: BankConnection
) -> Update:
    """Every change since the connection's last sync, from its provider."""
    secret = decrypt_access_token(connection.access_token_ciphertext)
    if connection.provider == "flinks":
        if flinks is None:
            raise FlinksError(http_status=None, flinks_code=FLINKS_NOT_CONFIGURED)
        # Flinks has no cursor: a year on the first sync, then the last 90 days.
        snapshot = flinks.accounts(
            secret,
            with_transactions=True,
            days="Days365" if connection.last_synced_at is None else "Days90",
            polls=SYNC_POLLS,
        )
        return _flinks_update(snapshot)
    return _plaid_update(_fetch_pages(plaid, secret, connection.transactions_cursor))


def synced_at(
    connection: BankConnection, flinks_refresh: datetime | None, now: datetime
) -> datetime:
    """When the data is from: `now` for Plaid; Flinks' last bank read if earlier (AD-146).

    Flinks' cached read succeeds even when its nightly refresh stopped, so the time it
    last read the bank is what the 48-hour "hasn't synced" check must see.
    """
    if connection.provider == "flinks" and flinks_refresh is not None:
        return min(now, flinks_refresh)
    return now


def remove_at_provider(
    plaid: PlaidClient, flinks: FlinksClient | None, connection: BankConnection
) -> None:
    """Remove the login at its provider; for Flinks a failure is logged, not raised.

    A Plaid failure stops the disconnect (spec 17). Flinks' `DeleteCard` failing must not
    keep the owner's bank (spec 17a): the local rows go, and the orphan is logged.
    """
    secret = decrypt_access_token(connection.access_token_ciphertext)
    if connection.provider != "flinks":
        try:
            plaid.remove_item(secret)
        except PlaidError as exc:
            if exc.error_code != ITEM_NOT_FOUND:
                raise
        return
    try:
        if flinks is None:
            raise FlinksError(http_status=None, flinks_code=FLINKS_NOT_CONFIGURED)
        flinks.delete(secret)
    except FlinksError as exc:
        log.error(
            "bank_connection.orphaned",
            business_id=str(connection.business_id),
            connection_id=str(connection.id),
            provider="flinks",
            error_code=exc.flinks_code,
        )
