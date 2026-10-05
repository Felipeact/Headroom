"""Spec 12: the real PlaidClient over a mocked plaid-python PlaidApi. No network."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import urllib3
from plaid import ApiException

from app.modules.bank_sync.plaid import (
    TIMEOUT_SECONDS,
    LinkTokenRequest,
    PlaidError,
    SdkPlaidClient,
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
