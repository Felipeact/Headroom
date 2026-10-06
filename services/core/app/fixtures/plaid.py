"""A `PlaidClient` that serves a sample bank instead of calling Plaid (spec 18, AD-069).

The loader hands it to `bank_sync.service`, so a sample goes through the same connect and
sync path as a real bank. Plaid IDs are `sample-<business_id>-<key>`, unique per load.
Amounts go back into Plaid's convention (positive is money out) here, so that
`bank_sync` stays the one place that flips a Plaid amount for storage.
"""

import uuid
from collections.abc import Iterable
from typing import Any, NoReturn

from app.fixtures.harbor_street import SampleAccount, SampleBank, SampleTransaction
from app.modules.bank_sync.plaid import (
    ExchangedItem,
    ItemAccounts,
    LinkToken,
    LinkTokenRequest,
    PlaidAccount,
    PlaidError,
    PlaidTransaction,
    SyncPage,
)

ACCESS_TOKEN = "sample-not-a-token"
DONE_CURSOR = "sample-done"
# Our account type as Plaid's type and subtype.
PLAID_TYPES = {
    "checking": ("depository", "checking"),
    "savings": ("depository", "savings"),
    "credit_card": ("credit", "credit card"),
    "line_of_credit": ("credit", "line of credit"),
}


def _dollars(cents: int | None) -> float | None:
    return None if cents is None else cents / 100


class FixturePlaidClient:
    """One sample bank, as Plaid would report it for one business."""

    def __init__(
        self,
        bank: SampleBank,
        history: Iterable[SampleTransaction],
        *,
        business_id: uuid.UUID,
    ) -> None:
        self._bank = bank
        self._prefix = f"sample-{business_id}"
        keys = {a.key for a in bank.accounts}
        self._history = [t for t in history if t.account_key in keys]

    def _id(self, key: str) -> str:
        return f"{self._prefix}-{key}"

    def _account(self, account: SampleAccount) -> PlaidAccount:
        plaid_type, subtype = PLAID_TYPES[account.type]
        return PlaidAccount(
            account_id=self._id(account.key),
            name=account.name,
            type=plaid_type,
            subtype=subtype,
            mask=account.mask,
            current=_dollars(account.balance_cents),
            iso_currency_code=account.currency,
            unofficial_currency_code=None,
            available=_dollars(account.available_cents),
        )

    def _transaction(self, t: SampleTransaction) -> PlaidTransaction:
        return PlaidTransaction(
            transaction_id=self._id(t.key),
            account_id=self._id(t.account_key),
            # Plaid's sign: positive is money out.
            amount=-t.amount_cents / 100,
            iso_currency_code=t.currency,
            unofficial_currency_code=None,
            date=t.date,
            pending=False,
            pending_transaction_id=None,
            name=t.description,
            merchant_name=None,
            counterparties=(t.counterparty,) if t.counterparty else (),
            category=t.category,
            category_detailed=t.category_detailed,
        )

    @staticmethod
    def _unsupported() -> NoReturn:
        raise PlaidError(
            error_type="SAMPLE", error_code="NOT_SUPPORTED", request_id=None
        )

    def create_link_token(self, request: LinkTokenRequest) -> LinkToken:
        self._unsupported()

    def exchange_public_token(self, public_token: str) -> ExchangedItem:
        return ExchangedItem(
            item_id=self._id(self._bank.key), access_token=ACCESS_TOKEN
        )

    def get_accounts(self, access_token: str) -> ItemAccounts:
        return ItemAccounts(
            institution_id=self._bank.institution_id,
            accounts=[self._account(a) for a in self._bank.accounts],
        )

    def get_institution_name(self, institution_id: str) -> str:
        return self._bank.institution_name

    def remove_item(self, access_token: str) -> None:
        self._unsupported()

    def sync_transactions(self, access_token: str, cursor: str | None) -> SyncPage:
        """The whole history on the first sync; nothing new after it."""
        added = [] if cursor else [self._transaction(t) for t in self._history]
        return SyncPage(
            added=added,
            modified=[],
            removed=[],
            accounts=[self._account(a) for a in self._bank.accounts],
            next_cursor=DONE_CURSOR,
            has_more=False,
        )

    def get_webhook_verification_key(self, key_id: str) -> dict[str, Any]:
        self._unsupported()
