"""Spec 12: the real PlaidClient over a mocked plaid-python PlaidApi. No network."""

import dataclasses
import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import urllib3
from plaid import ApiException

from app.modules.bank_sync.plaid import (
    TIMEOUT_SECONDS,
    LinkTokenRequest,
    PlaidAccount,
    PlaidError,
    PlaidTransaction,
    SdkPlaidClient,
    SyncPage,
)

REQUEST = LinkTokenRequest(
    client_user_id="9b2f6c1e-0000-4000-8000-000000000001",
    client_name="Headroom",
    language="en",
    country_codes=("CA",),
    products=("transactions",),
    days_requested=730,
)


class Model(SimpleNamespace):
    """Enough of a plaid-python response model: attributes plus `.get`."""

    def get(self, name: str, default: Any = None) -> Any:
        return getattr(self, name, default)


def sdk() -> MagicMock:
    api = MagicMock()
    api.link_token_create.return_value = Model(
        link_token="link-sandbox-1", expiration=datetime(2026, 10, 4, tzinfo=UTC)
    )
    api.item_public_token_exchange.return_value = Model(
        item_id="item-1", access_token="access-sandbox-1"
    )
    api.accounts_get.return_value = Model(
        item=Model(institution_id="ins_42"),
        accounts=[
            Model(
                account_id="acc-1",
                name="Chequing",
                type=Model(value="depository"),
                subtype=Model(value="checking"),
                mask="0001",
                balances=Model(current=12.5, iso_currency_code="CAD"),
            )
        ],
    )
    api.institutions_get_by_id.return_value = Model(
        institution=Model(name="TD Canada Trust")
    )
    return api


def test_sdk_requests() -> None:
    api = sdk()
    client = SdkPlaidClient(api)

    client.create_link_token(REQUEST)
    client.exchange_public_token("public-sandbox-1")
    accounts = client.get_accounts("access-sandbox-1")
    client.get_institution_name("ins_42")
    client.remove_item("access-sandbox-1")

    request = api.link_token_create.call_args.args[0]
    assert [c.value for c in request.country_codes] == ["CA"]
    assert [p.value for p in request.products] == ["transactions"]
    assert request.transactions.days_requested == 730
    assert request.language == "en"
    assert request.client_name == "Headroom"
    assert request.user.client_user_id == REQUEST.client_user_id

    assert api.item_public_token_exchange.call_args.args[0].public_token == (
        "public-sandbox-1"
    )
    assert api.accounts_get.call_args.args[0].access_token == "access-sandbox-1"
    by_id = api.institutions_get_by_id.call_args.args[0]
    assert by_id.institution_id == "ins_42"
    assert [c.value for c in by_id.country_codes] == ["CA"]
    assert api.item_remove.call_args.args[0].access_token == "access-sandbox-1"

    for method in (
        api.link_token_create,
        api.item_public_token_exchange,
        api.accounts_get,
        api.institutions_get_by_id,
        api.item_remove,
    ):
        assert method.call_args.kwargs == {"_request_timeout": TIMEOUT_SECONDS}
    assert TIMEOUT_SECONDS == 15

    assert accounts.institution_id == "ins_42"
    assert accounts.accounts[0].type == "depository"
    assert accounts.accounts[0].subtype == "checking"
    assert accounts.accounts[0].current == 12.5


def api_exception() -> ApiException:
    exc = ApiException(status=500, reason="Internal Server Error")
    exc.body = json.dumps(
        {
            "error_type": "API_ERROR",
            "error_code": "INTERNAL_SERVER_ERROR",
            "request_id": "req-1",
            "error_message": "something went wrong",
        }
    ).encode()
    return exc


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (api_exception(), ("API_ERROR", "INTERNAL_SERVER_ERROR", "req-1")),
        (
            urllib3.exceptions.ReadTimeoutError(None, "/accounts/get", "timed out"),  # type: ignore[arg-type]
            ("NETWORK", "ReadTimeoutError", None),
        ),
    ],
    ids=["api_exception", "read_timeout"],
)
def test_errors_mapped(raised: Exception, expected: tuple[Any, ...]) -> None:
    api = sdk()
    api.accounts_get.side_effect = raised

    with pytest.raises(PlaidError) as excinfo:
        SdkPlaidClient(api).get_accounts("access-sandbox-1")

    error = excinfo.value
    assert (error.error_type, error.error_code, error.request_id) == expected
    # `from None`: the SDK exception, with its body and headers, is not chained.
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


@pytest.mark.parametrize("available", [150.25, None])
def test_available_balance(available: float | None) -> None:
    api = sdk()
    api.accounts_get.return_value.accounts[0].balances = Model(
        current=12.5, available=available, iso_currency_code="CAD"
    )

    accounts = SdkPlaidClient(api).get_accounts("access-sandbox-1")

    assert accounts.accounts[0].available == available


# Spec 14: link tokens carry the webhook URL; /transactions/sync; verification keys


@pytest.mark.parametrize("webhook", ["https://example.test/v1/webhooks/plaid", None])
def test_link_token_webhook(webhook: str | None) -> None:
    api = sdk()

    SdkPlaidClient(api).create_link_token(dataclasses.replace(REQUEST, webhook=webhook))

    request = api.link_token_create.call_args.args[0]
    assert request.get("webhook") == webhook


def sync_response() -> Model:
    return Model(
        added=[
            Model(
                transaction_id="t1",
                account_id="acc-1",
                amount=12.34,
                iso_currency_code="CAD",
                unofficial_currency_code=None,
                date=date(2026, 9, 30),
                pending=True,
                pending_transaction_id=None,
                name="POS 4471 COASTAL",
                merchant_name="Coastal Supply Co",
                counterparties=[Model(name="Coastal Supply Co")],
                personal_finance_category=Model(
                    primary="GENERAL_MERCHANDISE",
                    detailed="GENERAL_MERCHANDISE_OTHER",
                ),
            )
        ],
        modified=[
            Model(
                transaction_id="t2",
                account_id="acc-1",
                amount=-500.0,
                iso_currency_code=None,
                unofficial_currency_code="BTC",
                date=date(2026, 9, 29),
                pending=False,
                pending_transaction_id="p2",
                name="Deposit",
            )
        ],
        removed=[Model(transaction_id="r1", account_id="acc-1")],
        accounts=[
            Model(
                account_id="acc-1",
                name="Chequing",
                type=Model(value="depository"),
                subtype=Model(value="checking"),
                mask="0001",
                balances=Model(current=80.0, available=79.5, iso_currency_code="CAD"),
            )
        ],
        next_cursor="cursor-2",
        has_more=True,
    )


def test_sync_transactions_request_and_mapping() -> None:
    api = sdk()
    api.transactions_sync.return_value = sync_response()
    client = SdkPlaidClient(api)

    result = client.sync_transactions("access-sandbox-1", None)
    client.sync_transactions("access-sandbox-1", "c1")

    first, second = (c.args[0] for c in api.transactions_sync.call_args_list)
    assert first.access_token == "access-sandbox-1"
    assert first.count == 500
    assert first.options.include_personal_finance_category is True
    assert first.get("cursor") is None
    assert second.cursor == "c1"
    for call in api.transactions_sync.call_args_list:
        assert call.kwargs == {"_request_timeout": TIMEOUT_SECONDS}

    assert result == SyncPage(
        added=[
            PlaidTransaction(
                transaction_id="t1",
                account_id="acc-1",
                amount=12.34,
                iso_currency_code="CAD",
                unofficial_currency_code=None,
                date=date(2026, 9, 30),
                pending=True,
                pending_transaction_id=None,
                name="POS 4471 COASTAL",
                merchant_name="Coastal Supply Co",
                counterparties=("Coastal Supply Co",),
                category="GENERAL_MERCHANDISE",
                category_detailed="GENERAL_MERCHANDISE_OTHER",
            )
        ],
        modified=[
            PlaidTransaction(
                transaction_id="t2",
                account_id="acc-1",
                amount=-500.0,
                iso_currency_code=None,
                unofficial_currency_code="BTC",
                date=date(2026, 9, 29),
                pending=False,
                pending_transaction_id="p2",
                name="Deposit",
                merchant_name=None,
                counterparties=(),
                category=None,
                category_detailed=None,
            )
        ],
        removed=["r1"],
        accounts=[
            PlaidAccount(
                account_id="acc-1",
                name="Chequing",
                type="depository",
                subtype="checking",
                mask="0001",
                current=80.0,
                available=79.5,
                iso_currency_code="CAD",
                unofficial_currency_code=None,
            )
        ],
        next_cursor="cursor-2",
        has_more=True,
    )


def test_sync_transactions_mutation_error() -> None:
    api = sdk()
    exc = ApiException(status=400, reason="Bad Request")
    exc.body = json.dumps(
        {
            "error_type": "TRANSACTIONS_ERROR",
            "error_code": "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION",
            "request_id": "req-m",
        }
    ).encode()
    api.transactions_sync.side_effect = exc

    with pytest.raises(PlaidError) as excinfo:
        SdkPlaidClient(api).sync_transactions("access-sandbox-1", "c1")

    assert excinfo.value.error_code == "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"


def test_webhook_verification_key() -> None:
    api = sdk()
    key = {
        "alg": "ES256",
        "crv": "P-256",
        "kid": "k1",
        "kty": "EC",
        "use": "sig",
        "x": "abc",
        "y": "def",
        "created_at": 1700000000,
        "expired_at": None,
    }
    api.webhook_verification_key_get.return_value = Model(
        key=MagicMock(to_dict=MagicMock(return_value=key))
    )

    result = SdkPlaidClient(api).get_webhook_verification_key("k1")

    assert api.webhook_verification_key_get.call_args.args[0].key_id == "k1"
    assert result == key
    assert isinstance(result, dict)
    assert "expired_at" in result


def test_update_mode_link_token() -> None:
    """Spec 17: update mode sends the access token, and no products or product options."""
    api = sdk()

    SdkPlaidClient(api).create_link_token(
        dataclasses.replace(
            REQUEST, products=(), days_requested=None, access_token="access-sandbox-1"
        )
    )

    request = api.link_token_create.call_args.args[0]
    assert request.access_token == "access-sandbox-1"
    assert "products" not in request
    assert "transactions" not in request
    assert "access-sandbox-1" not in repr(
        dataclasses.replace(REQUEST, access_token="access-sandbox-1")
    )
