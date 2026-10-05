"""Spec 14: POST /v1/webhooks/plaid. Webhooks are signed here with a test key."""

import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.bank_sync import webhooks
from app.modules.bank_sync.models import BankConnection, BankTransaction
from app.modules.bank_sync.plaid import PlaidError, get_plaid_client
from app.settings import get_settings
from tests import webhook_signing as signing
from tests.test_bank_connect import link_path
from tests.test_businesses import HARBOR, Caller, _owner
from tests.test_transaction_sync import (
    Connected,
    SyncFake,
    checking,
    make_connection,
    page,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)
URL = "/v1/webhooks/plaid"
INVALID = "Invalid webhook signature."


@pytest.fixture(autouse=True)
def _fresh_key_cache() -> Iterator[None]:
    webhooks.clear_key_cache()
    yield
    webhooks.clear_key_cache()


@pytest.fixture
def fake() -> Iterator[SyncFake]:
    plaid = SyncFake()
    plaid.keys = {signing.KID: signing.jwk()}
    app.dependency_overrides[get_plaid_client] = lambda: plaid
    yield plaid
    app.dependency_overrides.pop(get_plaid_client, None)


@pytest.fixture
def owner() -> tuple[Caller, str]:
    return _owner({**HARBOR, "name": f"Hook {uuid.uuid4().hex[:6]}"})


@pytest.fixture
def connected(owner: tuple[Caller, str]) -> Connected:
    return make_connection(owner[1], [checking()])


def post(content: bytes, headers: dict[str, str]) -> Any:
    return client.post(URL, content=content, headers=headers)


def assert_invalid(response: Any, fake: SyncFake) -> None:
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == INVALID
    assert fake.cursors == []


def stored_count(c: Connected) -> int:
    with get_sessionmaker()() as session:
        return len(
            session.scalars(
                select(BankTransaction.id).where(
                    BankTransaction.business_id == c.business_id
                )
            ).all()
        )


# S4 - only Plaid can trigger a sync


def test_bad_header_rejected(fake: SyncFake, connected: Connected) -> None:
    content = signing.body(connected.plaid_item_id)
    claims = {"iat": int(time.time()), "request_body_sha256": "x"}
    for header in (
        None,
        "not-a-jwt",
        jwt.encode(claims, "secret", algorithm="HS256", headers={"kid": signing.KID}),
        jwt.encode(claims, None, algorithm=None, headers={"kid": signing.KID}),
    ):
        headers = {"Content-Type": "application/json"}
        if header is not None:
            headers["Plaid-Verification"] = header
        assert_invalid(post(content, headers), fake)


def test_wrong_key_rejected(fake: SyncFake, connected: Connected) -> None:
    content = signing.body(connected.plaid_item_id)

    response = post(content, signing.headers(content, key=signing.OTHER_KEY))

    assert_invalid(response, fake)


def test_stale_iat(fake: SyncFake, connected: Connected) -> None:
    content = signing.body(connected.plaid_item_id)
    now = int(time.time())

    assert_invalid(post(content, signing.headers(content, iat=now - 301)), fake)
    response = post(content, signing.headers(content, iat=now - 299))
    assert response.status_code == 200


def test_body_hash_mismatch(fake: SyncFake, connected: Connected) -> None:
    content = signing.body(connected.plaid_item_id)
    headers = signing.headers(content)
    tampered = content.replace(b"SYNC_UPDATES_AVAILABLE", b"SYNC_UPDATES_AVAILABLF")

    assert_invalid(post(tampered, headers), fake)


def test_expired_key(fake: SyncFake, connected: Connected) -> None:
    content = signing.body(connected.plaid_item_id)
    fake.keys = {signing.KID: signing.jwk(expired_at=int(time.time()) - 1)}

    assert_invalid(post(content, signing.headers(content)), fake)

    webhooks.clear_key_cache()
    fake.keys = {signing.KID: signing.jwk(expired_at=None)}
    assert post(content, signing.headers(content)).status_code == 200


def test_key_fetch_fails(fake: SyncFake, connected: Connected) -> None:
    content = signing.body(connected.plaid_item_id)
    fake.fail = {
        "key": PlaidError(error_type="API_ERROR", error_code="X", request_id="r")
    }

    response = post(content, signing.headers(content))

    assert response.status_code == 502
    assert response.headers["content-type"] == "application/problem+json"
    assert fake.cursors == []


def test_key_cached(fake: SyncFake, connected: Connected) -> None:
    content = signing.body(connected.plaid_item_id)

    assert post(content, signing.headers(content)).status_code == 200
    assert post(content, signing.headers(content)).status_code == 200

    assert fake.key_calls == [signing.KID]


def test_sync_updates_available_syncs(
    fake: SyncFake, owner: tuple[Caller, str]
) -> None:
    chq = checking()
    c = make_connection(owner[1], [chq])
    fake.script = [page([chq], added=[tx("w1", chq), tx("w2", chq)], cursor="cw")]
    content = signing.body(c.plaid_item_id)

    response = post(content, signing.headers(content))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert stored_count(c) == 2
    with get_sessionmaker()() as session:
        cursor = session.scalar(
            select(BankConnection.transactions_cursor).where(
                BankConnection.id == c.connection_id
            )
        )
    assert cursor == "cw"


def test_other_webhooks_ignored(fake: SyncFake, connected: Connected) -> None:
    item = connected.plaid_item_id
    bodies = [
        signing.body(item, code="DEFAULT_UPDATE"),
        json.dumps(
            {"webhook_type": "ITEM", "webhook_code": "ERROR", "item_id": item}
        ).encode(),
        signing.body(f"item-{uuid.uuid4().hex}"),
    ]
    for content in bodies:
        response = post(content, signing.headers(content))
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    assert fake.cursors == []


def test_malformed_body(fake: SyncFake, connected: Connected) -> None:
    bodies = [
        b"[]",
        json.dumps(
            {"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE"}
        ).encode(),
        json.dumps(
            {
                "webhook_type": "TRANSACTIONS",
                "webhook_code": "SYNC_UPDATES_AVAILABLE",
                "item_id": 123,
            }
        ).encode(),
        b'"not json',
    ]
    for content in bodies:
        response = post(content, signing.headers(content))
        assert response.status_code == 422, content
        assert response.headers["content-type"] == "application/problem+json"
    assert fake.cursors == []


def test_only_public_v1_route(fake: SyncFake) -> None:
    using = TestClient(app, raise_server_exceptions=False)
    paths = app.openapi()["paths"]
    public = []
    for path, methods in paths.items():
        if not path.startswith("/v1"):
            continue
        for method in methods:
            response = using.request(method.upper(), path)
            clerk_rejected = (
                response.status_code == 401
                and response.json().get("detail") == "Authentication required."
            )
            if not clerk_rejected:
                public.append((method, path))

    assert public == [("post", URL)]


def test_background_sync_failure_logged(
    fake: SyncFake, connected: Connected, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.script = [
        PlaidError(
            error_type="ITEM_ERROR", error_code="ITEM_LOGIN_REQUIRED", request_id="r-7"
        )
    ]
    content = signing.body(connected.plaid_item_id)
    configure_logging()
    capsys.readouterr()

    response = post(content, signing.headers(content))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    failed = [line for line in lines if line["event"] == "bank_sync.sync_failed"]
    assert len(failed) == 1
    assert failed[0]["connection_id"] == str(connected.connection_id)
    assert failed[0]["error_type"] == "ITEM_ERROR"
    assert failed[0]["error_code"] == "ITEM_LOGIN_REQUIRED"
    assert failed[0]["request_id"] == "r-7"


# S5 - link tokens carry the webhook URL


@pytest.mark.parametrize(
    ("value", "url"),
    [
        (
            "https://example.test/v1/webhooks/plaid",
            "https://example.test/v1/webhooks/plaid",
        ),
        (None, None),
        # As copied from .env.example: empty means no webhook, never "".
        ("", None),
    ],
)
def test_link_token_webhook(
    fake: SyncFake,
    owner: tuple[Caller, str],
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
    url: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("PLAID_WEBHOOK_URL", raising=False)
    else:
        monkeypatch.setenv("PLAID_WEBHOOK_URL", value)
    get_settings.cache_clear()
    try:
        caller, business_id = owner
        response = client.post(link_path(business_id), headers=caller.headers)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()

    assert response.status_code == 200
    assert fake.link_requests[-1].webhook == url
