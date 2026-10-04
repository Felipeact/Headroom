import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

import structlog
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.modules.bank_sync import repository
from app.modules.bank_sync.models import BankAccount
from app.modules.bank_sync.plaid import (
    ExchangedItem,
    LinkToken,
    LinkTokenRequest,
    PlaidAccount,
    PlaidClient,
    PlaidError,
)
from app.modules.bank_sync.tokens import encrypt_access_token

INSTITUTION_INDEX = "uq_bank_connections_business_id_plaid_institution_id"
# 24 months of history, Plaid's maximum.
DAYS_REQUESTED = 730

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


@dataclass(frozen=True)
class AccountView:
    id: uuid.UUID
    name: str
    type: str
    mask: str | None
    currency: str
    balance_cents: int | None


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
    return BankAccount(
        business_id=business_id,
        connection_id=connection_id,
        plaid_account_id=account.account_id,
        name=account.name,
        type=account_type(account.type, account.subtype),
        mask=account.mask,
        currency=currency,
        balance_cents=to_cents(account.current),
    )


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
            orig = exc.orig
            if (
                isinstance(orig, UniqueViolation)
                and orig.diag.constraint_name == INSTITUTION_INDEX
            ):
                raise DuplicateBankError from None
            raise
        rows = [
            _account(a, business_id=business_id, connection_id=connection.id)
            for a in accounts.accounts
        ]
        repository.insert_accounts(session, rows)
        audit.record(
            session,
            action="bank_connection.created",
            business_id=business_id,
            actor_user_id=str(user_id),
            target_type="bank_connection",
            target_id=str(connection.id),
            details={"institution_id": institution_id, "account_count": len(rows)},
        )
        view = ConnectionView(
            id=connection.id,
            institution_name=connection.institution_name,
            created_at=connection.created_at,
            accounts=sorted(
                (
                    AccountView(
                        id=row.id,
                        name=row.name,
                        type=row.type,
                        mask=row.mask,
                        currency=row.currency,
                        balance_cents=row.balance_cents,
                    )
                    for row in rows
                ),
                key=lambda a: a.name,
            ),
        )
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
