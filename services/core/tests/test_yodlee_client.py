"""Spec 17b: the Yodlee port over a fake HTTP transport (no network)."""

import json
from collections.abc import Callable
from datetime import date

import httpx
import pytest

from app.modules.bank_sync.yodlee import HttpxYodleeClient, YodleeError
from app.settings import Settings

ADMIN = "admin-login-name"
USER = "hr-0123456789abcdef"


def settings() -> Settings:
    return Settings.model_construct(
        yodlee_api_url="https://yodlee.test/ysl",
        yodlee_client_id="client-id",
        yodlee_client_secret="client-secret",
        yodlee_admin_login_name=ADMIN,
        yodlee_fastlink_url="https://fastlink.test/fastlink",
        yodlee_fastlink_config_name="Headroom",
    )


def client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> HttpxYodleeClient:
    return HttpxYodleeClient(settings(), transport=httpx.MockTransport(handler))


def token_response() -> httpx.Response:
    return httpx.Response(
        201, json={"token": {"accessToken": "tok", "issuedAt": "x", "expiresIn": 1800}}
    )


def test_timeout_raises_yodlee_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(YodleeError) as raised:
        client(handler).accounts(USER, "1")
    assert raised.value.http_status is None


def test_error_carries_no_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"errorCode": "Y301", "errorMessage": "SECRET-BODY-TEXT"},
        )

    with pytest.raises(YodleeError) as raised:
        client(handler).accounts(USER, "1")
    error = raised.value
    assert (error.http_status, error.error_code) == (400, "Y301")
    assert "SECRET-BODY-TEXT" not in str(error)
    assert "SECRET-BODY-TEXT" not in repr(vars(error))


def transactions_handler(
    rows: list[dict[str, object]],
) -> Callable[..., httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            return token_response()
        skip = int(request.url.params["skip"])
        return httpx.Response(200, json={"transaction": rows} if skip == 0 else {})

    return handler


def row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 7,
        "accountId": 5,
        "baseType": "DEBIT",
        "status": "POSTED",
        "date": "2026-10-01",
        "amount": {"amount": 25.0, "currency": "CAD"},
        "description": {"simple": "Rent", "original": "RENT PAYMENT"},
    }
    return {**base, **overrides}


def test_debit_credit_sign() -> None:
    rows = [row(id=1, baseType="DEBIT"), row(id=2, baseType="CREDIT")]
    found = client(transactions_handler(rows)).transactions(
        USER, frozenset({"5"}), date(2026, 1, 1)
    )
    assert {t.transaction_id: t.amount for t in found} == {
        "yodlee:1": 25.0,
        "yodlee:2": -25.0,
    }


def test_only_posted() -> None:
    rows = [
        row(id=1, status="POSTED"),
        row(id=2, status="PENDING"),
        row(id=3, status="SCHEDULED"),
        row(id=4, status="POSTED", accountId=99),
    ]
    found = client(transactions_handler(rows)).transactions(
        USER, frozenset({"5"}), date(2026, 1, 1)
    )
    assert [t.transaction_id for t in found] == ["yodlee:1"]


def test_user_token_never_admin() -> None:
    logins: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            logins.append(request.headers["loginName"])
            return token_response()
        return httpx.Response(200, json={"account": []})

    yodlee = client(handler)
    yodlee.launch(USER, None)
    yodlee.accounts(USER, "1")
    yodlee.transactions(USER, frozenset(), date(2026, 1, 1))
    assert logins and set(logins) == {USER}


def test_register_uses_admin_token_only_for_registration() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            login = request.headers["loginName"]
            seen.append(("token", login))
            if login == USER:
                return httpx.Response(400, json={"errorCode": "Y305"})
            return token_response()
        seen.append(
            (request.url.path, json.loads(request.content)["user"]["loginName"])
        )
        return httpx.Response(201, json={})

    client(handler).register_user(USER)
    assert seen == [
        ("token", USER),
        ("token", ADMIN),
        ("/ysl/user/register", USER),
    ]


def test_register_skips_known_user() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return token_response()

    client(handler).register_user(USER)

    assert paths == ["/ysl/auth/token"]


def test_delete_missing_provider_account_is_ok() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.url.path.endswith("/auth/token"):
            return token_response()
        return httpx.Response(400, json={"errorCode": "Y807"})

    client(handler).delete_provider_account(USER, "1")

    assert "DELETE" not in methods


def test_timeout_is_15_seconds() -> None:
    seen: list[dict[str, float | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions["timeout"])
        return token_response()

    client(handler).launch(USER, None)

    assert seen == [{"connect": 15.0, "read": 15.0, "write": 15.0, "pool": 15.0}]


@pytest.mark.parametrize(
    "body",
    [
        {"account": [{"CONTAINER": "bank", "providerAccountId": 1}]},
        {"account": ["not-an-object"]},
    ],
    ids=["account_without_id", "account_not_an_object"],
)
def test_malformed_answer_is_a_yodlee_error(body: dict[str, object]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            return token_response()
        return httpx.Response(200, json=body)

    with pytest.raises(YodleeError) as raised:
        client(handler).accounts(USER, "1")

    assert raised.value.error_code == "INVALID_RESPONSE"


def test_malformed_transaction_date_is_a_yodlee_error() -> None:
    rows = [row(date="not-a-date")]

    with pytest.raises(YodleeError) as raised:
        client(transactions_handler(rows)).transactions(
            USER, frozenset({"5"}), date(2026, 1, 1)
        )

    assert raised.value.error_code == "INVALID_RESPONSE"
