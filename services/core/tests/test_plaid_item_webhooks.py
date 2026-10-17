"""Spec 17: the Plaid `ITEM` webhooks that record and clear a login problem (door 6)."""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.inspection import inspect as sa_inspect

from app.db import get_sessionmaker
from app.main import app
from app.modules.bank_sync import webhooks
from app.modules.bank_sync.models import BankConnection
from app.modules.bank_sync.plaid import get_plaid_client
from tests import webhook_signing as signing
from tests.test_businesses import HARBOR, Caller, _owner
from tests.test_transaction_sync import Connected, SyncFake, checking, make_connection

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)
URL = "/v1/webhooks/plaid"


def item_body(item_id: str, code: str, **extra: Any) -> bytes:
    return signing.body(item_id, code=code, webhook_type="ITEM", **extra)


def plaid_error(code: str) -> dict[str, Any]:
    """The `error` object of an `ITEM` / `ERROR` webhook, as Plaid documents it."""
    return {
        "error_type": "ITEM_ERROR",
        "error_code": code,
        "error_code_reason": None,
        "error_message": "the login details of this item have changed",
        "display_message": None,
        "request_id": "req-hook",
        "causes": [],
        "status": 400,
        "documentation_url": "https://plaid.com/docs/errors/item/",
        "suggested_action": None,
    }


def post(content: bytes) -> Any:
    return client.post(URL, content=content, headers=signing.headers(content))


def columns(c: Connected) -> dict[str, Any]:
    with get_sessionmaker()() as session:
        found = session.get(BankConnection, c.connection_id)
        assert found is not None
        return {
            attr.key: getattr(found, attr.key)
            for attr in sa_inspect(found).mapper.column_attrs
        }


def set_login_required(c: Connected, value: bool) -> None:
    with get_sessionmaker()() as session:
        session.execute(
            update(BankConnection)
            .where(BankConnection.id == c.connection_id)
            .values(login_required=value)
        )
        session.commit()


@pytest.fixture
def fake() -> Iterator[SyncFake]:
    plaid = SyncFake()
    plaid.keys = {signing.KID: signing.jwk()}
    app.dependency_overrides[get_plaid_client] = lambda: plaid
    webhooks.clear_key_cache()
    yield plaid
    app.dependency_overrides.pop(get_plaid_client, None)
    webhooks.clear_key_cache()


@pytest.fixture
def owner() -> tuple[Caller, str]:
    return _owner({**HARBOR, "name": f"Item hook {uuid.uuid4().hex[:6]}"})


def test_item_error_login_required(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C22."""
    target = make_connection(owner[1], [checking()])
    sibling = make_connection(owner[1], [checking()])
    untouched = columns(sibling)

    response = post(
        item_body(
            target.provider_item_id, "ERROR", error=plaid_error("ITEM_LOGIN_REQUIRED")
        )
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert columns(target)["login_required"] is True
    assert columns(sibling) == untouched
    assert fake.cursors == []


@pytest.mark.parametrize(
    "case", ["other_error_code", "null_error", "pending_disconnect", "unknown_item"]
)
def test_item_webhooks_ignored(
    fake: SyncFake, owner: tuple[Caller, str], case: str
) -> None:
    """C23."""
    c = make_connection(owner[1], [checking()])
    before = columns(c)
    content = {
        "other_error_code": item_body(
            c.provider_item_id, "ERROR", error=plaid_error("INSTITUTION_DOWN")
        ),
        "null_error": item_body(c.provider_item_id, "ERROR", error=None),
        "pending_disconnect": item_body(
            c.provider_item_id, "PENDING_DISCONNECT", reason="INSTITUTION_MIGRATION"
        ),
        "unknown_item": item_body(
            f"item-{uuid.uuid4().hex}",
            "ERROR",
            error=plaid_error("ITEM_LOGIN_REQUIRED"),
        ),
    }[case]

    response = post(content)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert fake.cursors == []
    assert columns(c) == before


def test_login_repaired_syncs(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C24."""
    c = make_connection(owner[1], [checking()])
    set_login_required(c, True)

    response = post(item_body(c.provider_item_id, "LOGIN_REPAIRED"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(fake.cursors) == 1
    after = columns(c)
    assert after["login_required"] is False
    assert after["last_synced_at"] is not None
