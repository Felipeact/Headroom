"""Spec 17a S2: connect a bank through Flinks. Fakes stand in for Flinks and Plaid."""

import json
import uuid
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.audit import AuditLog
from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.bank_sync import flinks as flinks_module
from app.modules.bank_sync.flinks import FlinksError, get_flinks_client
from app.modules.bank_sync.models import BankAccount, BankConnection
from app.modules.bank_sync.service import flinks_item_id
from app.modules.bank_sync.tokens import decrypt_access_token
from app.settings import get_settings
from tests.flinks_support import (
    ACCOUNT_NUMBER,
    HOLDER_NAME,
    INSTITUTION_ID,
    FakeFlinks,
    flinks,  # noqa: F401 - fixture
    flinks_account,
    no_flinks,  # noqa: F401 - fixture
)
from tests.test_bank_connect import (
    PUBLIC_TOKEN,
    FakePlaid,
    fake,  # noqa: F401 - fixture
)
from tests.test_bookkeeper_access import add_bookkeeper
from tests.test_businesses import BAYVIEW, HARBOR, Caller, _owner
from tests.test_flinks_client import DETAIL, flinks_api, mock_client

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

LOGIN_ID = "8b35f6c8-e7b6-41d3-98f8-08d68b7f8d31"
STILL_PREPARING = "Your bank is still preparing your accounts. Try again in a minute."
PROVIDER_UNAVAILABLE = "We couldn't reach our bank connection provider. Try again."
FLINKS_SETTINGS = (
    "flinks_instance",
    "flinks_customer_id",
    "flinks_auth_key",
    "flinks_api_key",
)


def url_path(business_id: str) -> str:
    return f"/v1/businesses/{business_id}/bank/flinks/connect-url"


def connections_path(business_id: str) -> str:
    return f"/v1/businesses/{business_id}/bank/connections"


@pytest.fixture(autouse=True)
def _fresh_login_id() -> None:
    """A loginId belongs to one connection, whatever the business (AD-142's unique)."""
    global LOGIN_ID
    LOGIN_ID = str(uuid.uuid4())


def connect_flinks(
    caller: Caller, business_id: str, login_id: str | None = None
) -> Any:
    return client.post(
        connections_path(business_id),
        json={"provider": "flinks", "login_id": login_id or LOGIN_ID},
        headers=caller.headers,
    )


def owner() -> tuple[Caller, str]:
    return _owner({**HARBOR, "name": f"Flinks {uuid.uuid4().hex[:6]}"})


def stored(business_id: str) -> tuple[list[BankConnection], list[BankAccount]]:
    bid = uuid.UUID(business_id)
    with get_sessionmaker()() as session:
        connections = list(
            session.scalars(
                select(BankConnection).where(BankConnection.business_id == bid)
            )
        )
        accounts = list(
            session.scalars(select(BankAccount).where(BankAccount.business_id == bid))
        )
        session.expunge_all()
    return connections, accounts


@pytest.fixture
def real_client() -> Iterator[None]:
    """The real HTTP client over a mocked Flinks: what reaches the logs is real."""
    flinks_client, _, _ = mock_client(flinks_api())
    app.dependency_overrides[get_flinks_client] = lambda: flinks_client
    yield
    app.dependency_overrides.pop(get_flinks_client, None)


# Connect URL


@pytest.mark.parametrize(
    ("instance", "origin", "demo"),
    [
        ("toolbox", "https://toolbox-iframe.private.fin.ag", ["true"]),
        ("acme", "https://acme-iframe.private.fin.ag", None),
    ],
    ids=["connect_url_sandbox", "connect_url_production_has_no_demo"],
)
def test_connect_url(instance: str, origin: str, demo: list[str] | None) -> None:
    """C7, C8."""
    flinks_client, _, _ = mock_client(flinks_api(), instance=instance)
    app.dependency_overrides[get_flinks_client] = lambda: flinks_client
    try:
        caller, business_id = owner()
        response = client.post(url_path(business_id), headers=caller.headers)
    finally:
        app.dependency_overrides.pop(get_flinks_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["origin"] == origin
    url = urlsplit(body["connect_url"])
    assert f"{url.scheme}://{url.netloc}" == origin
    assert url.path == "/v2/"
    query = parse_qs(url.query)
    assert query["authorizeToken"] == ["token-1"]
    assert query["jsRedirect"] == ["true"]
    assert query["daysOfTransactions"] == ["Days365"]
    assert query["language"] == ["en"]
    assert query.get("demo") == demo


def test_connect_url_sandbox(flinks: FakeFlinks) -> None:  # noqa: F811
    """C7: through the route, with the fake, the origin is passed on as is."""
    caller, business_id = owner()

    response = client.post(url_path(business_id), headers=caller.headers)

    assert response.status_code == 200
    assert response.json()["origin"] == "https://toolbox-iframe.private.fin.ag"


@pytest.mark.parametrize("unset", FLINKS_SETTINGS)
def test_connect_url_not_configured(
    unset: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C9: the real dependency, with one of the four settings missing."""
    settings = get_settings().model_copy(
        update={
            **{name: "set" for name in FLINKS_SETTINGS},
            unset: None,
        }
    )
    monkeypatch.setattr(flinks_module, "get_settings", lambda: settings)
    get_flinks_client.cache_clear()
    try:
        caller, business_id = owner()
        response = client.post(url_path(business_id), headers=caller.headers)
    finally:
        get_flinks_client.cache_clear()

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "Connecting through Flinks isn't available."


def test_connect_url_denied(flinks: FakeFlinks) -> None:  # noqa: F811
    """C10: a bookkeeper gets 403 and another business's owner 404."""
    _, business_id = owner()
    bookkeeper = add_bookkeeper(business_id)
    stranger, _ = _owner({**BAYVIEW, "name": f"Other {uuid.uuid4().hex[:6]}"})

    assert (
        client.post(url_path(business_id), headers=bookkeeper.headers).status_code
        == 403
    )
    assert (
        client.post(url_path(business_id), headers=stranger.headers).status_code == 404
    )
    assert flinks.calls == []


def test_flinks_connect_denied(flinks: FakeFlinks) -> None:  # noqa: F811
    """C10."""
    _, business_id = owner()
    bookkeeper = add_bookkeeper(business_id)
    stranger, _ = _owner({**BAYVIEW, "name": f"Other {uuid.uuid4().hex[:6]}"})

    assert connect_flinks(bookkeeper, business_id).status_code == 403
    assert connect_flinks(stranger, business_id).status_code == 404
    assert flinks.calls == []
    assert stored(business_id) == ([], [])


# Connect


def test_flinks_connect_stores_connection(flinks: FakeFlinks) -> None:  # noqa: F811
    """C11."""
    caller, business_id = owner()

    response = connect_flinks(caller, business_id)

    assert response.status_code == 201
    assert response.json()["provider"] == "flinks"
    (connection,), (account,) = stored(business_id)
    assert connection.provider == "flinks"
    assert connection.provider_item_id == flinks_item_id(LOGIN_ID)
    assert connection.provider_item_id != LOGIN_ID
    assert decrypt_access_token(connection.access_token_ciphertext) == LOGIN_ID
    assert connection.provider_institution_id == INSTITUTION_ID
    assert connection.transactions_cursor is None
    assert (account.mask, account.type, account.included) == ("6789", "checking", True)
    with get_sessionmaker()() as session:
        (audit,) = session.scalars(
            select(AuditLog).where(
                AuditLog.business_id == uuid.UUID(business_id),
                AuditLog.action == "bank_connection.created",
            )
        )
    assert audit.details == {
        "provider": "flinks",
        "institution_id": INSTITUTION_ID,
        "account_count": 1,
    }


def test_flinks_connect_unknown_type_is_other(flinks: FakeFlinks) -> None:  # noqa: F811
    """C11: an account type Flinks names and we don't map is stored as `other`."""
    flinks.accounts_list = [flinks_account("Brokerage", type="other")]
    caller, business_id = owner()

    assert connect_flinks(caller, business_id).status_code == 201

    (_, (account,)) = stored(business_id)
    assert (account.type, account.included) == ("other", False)


def test_flinks_connect_queues_first_sync(flinks: FakeFlinks) -> None:  # noqa: F811
    """C13: the background sync runs once, with transactions."""
    caller, business_id = owner()

    assert connect_flinks(caller, business_id).status_code == 201

    syncs = [c for c in flinks.accounts_calls if c.with_transactions]
    assert len(syncs) == 1
    assert syncs[0].login_id == LOGIN_ID


def test_flinks_connect_enables_refresh(flinks: FakeFlinks) -> None:  # noqa: F811
    """C14."""
    caller, business_id = owner()

    assert connect_flinks(caller, business_id).status_code == 201

    assert flinks.refresh_enabled == [LOGIN_ID]


@pytest.mark.parametrize(
    "body",
    [
        {"provider": "flinks", "public_token": PUBLIC_TOKEN},
        {"provider": "plaid", "login_id": LOGIN_ID},
        {"provider": "flinks", "login_id": LOGIN_ID, "public_token": PUBLIC_TOKEN},
        {"provider": "flinks"},
        {"provider": "flinks", "login_id": "not-a-uuid"},
    ],
    ids=["flinks_public_token", "plaid_login_id", "both", "neither", "bad_uuid"],
)
def test_connect_body_validation(
    body: dict[str, str],
    flinks: FakeFlinks,  # noqa: F811
    fake: FakePlaid,  # noqa: F811
) -> None:
    """C15."""
    caller, business_id = owner()

    response = client.post(
        connections_path(business_id), json=body, headers=caller.headers
    )

    assert response.status_code == 422
    assert LOGIN_ID not in response.text and PUBLIC_TOKEN not in response.text
    assert flinks.calls == [] and fake.calls == []


def test_connect_body_validation_plaid_default(
    flinks: FakeFlinks,  # noqa: F811
    fake: FakePlaid,  # noqa: F811
) -> None:
    """C15: a body with only `public_token` is still a Plaid connect."""
    caller, business_id = owner()

    response = client.post(
        connections_path(business_id),
        json={"public_token": PUBLIC_TOKEN},
        headers=caller.headers,
    )

    assert response.status_code == 201
    assert response.json()["provider"] == "plaid"
    assert flinks.calls == []


def test_flinks_duplicate_institution_is_409(flinks: FakeFlinks) -> None:  # noqa: F811
    """C16."""
    caller, business_id = owner()
    assert connect_flinks(caller, business_id).status_code == 201

    response = connect_flinks(caller, business_id, str(uuid.uuid4()))

    assert response.status_code == 409
    assert response.json()["detail"] == "This bank is already connected."
    assert len(stored(business_id)[0]) == 1


def test_flinks_connect_still_preparing(flinks: FakeFlinks) -> None:  # noqa: F811
    """C17."""
    caller, business_id = owner()
    flinks.pending_calls = 1

    response = connect_flinks(caller, business_id)

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == STILL_PREPARING
    assert stored(business_id) == ([], [])
    assert flinks.deleted == []
    assert flinks.refresh_enabled == []

    retry = connect_flinks(caller, business_id)

    assert retry.status_code == 201
    assert len(stored(business_id)[0]) == 1


@pytest.mark.parametrize("method", ["accounts", "enable_nightly_refresh"])
def test_flinks_failure_is_503(method: str, flinks: FakeFlinks) -> None:  # noqa: F811
    """C19: nothing is stored when any Flinks call of the connect fails."""
    flinks.fail[method] = FlinksError(http_status=500, flinks_code="INTERNAL")
    caller, business_id = owner()

    response = connect_flinks(caller, business_id)

    assert response.status_code == 503
    assert response.json()["detail"] == PROVIDER_UNAVAILABLE
    assert stored(business_id) == ([], [])


def test_flinks_connect_url_failure_is_503(flinks: FakeFlinks) -> None:  # noqa: F811
    """C19."""
    flinks.fail["connect_url"] = FlinksError(
        http_status=None, flinks_code="ReadTimeout"
    )
    caller, business_id = owner()

    response = client.post(url_path(business_id), headers=caller.headers)

    assert response.status_code == 503
    assert response.json()["detail"] == PROVIDER_UNAVAILABLE


def test_list_shows_provider(flinks: FakeFlinks, fake: FakePlaid) -> None:  # noqa: F811
    """C6."""
    caller, business_id = owner()
    assert connect_flinks(caller, business_id).status_code == 201
    assert (
        client.post(
            connections_path(business_id),
            json={"public_token": PUBLIC_TOKEN},
            headers=caller.headers,
        ).status_code
        == 201
    )

    response = client.get(connections_path(business_id), headers=caller.headers)

    assert response.status_code == 200
    assert sorted(c["provider"] for c in response.json()["items"]) == [
        "flinks",
        "plaid",
    ]


def test_no_secrets_in_logs_or_responses(
    real_client: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """C20: a connect, its first sync, a disconnect and a failure, through the real
    client; the mocked Flinks answers carry an account number and a holder's name."""
    configure_logging()
    caller, business_id = owner()
    capsys.readouterr()

    created = connect_flinks(caller, business_id)
    listed = client.get(connections_path(business_id), headers=caller.headers)
    connection_id = created.json()["id"]
    removed = client.delete(
        f"{connections_path(business_id)}/{connection_id}", headers=caller.headers
    )
    failing, _, _ = mock_client(
        flinks_api(
            fail={
                "Authorize": httpx.Response(
                    401,
                    json={"FlinksCode": "INVALID_LOGIN", "Message": f"bad {LOGIN_ID}"},
                )
            }
        )
    )
    app.dependency_overrides[get_flinks_client] = lambda: failing
    failed = connect_flinks(caller, business_id)
    out = capsys.readouterr()

    assert (created.status_code, removed.status_code, failed.status_code) == (
        201,
        204,
        503,
    )
    logs = out.out + out.err
    assert "flinks.request_failed" in logs
    assert "DeleteCard" in logs  # the httpx request line is logged, redacted
    for secret in (LOGIN_ID, ACCOUNT_NUMBER, HOLDER_NAME):
        assert secret not in logs
        for response in (created, listed, failed):
            assert secret not in response.text
    assert json.dumps(DETAIL).count(ACCOUNT_NUMBER) == 1  # the mock does carry it
