import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

import structlog
from psycopg.errors import UniqueViolation
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit, events
from app.db import get_sessionmaker
from app.modules.bank_sync import repository
from app.modules.bank_sync.events import TRANSACTIONS_SYNCED
from app.modules.bank_sync.models import (
    CASH_CURRENCY,
    CASH_TYPES,
    BankAccount,
    BankConnection,
    BankTransaction,
)
from app.modules.bank_sync.plaid import (
    ExchangedItem,
    LinkToken,
    LinkTokenRequest,
    PlaidAccount,
    PlaidClient,
    PlaidError,
    PlaidTransaction,
    SyncPage,
)
from app.modules.bank_sync.tokens import decrypt_access_token, encrypt_access_token
from app.settings import get_settings

INSTITUTION_INDEX = "uq_bank_connections_business_id_plaid_institution_id"
PRIMARY_INDEX = "uq_bank_accounts_primary_business_id"
# 24 months of history, Plaid's maximum.
DAYS_REQUESTED = 730
# Plaid asks for the whole update to restart when the data changes while paging.
MUTATION_DURING_PAGINATION = "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"
SYNC_ATTEMPTS = 3

# Plaid (type, subtype) -> our account type. Anything not listed is `other`.
ACCOUNT_TYPES: dict[tuple[str, str | None], str] = {
    ("depository", "checking"): "checking",
    ("depository", "savings"): "savings",
    ("credit", "credit card"): "credit_card",
    ("credit", "line of credit"): "line_of_credit",
    ("loan", "line of credit"): "line_of_credit",
}

log = structlog.get_logger(__name__)


class DuplicateBankError(Exception):
    """The business already has a connection to this institution."""


class AccountNotFoundError(Exception):
    """The business has no account with this ID."""


class ConnectionNotFoundError(Exception):
    """The business has no connection with this ID."""


AccountConflict = Literal[
    "credit", "other", "currency", "primary_not_included", "exclude_primary"
]


class AccountRuleError(Exception):
    """An account change breaks a cash or primary-account rule."""

    def __init__(self, reason: AccountConflict) -> None:
        super().__init__(reason)
        self.reason: AccountConflict = reason


@dataclass(frozen=True)
class AccountView:
    id: uuid.UUID
    name: str
    type: str
    mask: str | None
    currency: str
    balance_cents: int | None
    available_cents: int | None
    included: bool
    primary: bool


@dataclass(frozen=True)
class SyncResult:
    added: int
    modified: int
    removed: int
    balances_changed: bool

    @property
    def changed(self) -> bool:
        return bool(
            self.added or self.modified or self.removed or self.balances_changed
        )


@dataclass(frozen=True)
class ConnectionView:
    id: uuid.UUID
    institution_name: str
    created_at: datetime
    accounts: list[AccountView]


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


def _view(row: BankAccount) -> AccountView:
    return AccountView(
        id=row.id,
        name=row.name,
        type=row.type,
        mask=row.mask,
        currency=row.currency,
        balance_cents=row.balance_cents,
        available_cents=row.available_cents,
        included=row.included,
        primary=row.is_primary,
    )


def _connection_view(
    connection: BankConnection, accounts: Iterable[BankAccount]
) -> ConnectionView:
    return ConnectionView(
        id=connection.id,
        institution_name=connection.institution_name,
        created_at=connection.created_at,
        accounts=sorted((_view(a) for a in accounts), key=lambda a: (a.name, a.id)),
    )


def create_link_token(plaid: PlaidClient, *, user_id: uuid.UUID) -> LinkToken:
    """A Plaid Link token for Canada, transactions, and 24 months of history.

    Raises `PlaidError` when Plaid fails or times out.
    """
    return plaid.create_link_token(
        LinkTokenRequest(
            client_user_id=str(user_id),
            client_name="Headroom",
            language="en",
            country_codes=("CA",),
            products=("transactions",),
            days_requested=DAYS_REQUESTED,
            webhook=get_settings().plaid_webhook_url,
        )
    )


def _account(
    account: PlaidAccount, *, business_id: uuid.UUID, connection_id: uuid.UUID
) -> BankAccount:
    currency = account.iso_currency_code or account.unofficial_currency_code
    if currency is None:
        raise PlaidError(
            error_type="INVALID_RESPONSE", error_code="NO_CURRENCY", request_id=None
        )
    type_ = account_type(account.type, account.subtype)
    return BankAccount(
        business_id=business_id,
        connection_id=connection_id,
        plaid_account_id=account.account_id,
        name=account.name,
        type=type_,
        mask=account.mask,
        currency=currency,
        balance_cents=to_cents(account.current),
        available_cents=to_cents(account.available),
        # Checking counts as cash by default; savings waits for the owner (spec 13).
        included=type_ == "checking" and currency == CASH_CURRENCY,
        is_primary=False,
    )


def _violates(exc: IntegrityError, constraint: str) -> bool:
    orig = exc.orig
    return isinstance(orig, UniqueViolation) and orig.diag.constraint_name == constraint


def _choose_primary(
    session: Session, rows: list[BankAccount], *, business_id: uuid.UUID
) -> None:
    """Make the largest-balance included account primary if the business has none."""
    if repository.has_primary(session, business_id=business_id):
        return
    candidates = [r for r in rows if r.included]
    if not candidates:
        return
    best = min(
        candidates,
        key=lambda r: (r.balance_cents is None, -(r.balance_cents or 0), r.name, r.id),
    )
    try:
        with session.begin_nested():
            best.is_primary = True
            session.flush()
    except IntegrityError as exc:
        # Another connect for this business chose its primary first; keep that one.
        if not _violates(exc, PRIMARY_INDEX):
            raise


def _remove_new_item(
    plaid: PlaidClient, item: ExchangedItem, *, business_id: uuid.UUID
) -> None:
    try:
        plaid.remove_item(item.access_token)
    except PlaidError:
        # Nothing stored the token, so no one can remove this item later: say so loudly.
        log.error(
            "bank_connection.orphaned",
            business_id=str(business_id),
            plaid_item_id=item.item_id,
        )


def connect_bank(
    session: Session,
    plaid: PlaidClient,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    public_token: str,
) -> ConnectionView:
    """Exchange a Link `public_token` and store the bank, its accounts and an audit entry.

    Everything is stored in one transaction with the access token encrypted. If anything
    fails after the exchange, the new item is removed at Plaid and nothing is stored.
    Raises `DuplicateBankError` when the business already has this institution (also when
    two connects race), and `PlaidError` when Plaid fails. Commits the session.
    """
    item = plaid.exchange_public_token(public_token)
    try:
        accounts = plaid.get_accounts(item.access_token)
        institution_id = accounts.institution_id
        if repository.has_institution(
            session, business_id=business_id, institution_id=institution_id
        ):
            raise DuplicateBankError
        institution_name = plaid.get_institution_name(institution_id)
        try:
            connection = repository.insert_connection(
                session,
                business_id=business_id,
                plaid_item_id=item.item_id,
                plaid_institution_id=institution_id,
                institution_name=institution_name,
                access_token_ciphertext=encrypt_access_token(item.access_token),
            )
        except IntegrityError as exc:
            if _violates(exc, INSTITUTION_INDEX):
                raise DuplicateBankError from None
            raise
        rows = [
            _account(a, business_id=business_id, connection_id=connection.id)
            for a in accounts.accounts
        ]
        repository.insert_accounts(session, rows)
        _choose_primary(session, rows, business_id=business_id)
        audit.record(
            session,
            action="bank_connection.created",
            business_id=business_id,
            actor_user_id=str(user_id),
            target_type="bank_connection",
            target_id=str(connection.id),
            details={"institution_id": institution_id, "account_count": len(rows)},
        )
        view = _connection_view(connection, rows)
        session.commit()
    except BaseException:
        session.rollback()
        _remove_new_item(plaid, item, business_id=business_id)
        raise
    log.info(
        "bank_connection.created",
        business_id=str(business_id),
        connection_id=str(view.id),
        institution_id=institution_id,
        account_count=len(view.accounts),
    )
    return view


def list_connections(
    session: Session, *, business_id: uuid.UUID
) -> list[ConnectionView]:
    """The business's connections, oldest first, each with its accounts by name."""
    accounts = repository.accounts(session, business_id=business_id)
    return [
        _connection_view(c, (a for a in accounts if a.connection_id == c.id))
        for c in repository.connections(session, business_id=business_id)
    ]


def _cash_conflict(account: BankAccount) -> AccountConflict | None:
    if account.type in ("credit_card", "line_of_credit"):
        return "credit"
    if account.type not in CASH_TYPES:
        return "other"
    if account.currency != CASH_CURRENCY:
        return "currency"
    return None


def update_account(
    session: Session,
    *,
    business_id: uuid.UUID,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    included: bool | None,
    primary: bool,
) -> AccountView:
    """Include or exclude an account as cash, or make it the primary account.

    `included` None leaves inclusion as it is; `primary` True moves the primary account
    here. Including an account when the business has no primary makes it primary. Locks
    the business's accounts, so concurrent changes run one after the other. Writes an
    audit entry when something changed, and commits the session.
    Raises `AccountNotFoundError`, and `AccountRuleError` when a rule forbids the change.
    """
    try:
        accounts = repository.lock_accounts(session, business_id=business_id)
        account = next((a for a in accounts if a.id == account_id), None)
        if account is None:
            raise AccountNotFoundError
        will_include = account.included if included is None else included
        if will_include and not account.included:
            conflict = _cash_conflict(account)
            if conflict is not None:
                raise AccountRuleError(conflict)
        if primary and not will_include:
            raise AccountRuleError("primary_not_included")
        if not will_include and account.is_primary:
            raise AccountRuleError("exclude_primary")

        changes: dict[str, bool] = {}
        if will_include != account.included:
            account.included = will_include
            changes["included"] = will_include
        current = next((a for a in accounts if a.is_primary), None)
        if (primary or (will_include and current is None)) and not account.is_primary:
            if current is not None:
                current.is_primary = False
                # Before the new primary: the unique index checks each statement.
                session.flush()
            account.is_primary = True
            changes["primary"] = True
        if changes:
            session.flush()
            audit.record(
                session,
                action="bank_account.updated",
                business_id=business_id,
                actor_user_id=str(user_id),
                target_type="bank_account",
                target_id=str(account.id),
                details=changes,
            )
        view = _view(account)
        session.commit()
    except BaseException:
        session.rollback()
        raise
    if changes:
        log.info(
            "bank_account.updated",
            business_id=str(business_id),
            account_id=str(account_id),
            **changes,
        )
    return view


def _invalid(error_code: str) -> PlaidError:
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


def _values(transaction: PlaidTransaction, account: BankAccount) -> dict[str, object]:
    """A Plaid transaction in our terms: cents, money in positive, one currency code.

    The only place a Plaid amount's sign is flipped (AGENTS.md).
    """
    currency = transaction.iso_currency_code or transaction.unofficial_currency_code
    if currency is None:
        raise _invalid("NO_CURRENCY")
    cents = to_cents(transaction.amount)
    assert cents is not None
    counterparty = (
        transaction.counterparties[0]
        if transaction.counterparties
        else transaction.merchant_name
    )
    return {
        "business_id": account.business_id,
        "account_id": account.id,
        "amount_cents": -cents,
        "currency": currency,
        "date": transaction.date,
        "pending": transaction.pending,
        "description": transaction.name,
        "counterparty": counterparty,
        "category": transaction.category,
        "category_detailed": transaction.category_detailed,
    }


def _apply(
    session: Session, connection: BankConnection, pages: list[SyncPage]
) -> SyncResult:
    business_id = connection.business_id
    accounts = {
        a.plaid_account_id: a
        for a in repository.connection_accounts(
            session, business_id=business_id, connection_id=connection.id
        )
    }
    new_accounts: list[BankAccount] = []
    for page in pages:
        for reported in page.accounts:
            if reported.account_id not in accounts:
                row = _account(
                    reported, business_id=business_id, connection_id=connection.id
                )
                # The owner decides whether an account found later counts as cash.
                row.included = False
                accounts[reported.account_id] = row
                new_accounts.append(row)
    if new_accounts:
        repository.insert_accounts(session, new_accounts)

    added = modified = removed = 0
    for page in pages:
        changes = [*page.added, *page.modified]
        existing = repository.transactions_by_plaid_id(
            session,
            business_id=business_id,
            plaid_transaction_ids=[t.transaction_id for t in changes],
        )
        replaced: list[str] = []
        for transaction in changes:
            account = accounts.get(transaction.account_id)
            if account is None:
                raise _invalid("UNKNOWN_ACCOUNT")
            values = _values(transaction, account)
            stored = existing.get(transaction.transaction_id)
            if stored is None:
                stored = BankTransaction(
                    plaid_transaction_id=transaction.transaction_id, **values
                )
                repository.insert_transaction(
                    session, business_id=business_id, transaction=stored
                )
                existing[transaction.transaction_id] = stored
                added += 1
            elif any(getattr(stored, k) != v for k, v in values.items()):
                for key, value in values.items():
                    setattr(stored, key, value)
                stored.updated_at = func.now()
                modified += 1
            # The posted version replaces its pending one, even when Plaid's removal
            # of the pending ID comes in a later page or not at all.
            pending_id = transaction.pending_transaction_id
            if pending_id is not None and pending_id != transaction.transaction_id:
                replaced.append(pending_id)
        removed += repository.delete_transactions(
            session,
            business_id=business_id,
            plaid_transaction_ids=[*page.removed, *replaced],
        )

    balances_changed = bool(new_accounts)
    for reported in pages[-1].accounts:
        row = accounts[reported.account_id]
        balance = to_cents(reported.current)
        available = to_cents(reported.available)
        if (row.balance_cents, row.available_cents) != (balance, available):
            row.balance_cents = balance
            row.available_cents = available
            row.updated_at = func.now()
            balances_changed = True

    connection.transactions_cursor = pages[-1].next_cursor
    session.flush()
    return SyncResult(
        added=added,
        modified=modified,
        removed=removed,
        balances_changed=balances_changed,
    )


def sync_connection(
    session: Session,
    plaid: PlaidClient,
    *,
    business_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> SyncResult:
    """Bring in every transaction and balance change since the connection's last sync.

    Locks the connection for the whole sync, so two syncs of it run one after the other
    and the second starts from the cursor the first stored. Every page is fetched first;
    then the changes, the balances and the new cursor are stored in one transaction, and
    on any failure nothing is. Publishes `transactions.synced` after the commit when
    something changed. Commits the session.
    Raises `ConnectionNotFoundError`, and `PlaidError` when Plaid fails.
    """
    try:
        connection = repository.lock_connection(
            session, business_id=business_id, connection_id=connection_id
        )
        if connection is None:
            raise ConnectionNotFoundError
        pages = _fetch_pages(
            plaid,
            decrypt_access_token(connection.access_token_ciphertext),
            connection.transactions_cursor,
        )
        result = _apply(session, connection, pages)
        session.commit()
    except BaseException:
        session.rollback()
        raise
    log.info(
        "bank_sync.synced",
        business_id=str(business_id),
        connection_id=str(connection_id),
        added=result.added,
        modified=result.modified,
        removed=result.removed,
        balances_changed=result.balances_changed,
    )
    if result.changed:
        events.publish(
            events.Event(
                name=TRANSACTIONS_SYNCED,
                business_id=business_id,
                payload={
                    "connection_id": str(connection_id),
                    "added": result.added,
                    "modified": result.modified,
                    "removed": result.removed,
                    "balances_changed": result.balances_changed,
                },
            )
        )
    return result


def sync_in_background(
    plaid: PlaidClient, *, business_id: uuid.UUID, connection_id: uuid.UUID
) -> None:
    """`sync_connection` in a session of its own, for work that runs after a response.

    A Plaid failure is logged as `bank_sync.sync_failed` rather than raised: the response
    has gone, and the next webhook or the nightly sync (spec 15) tries again.
    """
    with get_sessionmaker()() as session:
        try:
            sync_connection(
                session, plaid, business_id=business_id, connection_id=connection_id
            )
        except PlaidError as exc:
            log.warning(
                "bank_sync.sync_failed",
                business_id=str(business_id),
                connection_id=str(connection_id),
                error_type=exc.error_type,
                error_code=exc.error_code,
                request_id=exc.request_id,
            )


def connection_for_item(
    session: Session, *, plaid_item_id: str
) -> tuple[uuid.UUID, uuid.UUID] | None:
    """The `(business_id, connection_id)` of a Plaid item; None when it is not stored."""
    connection = repository.connection_for_item(session, plaid_item_id=plaid_item_id)
    return None if connection is None else (connection.business_id, connection.id)
