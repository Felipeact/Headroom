"""Spec 12: connect a bank. The fake Plaid client stands in for Plaid; nothing here calls it."""

import json
import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
import sentry_sdk
from cryptography.fernet import Fernet, MultiFernet
from fastapi.testclient import TestClient
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport
from sentry_sdk.types import Event
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import monitoring
from app.audit import AuditLog
from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync import repository, service
from app.modules.bank_sync.models import BankAccount, BankConnection
from app.modules.bank_sync.plaid import (
    ExchangedItem,
    ItemAccounts,
    LinkToken,
    LinkTokenRequest,
    PlaidAccount,
    PlaidError,
    get_plaid_client,
)
from app.modules.bank_sync.tokens import decrypt_access_token
from app.settings import get_settings
from tests.test_businesses import (
    BAYVIEW,
    HARBOR,
    Caller,
    _owner,
    _routes,
    business_routes_missing_member,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

PUBLIC_TOKEN = "public-sandbox-1"
INSTITUTION_ID = "ins_42"
INSTITUTION_NAME = "TD Canada Trust"
LINK_EXPIRATION = datetime(2026, 10, 4, 16, 0, tzinfo=UTC)
PROVIDER_UNAVAILABLE = "We couldn't reach our bank connection provider. Try again."
CONNECTION_KEYS = {"id", "institution_name", "created_at", "accounts"}
ACCOUNT_KEYS = {"id", "name", "type", "mask", "currency", "balance_cents"}


def plaid_account(
    name: str,
    *,
    type: str = "depository",
    subtype: str | None = "checking",
    mask: str | None = "0001",
    current: float | None = 100.0,
    iso: str | None = "CAD",
    unofficial: str | None = None,
) -> PlaidAccount:
    return PlaidAccount(
        account_id=f"acc-{uuid.uuid4().hex}",
        name=name,
        type=type,
        subtype=subtype,
        mask=mask,
        current=current,
        iso_currency_code=iso,
        unofficial_currency_code=unofficial,
    )


def default_accounts() -> list[PlaidAccount]:
    return [
        plaid_account("Savings", subtype="savings", mask="0002", current=20000.0),
        plaid_account("Chequing", mask="0001", current=1234.56),
        plaid_account(
            "Visa", type="credit", subtype="credit card", mask="0003", current=812.34
        ),
    ]


def plaid_error(error_type: str = "API_ERROR") -> PlaidError:
    return PlaidError(
        error_type=error_type, error_code="INTERNAL_SERVER_ERROR", request_id="req-1"
    )


class FakePlaid:
    """Behaves like Plaid for the calls spec 12 makes, and records them."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.link_requests: list[LinkTokenRequest] = []
        self.access_tokens: list[str] = []
        self.removed: list[str] = []
        self.fail: dict[str, PlaidError] = {}
        self.institution_id = INSTITUTION_ID
        self.accounts: Callable[[], list[PlaidAccount]] = default_accounts
        self._lock = threading.Lock()

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if name in self.fail:
            raise self.fail[name]

    def create_link_token(self, request: LinkTokenRequest) -> LinkToken:
        self._call("link_token")
        self.link_requests.append(request)
        return LinkToken(link_token="link-sandbox-123", expiration=LINK_EXPIRATION)

    def exchange_public_token(self, public_token: str) -> ExchangedItem:
        self._call("exchange")
        with self._lock:
            token = f"access-sandbox-secret-{len(self.access_tokens) + 1}"
            self.access_tokens.append(token)
        return ExchangedItem(item_id=f"item-{uuid.uuid4().hex}", access_token=token)

    def get_accounts(self, access_token: str) -> ItemAccounts:
        self._call("accounts")
        return ItemAccounts(
            institution_id=self.institution_id, accounts=self.accounts()
        )

    def get_institution_name(self, institution_id: str) -> str:
        self._call("institution")
        return INSTITUTION_NAME

    def remove_item(self, access_token: str) -> None:
        self.calls.append("remove")
        self.removed.append(access_token)
        if "remove" in self.fail:
            raise self.fail["remove"]


@pytest.fixture
def fake() -> Iterator[FakePlaid]:
    plaid = FakePlaid()
    app.dependency_overrides[get_plaid_client] = lambda: plaid
    yield plaid
    app.dependency_overrides.pop(get_plaid_client, None)


@pytest.fixture
def owner_a() -> tuple[Caller, str]:
    return _owner(HARBOR)


@pytest.fixture
def owner_b() -> tuple[Caller, str]:
    return _owner(BAYVIEW)


def link_path(business_id: str) -> str:
    return f"/v1/businesses/{business_id}/bank/link-token"


def connections_path(business_id: str) -> str:
    return f"/v1/businesses/{business_id}/bank/connections"


def connect(
    caller: Caller,
    business_id: str,
    body: Any = None,
    *,
    using: TestClient = client,
) -> Any:
    return using.post(
        connections_path(business_id),
        json={"public_token": PUBLIC_TOKEN} if body is None else body,
        headers=caller.headers,
    )


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


def audit_rows(business_id: str) -> list[AuditLog]:
    with get_sessionmaker()() as session:
        rows = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.business_id == uuid.UUID(business_id),
                    AuditLog.action == "bank_connection.created",
                )
            )
        )
        session.expunge_all()
    return rows


# S1 - link token


def test_link_token_returned(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    response = client.post(link_path(business_id), headers=owner.headers)

    assert response.status_code == 200
    assert response.json() == {
        "link_token": "link-sandbox-123",
        "expiration": "2026-10-04T16:00:00Z",
    }


def test_link_token_request_values(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    client.post(link_path(business_id), headers=owner.headers)

    assert fake.link_requests == [
        LinkTokenRequest(
            client_user_id=str(owner.id),
            client_name="Headroom",
            language="en",
            country_codes=("CA",),
            products=("transactions",),
            days_requested=730,
        )
    ]


@pytest.mark.parametrize(
    "error",
    [
        plaid_error(),
        PlaidError(
            error_type="NETWORK", error_code="ReadTimeoutError", request_id=None
        ),
    ],
    ids=["plaid_error", "timeout"],
)
def test_link_token_plaid_fails(
    error: PlaidError, owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    fake.fail["link_token"] = error

    response = client.post(link_path(business_id), headers=owner.headers)

    assert response.status_code == 502
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == PROVIDER_UNAVAILABLE


# S2 - storing a connection


def test_connect_returns_connection(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    response = connect(owner, business_id)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == CONNECTION_KEYS
    assert body["institution_name"] == INSTITUTION_NAME
    assert [set(a) for a in body["accounts"]] == [ACCOUNT_KEYS] * 3
    assert [a["name"] for a in body["accounts"]] == ["Chequing", "Savings", "Visa"]


def test_connect_stores_rows(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    accounts = default_accounts()
    fake.accounts = lambda: accounts
    body = connect(owner, business_id).json()

    connections, rows = stored(business_id)
    assert len(connections) == 1
    connection = connections[0]
    assert str(connection.id) == body["id"]
    assert connection.plaid_institution_id == INSTITUTION_ID
    assert connection.plaid_item_id.startswith("item-")
    assert len(rows) == 3
    assert {r.connection_id for r in rows} == {connection.id}
    assert {r.plaid_account_id for r in rows} == {a.account_id for a in accounts}


@pytest.mark.parametrize(
    ("plaid_type", "subtype", "expected"),
    [
        ("depository", "checking", "checking"),
        ("depository", "savings", "savings"),
        ("credit", "credit card", "credit_card"),
        ("loan", "line of credit", "line_of_credit"),
        ("credit", "line of credit", "line_of_credit"),
        ("depository", "money market", "other"),
        ("investment", "brokerage", "other"),
        ("loan", "mortgage", "other"),
        ("other", None, "other"),
    ],
)
def test_account_type_mapping(
    plaid_type: str,
    subtype: str | None,
    expected: str,
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
) -> None:
    owner, business_id = owner_a
    fake.accounts = lambda: [plaid_account("One", type=plaid_type, subtype=subtype)]

    body = connect(owner, business_id).json()

    assert body["accounts"][0]["type"] == expected
    assert stored(business_id)[1][0].type == expected


@pytest.mark.parametrize(
    ("account", "field", "expected"),
    [
        (plaid_account("A", mask="0001"), "mask", "0001"),
        (plaid_account("A", mask=None), "mask", None),
        (plaid_account("A", iso="CAD"), "currency", "CAD"),
        (plaid_account("A", iso=None, unofficial="USDC"), "currency", "USDC"),
        (plaid_account("A", current=1234.565), "balance_cents", 123456),
        (plaid_account("A", current=10.005), "balance_cents", 1000),
        (plaid_account("A", current=-50.0), "balance_cents", -5000),
        (plaid_account("A", current=8000.0), "balance_cents", 800000),
        (plaid_account("A", current=None), "balance_cents", None),
    ],
)
def test_account_field_mapping(
    account: PlaidAccount,
    field: str,
    expected: object,
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
) -> None:
    owner, business_id = owner_a
    fake.accounts = lambda: [account]

    body = connect(owner, business_id).json()

    assert body["accounts"][0][field] == expected
    assert getattr(stored(business_id)[1][0], field) == expected


def test_token_encrypted(
    owner_a: tuple[Caller, str], fake: FakePlaid, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, business_id = owner_a
    connect(owner, business_id)
    ciphertext = stored(business_id)[0][0].access_token_ciphertext

    assert ciphertext != "access-sandbox-secret-1"
    assert "access-sandbox-secret-1" not in ciphertext
    keys = get_settings().token_encryption_keys
    assert (
        MultiFernet([Fernet(k) for k in keys]).decrypt(ciphertext.encode()).decode()
        == "access-sandbox-secret-1"
    )

    # Rotation: a new key goes first; values under the old key still decrypt.
    old, new = keys[0], Fernet.generate_key().decode()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEYS", f"{new},{old}")
    get_settings.cache_clear()
    try:
        caller_c, business_c = _owner({**HARBOR, "name": "Rotation Co"})
        connect(caller_c, business_c)
        new_ciphertext = stored(business_c)[0][0].access_token_ciphertext
        assert (
            Fernet(new).decrypt(new_ciphertext.encode()).decode()
            == fake.access_tokens[-1]
        )
        assert decrypt_access_token(ciphertext) == "access-sandbox-secret-1"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_connect_audited(
    owner_a: tuple[Caller, str],
    owner_b: tuple[Caller, str],
    fake: FakePlaid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, business_id = owner_a
    body = connect(owner, business_id).json()

    rows = audit_rows(business_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == str(owner.id)
    assert row.target_type == "bank_connection"
    assert row.target_id == body["id"]
    assert row.details == {"institution_id": INSTITUTION_ID, "account_count": 3}

    other, other_business = owner_b

    def broken(*_: object, **__: object) -> None:
        raise SQLAlchemyError("database write failed")

    monkeypatch.setattr(repository, "insert_accounts", broken)
    failing = TestClient(app, raise_server_exceptions=False)
    assert connect(other, other_business, using=failing).status_code == 500
    assert audit_rows(other_business) == []


def test_same_bank_twice_conflicts(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    first = connect(owner, business_id).json()

    second = connect(owner, business_id)

    assert second.status_code == 409
    assert second.headers["content-type"] == "application/problem+json"
    assert second.json()["detail"] == "This bank is already connected."
    assert fake.removed == ["access-sandbox-secret-2"]
    connections, rows = stored(business_id)
    assert [str(c.id) for c in connections] == [first["id"]]
    assert {str(r.id) for r in rows} == {a["id"] for a in first["accounts"]}


def test_concurrent_connects(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    barrier = threading.Barrier(2)
    created: list[service.ConnectionView] = []
    duplicates: list[service.DuplicateBankError] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            with get_sessionmaker()() as session:
                barrier.wait()
                created.append(
                    service.connect_bank(
                        session,
                        fake,
                        business_id=uuid.UUID(business_id),
                        user_id=owner.id,
                        public_token=PUBLIC_TOKEN,
                    )
                )
        except service.DuplicateBankError as exc:
            duplicates.append(exc)
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len(created) == 1
    assert len(duplicates) == 1
    connections, _ = stored(business_id)
    assert len(connections) == 1
    winner = decrypt_access_token(connections[0].access_token_ciphertext)
    assert len(fake.removed) == 1
    assert fake.removed[0] in fake.access_tokens
    assert fake.removed[0] != winner


def test_invalid_public_token(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    fake.fail["exchange"] = plaid_error("INVALID_INPUT")

    response = connect(owner, business_id)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "We couldn't finish connecting your bank. Try again."
    )
    assert stored(business_id) == ([], [])
    assert fake.removed == []


@pytest.mark.parametrize(
    ("failing", "error", "removed"),
    [
        ("exchange", plaid_error(), []),
        ("accounts", plaid_error(), ["access-sandbox-secret-1"]),
        ("institution", plaid_error(), ["access-sandbox-secret-1"]),
        (
            "accounts",
            PlaidError(
                error_type="NETWORK", error_code="ReadTimeoutError", request_id=None
            ),
            ["access-sandbox-secret-1"],
        ),
    ],
    ids=["exchange", "accounts", "institution", "accounts_timeout"],
)
def test_plaid_failures(
    failing: str,
    error: PlaidError,
    removed: list[str],
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
) -> None:
    owner, business_id = owner_a
    fake.fail[failing] = error

    response = connect(owner, business_id)

    assert response.status_code == 502
    assert response.json()["detail"] == PROVIDER_UNAVAILABLE
    assert stored(business_id) == ([], [])
    assert fake.removed == removed


@pytest.mark.parametrize("target", ["insert_accounts", "audit"])
def test_database_failure_removes_item(
    target: str,
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, business_id = owner_a

    def broken(*_: object, **__: object) -> None:
        raise SQLAlchemyError("write failed")

    if target == "audit":
        monkeypatch.setattr(service.audit, "record", broken)
    else:
        monkeypatch.setattr(repository, "insert_accounts", broken)
    failing = TestClient(app, raise_server_exceptions=False)

    response = connect(owner, business_id, using=failing)

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "An unexpected error occurred."
    assert stored(business_id) == ([], [])
    assert fake.removed == ["access-sandbox-secret-1"]


def test_orphaned_item_logged(
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner, business_id = owner_a
    fake.fail["accounts"] = plaid_error()
    fake.fail["remove"] = plaid_error()
    configure_logging()
    capsys.readouterr()

    response = connect(owner, business_id)

    assert response.status_code == 502
    assert response.json()["detail"] == PROVIDER_UNAVAILABLE
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    orphaned = [line for line in lines if line["event"] == "bank_connection.orphaned"]
    assert len(orphaned) == 1
    assert orphaned[0]["level"] == "error"
    assert orphaned[0]["business_id"] == business_id
    assert orphaned[0]["plaid_item_id"].startswith("item-")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"public_token": ""},
        {"public_token": None},
        {"public_token": PUBLIC_TOKEN, "extra": 1},
    ],
    ids=["missing", "empty", "null", "extra_field"],
)
def test_connect_body_validation(
    body: dict[str, Any], owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a

    response = connect(owner, business_id, body)

    assert response.status_code == 422
    assert response.json()["errors"]
    assert fake.calls == []
    assert stored(business_id) == ([], [])


def test_database_constraints(owner_a: tuple[Caller, str]) -> None:
    _, business_id = owner_a
    bid = uuid.UUID(business_id)

    def connection(item: str, institution: str) -> BankConnection:
        return BankConnection(
            business_id=bid,
            plaid_item_id=item,
            plaid_institution_id=institution,
            institution_name="Bank",
            access_token_ciphertext="x",
        )

    def account(connection_id: uuid.UUID, plaid_id: str, type: str) -> BankAccount:
        return BankAccount(
            business_id=bid,
            connection_id=connection_id,
            plaid_account_id=plaid_id,
            name="A",
            type=type,
            currency="CAD",
        )

    with get_sessionmaker()() as session:
        base = connection("item-base", "ins_base")
        session.add(base)
        session.flush()
        session.add(account(base.id, "acc-base", "checking"))
        session.commit()
        base_id = base.id

    cases: list[Callable[[], object]] = [
        lambda: account(base_id, "acc-loan", "loan"),
        lambda: connection("item-base", "ins_other"),
        lambda: connection("item-other", "ins_base"),
        lambda: account(base_id, "acc-base", "savings"),
        lambda: account(uuid.uuid4(), "acc-orphan", "checking"),
    ]
    for make in cases:
        with get_sessionmaker()() as session:
            session.add(make())
            with pytest.raises(IntegrityError):
                session.flush()


# S3 - only the owner, only their business


def test_non_member_gets_404(
    owner_a: tuple[Caller, str], owner_b: tuple[Caller, str], fake: FakePlaid
) -> None:
    _, business_a = owner_a
    stranger, _ = owner_b

    for path in (link_path, connections_path):
        foreign = client.post(
            path(business_a),
            json={"public_token": PUBLIC_TOKEN},
            headers=stranger.headers,
        )
        missing = client.post(
            path(str(uuid.uuid4())),
            json={"public_token": PUBLIC_TOKEN},
            headers=stranger.headers,
        )
        assert foreign.status_code == 404
        assert foreign.json()["detail"] == "Business not found."
        assert missing.status_code == 404
        assert {k: v for k, v in foreign.json().items() if k != "instance"} == {
            k: v for k, v in missing.json().items() if k != "instance"
        }
    assert fake.calls == []


def test_non_owner_gets_403(
    owner_a: tuple[Caller, str], fake: FakePlaid, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, business_id = owner_a
    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="viewer"),
    )

    for path in (link_path, connections_path):
        response = client.post(
            path(business_id),
            json={"public_token": PUBLIC_TOKEN},
            headers=owner.headers,
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "You don't have permission to do this."
    assert fake.calls == []


def test_bank_routes_require_member() -> None:
    walked = {
        (method, route.path)
        for route in _routes(app.routes)
        if "{business_id}" in route.path
        for method in route.methods
    }
    assert ("POST", "/businesses/{business_id}/bank/link-token") in walked
    assert ("POST", "/businesses/{business_id}/bank/connections") in walked
    assert business_routes_missing_member(app) == []


def test_malformed_business_id(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, _ = owner_a
    for path in (link_path, connections_path):
        response = client.post(
            path("not-a-uuid"),
            json={"public_token": PUBLIC_TOKEN},
            headers=owner.headers,
        )
        assert response.status_code == 422
        assert any(e["loc"][-1] == "business_id" for e in response.json()["errors"])
    assert fake.calls == []


# S4 - the access token never leaks


def every_path(
    using: TestClient,
    fake: FakePlaid,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[Any], str]:
    """Walk success, duplicate, 400, 502, orphan, 500, 404, 403 and 422.

    Returns the responses and the business whose connection was stored.
    """
    responses: list[Any] = []
    owner, business_id = _owner(HARBOR)
    responses.append(using.post(link_path(business_id), headers=owner.headers))
    responses.append(connect(owner, business_id, using=using))  # 201
    responses.append(connect(owner, business_id, using=using))  # 409

    def fresh() -> tuple[Caller, str]:
        return _owner({**HARBOR, "name": f"Path {uuid.uuid4().hex[:6]}"})

    for failing, error_type in (
        ("exchange", "INVALID_INPUT"),
        ("exchange", "API_ERROR"),
        ("accounts", "API_ERROR"),
        ("institution", "API_ERROR"),
    ):
        caller, bid = fresh()
        fake.fail = {failing: plaid_error(error_type)}
        responses.append(connect(caller, bid, using=using))
    caller, bid = fresh()
    fake.fail = {"accounts": plaid_error(), "remove": plaid_error()}
    responses.append(connect(caller, bid, using=using))
    fake.fail = {}

    with monkeypatch.context() as patch:

        def broken(*_: object, **__: object) -> None:
            raise SQLAlchemyError("write failed")

        patch.setattr(repository, "insert_accounts", broken)
        caller, bid = fresh()
        responses.append(connect(caller, bid, using=using))  # 500

    stranger = Caller()
    responses.append(connect(stranger, business_id, using=using))  # 404
    with monkeypatch.context() as patch:
        patch.setattr(
            accounts_service,
            "get_membership",
            lambda *_, **__: SimpleNamespace(role="viewer"),
        )
        responses.append(connect(owner, business_id, using=using))  # 403
    responses.append(connect(owner, business_id, {"public_token": ""}, using=using))
    return responses, business_id


def secrets(fake: FakePlaid) -> list[str]:
    return [*fake.access_tokens, PUBLIC_TOKEN]


def test_no_token_in_responses(
    fake: FakePlaid, monkeypatch: pytest.MonkeyPatch
) -> None:
    using = TestClient(app, raise_server_exceptions=False)
    responses, business_id = every_path(using, fake, monkeypatch)
    ciphertexts = [c.access_token_ciphertext for c in stored(business_id)[0]]
    assert len(ciphertexts) == 1

    statuses = sorted({r.status_code for r in responses})
    assert statuses == [200, 201, 400, 403, 404, 409, 422, 500, 502]
    assert fake.access_tokens
    for response in responses:
        for value in [*secrets(fake), *ciphertexts]:
            assert value not in response.text


class FakeTransport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[Event] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        for item in envelope.items:
            event = item.get_event()
            if event is not None:
                self.events.append(event)


def test_no_token_in_logs_or_sentry(
    fake: FakePlaid,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = FakeTransport()
    real_init: Callable[..., Any] = sentry_sdk.init

    def init_with_fake_transport(*args: Any, **kwargs: Any) -> Any:
        return real_init(*args, transport=transport, **kwargs)

    monkeypatch.setattr(monitoring.sentry_sdk, "init", init_with_fake_transport)
    monkeypatch.setenv("SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    get_settings.cache_clear()
    try:
        with TestClient(app, raise_server_exceptions=False) as using:
            capsys.readouterr()
            every_path(using, fake, monkeypatch)
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_global_scope().set_client(None)
        sentry_sdk.get_isolation_scope().clear()
        get_settings.cache_clear()

    output = capsys.readouterr()
    logs = output.out + output.err
    events = json.dumps(transport.events, default=str)
    assert transport.events, "the 500 and 502 paths report to Sentry"
    assert "bank_connection.orphaned" in logs
    # Lists, not `not in` on the whole text: a failure names the leak without a huge diff.
    assert [v for v in secrets(fake) if v in logs] == []
    assert [v for v in secrets(fake) if v in events] == []


def test_connect_logged(
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner, business_id = owner_a
    configure_logging()
    capsys.readouterr()

    body = connect(owner, business_id).json()

    out = capsys.readouterr().out
    lines = [json.loads(line) for line in out.splitlines()]
    created = [line for line in lines if line["event"] == "bank_connection.created"]
    assert len(created) == 1
    assert created[0]["business_id"] == business_id
    assert created[0]["connection_id"] == body["id"]
    assert created[0]["institution_id"] == INSTITUTION_ID
    assert created[0]["account_count"] == 3
    for value in ("Chequing", "Savings", "Visa", "0001", "0002", "0003"):
        assert value not in out
    for value in ("1234.56", "123456", "20000", "812.34", "81234"):
        assert value not in out
