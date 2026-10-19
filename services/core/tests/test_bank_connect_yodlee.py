"""Spec 17b: FastLink launch and connecting a bank through Yodlee (fake client, no network)."""

# ruff: noqa: F811

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.bank_sync import repository
from app.modules.bank_sync.tokens import decrypt_access_token
from app.modules.bank_sync.yodlee import YodleeError, get_yodlee_client
from app.settings import get_settings
from tests.test_bank_connect import (  # noqa: F401  (pytest fixtures)
    FakePlaid,
    audit_rows,
    client,
    connect,
    connections_path,
    fake,
    owner_a,
    owner_b,
    stored,
)
from tests.test_bookkeeper_access import add_bookkeeper
from tests.test_businesses import Caller
from tests.yodlee_support import (  # noqa: F401  (pytest fixtures)
    CONFIG_NAME,
    FASTLINK_URL,
    FakeYodlee,
    no_test_login,
    yodlee,
    yodlee_account,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

PROVIDER_UNAVAILABLE = "We couldn't reach our bank connection provider. Try again."
SETTINGS = [
    "YODLEE_API_URL",
    "YODLEE_CLIENT_ID",
    "YODLEE_CLIENT_SECRET",
    "YODLEE_ADMIN_LOGIN_NAME",
    "YODLEE_FASTLINK_URL",
    "YODLEE_FASTLINK_CONFIG_NAME",
]


def providers_path(business_id: str) -> str:
    return f"/v1/businesses/{business_id}/bank/providers"


def fastlink_path(business_id: str) -> str:
    return f"/v1/businesses/{business_id}/bank/yodlee/fastlink"


def launch(caller: Caller, business_id: str, body: Any = None) -> Any:
    return client.post(
        fastlink_path(business_id), json=body or {}, headers=caller.headers
    )


def new_provider_account() -> str:
    """Yodlee's provider-account IDs are unique across the table, so tests never reuse one."""
    return f"pa-{uuid.uuid4().hex[:10]}"


def yconnect(
    caller: Caller, business_id: str, provider_account_id: str | None = None
) -> Any:
    provider_account_id = provider_account_id or new_provider_account()
    return connect(
        caller,
        business_id,
        {"provider": "yodlee", "provider_account_id": provider_account_id},
    )


def login_name(business_id: str) -> str:
    return f"hr-{uuid.UUID(business_id).hex}"


# S1 and S2 - the provider shows, and Yodlee can be off


def test_list_shows_provider(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    connect(owner, business_id)
    assert yconnect(owner, business_id).status_code == 201

    items = client.get(connections_path(business_id), headers=owner.headers).json()[
        "items"
    ]
    assert sorted(i["provider"] for i in items) == ["plaid", "yodlee"]


@pytest.fixture
def prepare_real_yodlee(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[[str], None]]:
    """Builds the real dependency with all six settings set but one."""

    def prepare(unset: str) -> None:
        for name in SETTINGS:
            monkeypatch.setenv(name, "" if name == unset else "https://x.test/v")
        get_settings.cache_clear()
        get_yodlee_client.cache_clear()

    yield prepare
    get_settings.cache_clear()
    get_yodlee_client.cache_clear()


@pytest.mark.parametrize("unset", SETTINGS)
def test_off_when_any_setting_unset(
    unset: str,
    owner_a: tuple[Caller, str],
    prepare_real_yodlee: Callable[[str], None],
) -> None:
    owner, business_id = owner_a
    prepare_real_yodlee(unset)

    providers = client.get(providers_path(business_id), headers=owner.headers)
    assert providers.status_code == 200
    assert providers.json() == {"providers": ["plaid"]}
    assert launch(owner, business_id).status_code == 404


def test_providers_lists_yodlee(
    owner_a: tuple[Caller, str], yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    response = client.get(providers_path(business_id), headers=owner.headers)
    assert response.status_code == 200
    assert response.json() == {"providers": ["plaid", "yodlee"]}

    app.dependency_overrides[get_yodlee_client] = lambda: None
    response = client.get(providers_path(business_id), headers=owner.headers)
    assert response.json() == {"providers": ["plaid"]}


# S3 - FastLink launch


def test_fastlink_registers_user(
    owner_a: tuple[Caller, str], yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    response = launch(owner, business_id)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "fastlink_url",
        "access_token",
        "config_name",
        "expires_in",
        "provider_account_id",
    }
    assert (body["fastlink_url"], body["config_name"], body["expires_in"]) == (
        FASTLINK_URL,
        CONFIG_NAME,
        1800,
    )
    assert body["provider_account_id"] is None
    assert yodlee.registered == [login_name(business_id)]
    assert yodlee.launches == [(login_name(business_id), None)]


def test_fastlink_does_not_register_twice(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    assert launch(owner, business_id).status_code == 200
    assert yconnect(owner, business_id).status_code == 201
    assert launch(owner, business_id).status_code == 200

    assert yodlee.registered == [login_name(business_id)]


def test_fastlink_edit_mode(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    pa = new_provider_account()
    connection_id = yconnect(owner, business_id, pa).json()["id"]

    response = launch(owner, business_id, {"connection_id": connection_id})

    assert response.status_code == 200
    assert response.json()["provider_account_id"] == pa
    assert yodlee.launches[-1] == (login_name(business_id), pa)


def test_fastlink_plaid_connection_409(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    connection_id = connect(owner, business_id).json()["id"]

    response = launch(owner, business_id, {"connection_id": connection_id})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"


def test_fastlink_yodlee_failure_503(
    owner_a: tuple[Caller, str], yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    yodlee.fail["launch"] = YodleeError(http_status=500, error_code="Y902")

    response = launch(owner, business_id)

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == PROVIDER_UNAVAILABLE
    assert "Y902" not in response.text


def test_fastlink_secrets_not_logged(
    owner_a: tuple[Caller, str],
    yodlee: FakeYodlee,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner, business_id = owner_a
    launch(owner, business_id)
    yodlee.fail["launch"] = YodleeError(http_status=500, error_code="Y902")
    launch(owner, business_id)

    captured = capsys.readouterr()
    output = captured.out + captured.err + caplog.text
    for secret in ("yodlee-user-token-SECRET-1", get_settings().yodlee_client_secret):
        if secret:
            assert secret not in output


# S4 - connect


def test_connect_stores_connection(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    pa = new_provider_account()
    response = yconnect(owner, business_id, pa)

    assert response.status_code == 201
    body = response.json()
    assert (body["provider"], body["institution_name"]) == (
        "yodlee",
        "Royal Bank of Canada",
    )
    connections, _ = stored(business_id)
    (connection,) = connections
    assert connection.provider == "yodlee"
    assert connection.provider_item_id == pa
    assert connection.provider_institution_id == "16441"
    assert decrypt_access_token(connection.access_token_ciphertext) == login_name(
        business_id
    )
    assert connection.access_token_ciphertext != login_name(business_id)
    (entry,) = audit_rows(business_id)
    assert entry.target_id == str(connection.id)
    assert entry.details == {"institution_id": "16441", "account_count": 2}
    # The first sync ran after the response.
    assert "transactions" in yodlee.calls
    assert connection.last_synced_at is not None


def test_connect_includes_checking_cad_only(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    accounts = [
        yodlee_account("Chequing CAD"),
        yodlee_account("Savings CAD", subtype="savings"),
        yodlee_account("Chequing USD", iso="USD"),
        yodlee_account("Visa", type="credit", subtype="credit card"),
    ]
    yodlee.accounts_list = lambda: accounts

    yconnect(owner, business_id)

    _, rows = stored(business_id)
    assert {r.name: r.included for r in rows} == {
        "Chequing CAD": True,
        "Savings CAD": False,
        "Chequing USD": False,
        "Visa": False,
    }


def test_connect_duplicate_409(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    assert yconnect(owner, business_id).status_code == 201
    second_pa = new_provider_account()

    second = yconnect(owner, business_id, second_pa)

    assert second.status_code == 409
    connections, _ = stored(business_id)
    assert len(connections) == 1
    assert yodlee.deleted == [(login_name(business_id), second_pa)]


@pytest.mark.parametrize(
    "body",
    [
        {"provider": "yodlee", "public_token": "public-sandbox-1"},
        {"provider": "plaid", "provider_account_id": "pa-1"},
        {"provider": "yodlee"},
    ],
    ids=["yodlee_with_public_token", "plaid_with_provider_account", "neither_field"],
)
def test_connect_field_mismatch_422(
    body: dict[str, str],
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
    yodlee: FakeYodlee,
) -> None:
    owner, business_id = owner_a
    response = connect(owner, business_id, body)

    assert response.status_code == 422
    assert stored(business_id) == ([], [])


def test_connect_failure_cleans_up(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    yodlee.accounts_list = list

    pa = new_provider_account()
    response = yconnect(owner, business_id, pa)

    assert response.status_code == 503
    assert stored(business_id) == ([], [])
    assert yodlee.deleted == [(login_name(business_id), pa)]


def test_link_token_409(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    connection_id = yconnect(owner, business_id).json()["id"]

    response = client.post(
        f"{connections_path(business_id)}/{connection_id}/link-token",
        headers=owner.headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Use the Yodlee window to reconnect this bank."


# S8 - access

NEW_ROUTES = [
    ("GET", providers_path, None),
    ("POST", fastlink_path, {}),
    (
        "POST",
        connections_path,
        {"provider": "yodlee", "provider_account_id": "pa-denied"},
    ),
]


def call(caller: Caller, method: str, path: str, body: dict[str, str] | None) -> Any:
    return TestClient(app).request(method, path, json=body, headers=caller.headers)


@pytest.mark.parametrize("route", NEW_ROUTES, ids=["providers", "fastlink", "connect"])
def test_other_business_denied(
    route: tuple[str, Any, Any],
    owner_a: tuple[Caller, str],
    owner_b: tuple[Caller, str],
    yodlee: FakeYodlee,
) -> None:
    method, path, body = route
    _, business_id = owner_a
    stranger, _ = owner_b

    response = call(stranger, method, path(business_id), body)

    assert response.status_code == 404
    assert yodlee.calls == []


@pytest.mark.parametrize("route", NEW_ROUTES, ids=["providers", "fastlink", "connect"])
def test_non_owner_denied(
    route: tuple[str, Any, Any], owner_a: tuple[Caller, str], yodlee: FakeYodlee
) -> None:
    method, path, body = route
    _, business_id = owner_a
    bookkeeper = add_bookkeeper(business_id)

    response = call(bookkeeper, method, path(business_id), body)

    assert response.status_code == 403
    assert yodlee.calls == []


@pytest.mark.parametrize("route", NEW_ROUTES, ids=["providers", "fastlink", "connect"])
def test_unknown_business_404(
    route: tuple[str, Any, Any], owner_a: tuple[Caller, str], yodlee: FakeYodlee
) -> None:
    method, path, body = route
    owner, _ = owner_a

    response = call(owner, method, path(str(uuid.uuid4())), body)

    assert response.status_code == 404
    assert yodlee.calls == []


# Found by verification round 1


def test_fastlink_other_business_connection_404(
    owner_a: tuple[Caller, str],
    owner_b: tuple[Caller, str],
    fake: FakePlaid,
    yodlee: FakeYodlee,
) -> None:
    owner, business_id = owner_a
    connection_id = yconnect(owner, business_id).json()["id"]
    stranger, stranger_business = owner_b

    response = launch(stranger, stranger_business, {"connection_id": connection_id})

    assert response.status_code == 404
    assert yodlee.launches == []


def test_connect_yodlee_failure_503(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    yodlee.fail["accounts"] = YodleeError(http_status=500, error_code="Y902")

    response = yconnect(owner, business_id)

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert "Y902" not in response.text
    assert stored(business_id) == ([], [])


def test_connect_same_provider_account_409_keeps_it_at_yodlee(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    pa = new_provider_account()
    assert yconnect(owner, business_id, pa).status_code == 201

    again = yconnect(owner, business_id, pa)

    assert again.status_code == 409
    assert yodlee.deleted == []
    assert len(stored(business_id)[0]) == 1


def test_connect_race_on_the_unique_index_keeps_it_at_yodlee(
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
    yodlee: FakeYodlee,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two connects of one provider account both pass the pre-check; the loser must not delete it."""
    owner, business_id = owner_a
    pa = new_provider_account()
    assert yconnect(owner, business_id, pa).status_code == 201
    monkeypatch.setattr(repository, "has_provider_item", lambda *a, **k: False)
    monkeypatch.setattr(repository, "has_institution", lambda *a, **k: False)

    again = yconnect(owner, business_id, pa)

    assert again.status_code == 409
    assert yodlee.deleted == []


def test_connect_another_businesss_provider_account_409(
    owner_a: tuple[Caller, str],
    owner_b: tuple[Caller, str],
    fake: FakePlaid,
    yodlee: FakeYodlee,
) -> None:
    """On a shared sandbox user, business B posting business A's provider account stores nothing."""
    owner, business_id = owner_a
    pa = new_provider_account()
    assert yconnect(owner, business_id, pa).status_code == 201
    stranger, stranger_business = owner_b

    response = yconnect(stranger, stranger_business, pa)

    assert response.status_code == 409
    assert yodlee.deleted == []
    assert stored(stranger_business) == ([], [])


def test_test_login_name_replaces_the_derived_user(
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
    yodlee: FakeYodlee,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Door 2a: the sandbox cannot register users, so one test user serves every business."""
    owner, business_id = owner_a
    monkeypatch.setenv("YODLEE_TEST_LOGIN_NAME", "sbMemTest1")
    get_settings.cache_clear()

    assert launch(owner, business_id).status_code == 200
    assert yconnect(owner, business_id).status_code == 201

    assert yodlee.registered == []
    assert yodlee.launches == [("sbMemTest1", None)]
    (connection,), _ = stored(business_id)
    assert decrypt_access_token(connection.access_token_ciphertext) == "sbMemTest1"


def test_repair_and_disconnect_over_http(
    owner_a: tuple[Caller, str], fake: FakePlaid, yodlee: FakeYodlee
) -> None:
    owner, business_id = owner_a
    connection_id = yconnect(owner, business_id).json()["id"]
    path = f"{connections_path(business_id)}/{connection_id}"

    repaired = client.post(f"{path}/repair", headers=owner.headers)
    assert repaired.status_code == 200
    assert repaired.json()["provider"] == "yodlee"

    yodlee.needs_login = True
    still = client.post(f"{path}/repair", headers=owner.headers)
    assert still.status_code == 409
    yodlee.needs_login = False

    yodlee.fail["delete"] = YodleeError(http_status=500, error_code="Y902")
    failed = client.delete(path, headers=owner.headers)
    assert failed.status_code == 503
    assert failed.headers["content-type"] == "application/problem+json"
    assert len(stored(business_id)[0]) == 1

    del yodlee.fail["delete"]
    gone = client.delete(path, headers=owner.headers)
    assert gone.status_code == 204
    assert stored(business_id)[0] == []
