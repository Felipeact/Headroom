"""Spec 17: bank connection settings. A fake Plaid client stands in for Plaid."""

import json
import threading
import time
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app import events
from app.audit import AuditLog
from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync import repository, service, webhooks
from app.modules.bank_sync.models import BankAccount, BankConnection, BankTransaction
from app.modules.bank_sync.plaid import PlaidAccount, PlaidError, get_plaid_client
from app.modules.bank_sync.tokens import encrypt_access_token
from app.settings import get_settings
from tests import webhook_signing as signing
from tests.test_bank_connect import plaid_account
from tests.test_businesses import BAYVIEW, HARBOR, Caller, _owner
from tests.test_transaction_sync import (
    ACCESS_TOKEN,
    Connected,
    SyncFake,
    _run,
    checking,
    page,
    snapshot,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

NOT_FOUND = "Bank connection not found."
STILL_LOGIN = "Your bank still needs you to log in."
PROVIDER_UNAVAILABLE = "We couldn't reach our bank connection provider. Try again."
CONNECTION_KEYS = {
    "id",
    "institution_name",
    "created_at",
    "accounts",
    "status",
    "last_synced_at",
}
SYNCED_AT = datetime(2026, 10, 6, 6, 4, tzinfo=UTC)
ROUTES = [("POST", "/link-token"), ("POST", "/repair"), ("DELETE", "")]
ROUTE_IDS = ["link-token", "repair", "disconnect"]


def login_error() -> PlaidError:
    return PlaidError(
        error_type="ITEM_ERROR", error_code="ITEM_LOGIN_REQUIRED", request_id="req-l"
    )


def other_error() -> PlaidError:
    return PlaidError(
        error_type="API_ERROR", error_code="INTERNAL_SERVER_ERROR", request_id="req-o"
    )


def savings() -> PlaidAccount:
    return plaid_account("Reserve", subtype="savings", mask="9025", current=34300.0)


def stored(
    business_id: str,
    accounts: Sequence[PlaidAccount],
    *,
    token: str = ACCESS_TOKEN,
    institution_name: str = "TD Canada Trust",
) -> Connected:
    """A stored connection with these accounts, as spec 12 leaves it."""
    bid = uuid.UUID(business_id)
    item_id = f"item-{uuid.uuid4().hex}"
    with get_sessionmaker()() as session:
        connection = repository.insert_connection(
            session,
            business_id=bid,
            provider_item_id=item_id,
            provider_institution_id=f"ins_{uuid.uuid4().hex[:8]}",
            institution_name=institution_name,
            access_token_ciphertext=encrypt_access_token(token),
        )
        repository.insert_accounts(
            session,
            [
                service._account(a, business_id=bid, connection_id=connection.id)
                for a in accounts
            ],
        )
        session.commit()
        return Connected(bid, connection.id, item_id)


def path(business_id: Any, connection_id: Any, suffix: str = "") -> str:
    return f"/v1/businesses/{business_id}/bank/connections/{connection_id}{suffix}"


def call(caller: Caller, method: str, url: str) -> Any:
    return client.request(method, url, headers=caller.headers)


def row(c: Connected) -> BankConnection | None:
    with get_sessionmaker()() as session:
        found = session.get(BankConnection, c.connection_id)
        session.expunge_all()
    return found


def set_state(c: Connected, **values: Any) -> None:
    with get_sessionmaker()() as session:
        session.execute(
            update(BankConnection)
            .where(BankConnection.id == c.connection_id)
            .values(**values)
        )
        session.commit()


def sync(fake: SyncFake, c: Connected, now: datetime | None = None) -> Any:
    with get_sessionmaker()() as session:
        return service.sync_connection(
            session,
            fake,
            business_id=c.business_id,
            connection_id=c.connection_id,
            now=now,
        )


def listed(caller: Caller, c: Connected) -> dict[str, Any]:
    response = client.get(
        f"/v1/businesses/{c.business_id}/bank/connections", headers=caller.headers
    )
    assert response.status_code == 200, response.text
    found: dict[str, Any] = next(
        item for item in response.json()["items"] if item["id"] == str(c.connection_id)
    )
    return found


def counts(c: Connected) -> tuple[int, int, int]:
    """(connections, accounts, transactions) stored for the connection."""
    with get_sessionmaker()() as session:
        account_ids = select(BankAccount.id).where(
            BankAccount.connection_id == c.connection_id
        )
        return (
            session.scalar(
                select(func.count())
                .select_from(BankConnection)
                .where(BankConnection.id == c.connection_id)
            )
            or 0,
            session.scalar(
                select(func.count())
                .select_from(BankAccount)
                .where(BankAccount.connection_id == c.connection_id)
            )
            or 0,
            session.scalar(
                select(func.count())
                .select_from(BankTransaction)
                .where(BankTransaction.account_id.in_(account_ids))
            )
            or 0,
        )


def audits(business_id: uuid.UUID) -> list[AuditLog]:
    with get_sessionmaker()() as session:
        found = list(
            session.scalars(
                select(AuditLog)
                .where(AuditLog.business_id == business_id)
                .order_by(AuditLog.id)
            )
        )
        session.expunge_all()
    return found


def primaries(business_id: uuid.UUID) -> list[str]:
    with get_sessionmaker()() as session:
        return list(
            session.scalars(
                select(BankAccount.name).where(
                    BankAccount.business_id == business_id, BankAccount.is_primary
                )
            )
        )


def make_primary(business_id: uuid.UUID, name: str) -> None:
    with get_sessionmaker()() as session:
        session.execute(
            update(BankAccount)
            .where(BankAccount.business_id == business_id)
            .values(is_primary=False)
        )
        session.execute(
            update(BankAccount)
            .where(BankAccount.business_id == business_id, BankAccount.name == name)
            .values(is_primary=True, included=True)
        )
        session.commit()


def log_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


@pytest.fixture(autouse=True)
def _unique_transaction_ids() -> None:
    # Plaid transaction IDs are unique across businesses; `tx` suffixes them per test.
    _run["id"] = uuid.uuid4().hex[:12]


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
    return _owner({**HARBOR, "name": f"Settings {uuid.uuid4().hex[:6]}"})


@pytest.fixture
def other() -> tuple[Caller, str]:
    return _owner({**BAYVIEW, "name": f"Other {uuid.uuid4().hex[:6]}"})


@pytest.fixture
def published() -> Iterator[list[events.Event]]:
    seen: list[events.Event] = []
    events.subscribe("transactions.synced", seen.append)
    yield seen
    events.unsubscribe("transactions.synced", seen.append)


# S1 - the owner sees every bank and its sync status


def test_sync_success_records_time(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C1."""
    c = stored(owner[1], [checking()])
    set_state(c, login_required=True)
    assert (found := row(c)) is not None and found.last_synced_at is None

    sync(fake, c, now=SYNCED_AT)

    after = row(c)
    assert after is not None
    assert after.last_synced_at == SYNCED_AT
    assert after.login_required is False


@pytest.mark.parametrize(
    ("login_required", "failed_nights", "synced_at", "status"),
    [
        (True, 3, SYNCED_AT, "login_required"),
        (True, 0, None, "login_required"),
        (False, 3, SYNCED_AT, "sync_failing"),
        (False, 2, SYNCED_AT, "synced"),
        (False, 0, None, "syncing"),
    ],
)
def test_status_precedence(
    owner: tuple[Caller, str],
    login_required: bool,
    failed_nights: int,
    synced_at: datetime | None,
    status: str,
) -> None:
    """C2."""
    caller, business_id = owner
    c = stored(business_id, [checking()])
    set_state(
        c,
        login_required=login_required,
        failed_nights=failed_nights,
        last_synced_at=synced_at,
    )

    item = listed(caller, c)

    assert set(item) == CONNECTION_KEYS
    assert item["status"] == status
    if synced_at is None:
        assert item["last_synced_at"] is None
    else:
        assert datetime.fromisoformat(item["last_synced_at"]) == synced_at


# S3 - a bank that needs a login shows a banner and can be repaired


@pytest.mark.parametrize("path_", ["direct", "background"])
def test_login_error_recorded(
    fake: SyncFake, owner: tuple[Caller, str], path_: str
) -> None:
    """C19."""
    chq = checking()
    c = stored(owner[1], [chq])
    fake.script = [page([chq], added=[tx("t1", chq, 25.0)], cursor="c1")]
    sync(fake, c, now=SYNCED_AT)
    before = snapshot(c.business_id)
    fake.script = [login_error()]

    if path_ == "direct":
        with pytest.raises(PlaidError):
            sync(fake, c)
    else:
        assert (
            service.sync_in_background(
                fake, business_id=c.business_id, connection_id=c.connection_id
            )
            is None
        )

    after = row(c)
    assert after is not None
    assert after.login_required is True
    assert after.last_synced_at == SYNCED_AT
    assert snapshot(c.business_id) == before


def test_other_error_not_login(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C21."""
    c = stored(owner[1], [checking()])
    fake.script = [other_error()]

    with pytest.raises(PlaidError):
        sync(fake, c)

    after = row(c)
    assert after is not None and after.login_required is False


@pytest.mark.parametrize(
    ("login_required", "failed_nights", "expected"),
    [(True, 0, True), (False, 3, True), (True, 3, True), (False, 2, False)],
)
def test_needs_attention_table(
    owner: tuple[Caller, str],
    login_required: bool,
    failed_nights: int,
    expected: bool,
) -> None:
    """C25."""
    c = stored(owner[1], [checking()])
    set_state(c, login_required=login_required, failed_nights=failed_nights)

    with get_sessionmaker()() as session:
        result = service.needs_attention(
            session, business_id=c.business_id, connection_id=c.connection_id
        )

    assert result is expected


def test_update_link_token(
    fake: SyncFake, owner: tuple[Caller, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C29."""
    caller, business_id = owner
    c = stored(business_id, [checking()])
    url = "https://example.test/v1/webhooks/plaid"
    monkeypatch.setenv("PLAID_WEBHOOK_URL", url)
    get_settings.cache_clear()
    try:
        response = call(
            caller, "POST", path(business_id, c.connection_id, "/link-token")
        )
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()

    assert response.status_code == 200, response.text
    assert set(response.json()) == {"link_token", "expiration"}
    assert response.json()["link_token"] == "link-sandbox-123"
    assert len(fake.link_requests) == 1
    request = fake.link_requests[0]
    assert request.access_token == ACCESS_TOKEN
    assert request.products == ()
    assert request.webhook == url


def test_repair_succeeds(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C31."""
    caller, business_id = owner
    c = stored(business_id, [checking()])
    set_state(c, login_required=True)

    response = call(caller, "POST", path(business_id, c.connection_id, "/repair"))

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == CONNECTION_KEYS
    assert body["id"] == str(c.connection_id)
    assert body["status"] == "synced"
    assert body["last_synced_at"] is not None


def test_repair_still_login(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C32."""
    caller, business_id = owner
    c = stored(business_id, [checking()])
    set_state(c, login_required=True)
    fake.script = [login_error()]

    response = call(caller, "POST", path(business_id, c.connection_id, "/repair"))

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == STILL_LOGIN
    after = row(c)
    assert after is not None and after.login_required is True


@pytest.mark.parametrize("route", ["link-token", "repair"])
def test_plaid_failure_502(
    fake: SyncFake, owner: tuple[Caller, str], route: str
) -> None:
    """C33."""
    caller, business_id = owner
    c = stored(business_id, [checking()])
    if route == "link-token":
        fake.fail["link_token"] = other_error()
    else:
        fake.script = [other_error()]

    response = call(caller, "POST", path(business_id, c.connection_id, f"/{route}"))

    assert response.status_code == 502
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == PROVIDER_UNAVAILABLE


# S4 - the owner disconnects a bank


def _with_transactions(fake: SyncFake, business_id: str) -> Connected:
    chq, sav = checking(), savings()
    c = stored(business_id, [chq, sav])
    # A prefix per connection: one test may set up two of these.
    p = uuid.uuid4().hex[:6]
    fake.script = [
        page(
            [chq, sav],
            added=[
                tx(f"{p}-1", chq, 10.0),
                tx(f"{p}-2", chq, 20.0),
                tx(f"{p}-3", sav, -30.0),
            ],
        )
    ]
    sync(fake, c)
    assert counts(c) == (1, 2, 3)
    return c


def test_disconnect_deletes(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C37."""
    caller, business_id = owner
    c = _with_transactions(fake, business_id)

    response = call(caller, "DELETE", path(business_id, c.connection_id))

    assert response.status_code == 204
    assert response.content == b""
    assert fake.removed == [ACCESS_TOKEN]
    assert fake.calls.count("remove") == 1
    assert counts(c) == (0, 0, 0)


def test_disconnect_item_not_found(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C38."""
    caller, business_id = owner
    c = _with_transactions(fake, business_id)
    fake.fail["remove"] = PlaidError(
        error_type="ITEM_ERROR", error_code="ITEM_NOT_FOUND", request_id="req-nf"
    )

    response = call(caller, "DELETE", path(business_id, c.connection_id))

    assert response.status_code == 204
    assert counts(c) == (0, 0, 0)


def test_disconnect_plaid_fails(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C39."""
    caller, business_id = owner
    c = _with_transactions(fake, business_id)
    fake.fail["remove"] = other_error()
    before = (snapshot(c.business_id), [a.id for a in audits(c.business_id)])

    response = call(caller, "DELETE", path(business_id, c.connection_id))

    assert response.status_code == 502
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == PROVIDER_UNAVAILABLE
    assert counts(c) == (1, 2, 3)
    assert (snapshot(c.business_id), [a.id for a in audits(c.business_id)]) == before


def test_disconnect_audited(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C41."""
    caller, business_id = owner
    c = _with_transactions(fake, business_id)
    with get_sessionmaker()() as session:
        connection = session.get(BankConnection, c.connection_id)
        assert connection is not None
        institution_id = connection.provider_institution_id
    before = {a.id for a in audits(c.business_id)}

    response = call(caller, "DELETE", path(business_id, c.connection_id))

    assert response.status_code == 204
    new = [a for a in audits(c.business_id) if a.id not in before]
    assert len(new) == 1
    entry = new[0]
    assert entry.action == "bank_connection.disconnected"
    assert entry.actor_user_id == str(caller.id)
    assert entry.target_type == "bank_connection"
    assert entry.target_id == str(c.connection_id)
    assert entry.details == {"institution_id": institution_id, "account_count": 2}


@pytest.mark.parametrize("case", ["reassigned", "none_left", "untouched"])
def test_disconnect_primary(
    fake: SyncFake, owner: tuple[Caller, str], case: str
) -> None:
    """C42."""
    caller, business_id = owner
    bid = uuid.UUID(business_id)
    a = stored(business_id, [plaid_account("A checking", current=1.0)])
    if case == "none_left":
        stored(business_id, [savings()])
    else:
        stored(
            business_id,
            [
                plaid_account("B small", current=100.0),
                plaid_account("B large", current=500.0),
            ],
        )
    make_primary(bid, "B small" if case == "untouched" else "A checking")

    response = call(caller, "DELETE", path(business_id, a.connection_id))

    assert response.status_code == 204
    expected = {"reassigned": ["B large"], "none_left": [], "untouched": ["B small"]}
    assert primaries(bid) == expected[case]


def _paired_across_banks(
    fake: SyncFake, business_id: str
) -> tuple[Connected, Connected]:
    sav, chq = savings(), checking()
    a, b = stored(business_id, [sav]), stored(business_id, [chq])
    # Plaid amounts: positive is money out.
    fake.script = [page([sav], added=[tx("out", sav, 10000.0, day=date(2026, 9, 14))])]
    sync(fake, a)
    fake.script = [page([chq], added=[tx("in", chq, -10000.0, day=date(2026, 9, 14))])]
    sync(fake, b)
    with get_sessionmaker()() as session:
        labels = sorted(
            (r.label, r.linked_transaction_id is not None)
            for r in session.scalars(
                select(BankTransaction).where(
                    BankTransaction.business_id == uuid.UUID(business_id)
                )
            )
        )
    assert labels == [("internal_transfer", True), ("internal_transfer", True)]
    return a, b


def test_disconnect_relabels(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C43."""
    caller, business_id = owner
    a, b = _paired_across_banks(fake, business_id)

    response = call(caller, "DELETE", path(business_id, a.connection_id))

    assert response.status_code == 204
    with get_sessionmaker()() as session:
        remaining = list(
            session.scalars(
                select(BankTransaction).where(
                    BankTransaction.business_id == b.business_id
                )
            )
        )
    assert len(remaining) == 1
    assert remaining[0].label == "normal"
    assert remaining[0].linked_transaction_id is None


def test_disconnect_publishes(
    fake: SyncFake, owner: tuple[Caller, str], published: list[events.Event]
) -> None:
    """C44."""
    caller, business_id = owner
    a, _ = _paired_across_banks(fake, business_id)
    published.clear()

    response = call(caller, "DELETE", path(business_id, a.connection_id))

    assert response.status_code == 204
    assert len(published) == 1
    event = published[0]
    assert event.business_id == a.business_id
    assert dict(event.payload) == {
        "connection_id": str(a.connection_id),
        "added": 0,
        "modified": 0,
        "removed": 1,
        "relabeled": 1,
        "balances_changed": True,
    }


def test_disconnect_stops_syncing(
    fake: SyncFake, owner: tuple[Caller, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """C45."""
    caller, business_id = owner
    c = _with_transactions(fake, business_id)
    with get_sessionmaker()() as session:
        connection = session.get(BankConnection, c.connection_id)
        assert connection is not None
        ciphertext = connection.access_token_ciphertext

    response = call(caller, "DELETE", path(business_id, c.connection_id))
    assert response.status_code == 204

    with get_sessionmaker()() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(BankConnection)
                .where(BankConnection.access_token_ciphertext == ciphertext)
            )
            == 0
        )
        candidates = {x.id for x in repository.nightly_candidates(session)}
    assert c.connection_id not in candidates

    fake.calls.clear()
    content = signing.body(c.provider_item_id)
    hook = client.post(
        "/v1/webhooks/plaid", content=content, headers=signing.headers(content)
    )
    assert hook.status_code == 200
    assert "sync" not in fake.calls

    configure_logging()
    capsys.readouterr()
    assert (
        service.sync_in_background(
            fake, business_id=c.business_id, connection_id=c.connection_id
        )
        is None
    )
    skipped = [
        line for line in log_lines(capsys) if line["event"] == "bank_sync.sync_skipped"
    ]
    assert len(skipped) == 1
    assert skipped[0]["business_id"] == str(c.business_id)
    assert skipped[0]["connection_id"] == str(c.connection_id)
    assert "sync" not in fake.calls


def test_disconnect_waits_for_sync(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    """C46."""
    caller, business_id = owner
    c = stored(business_id, [checking()])
    fake.hold_first = threading.Event()
    results: dict[str, Any] = {}
    errors: list[BaseException] = []

    def run_sync() -> None:
        try:
            results["sync"] = sync(fake, c)
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    def run_disconnect() -> None:
        try:
            results["disconnect"] = call(
                caller, "DELETE", path(business_id, c.connection_id)
            )
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    syncing = threading.Thread(target=run_sync)
    syncing.start()
    assert fake.entered.wait(10)
    disconnecting = threading.Thread(target=run_disconnect)
    disconnecting.start()
    time.sleep(0.5)
    assert disconnecting.is_alive(), "the disconnect did not wait for the sync"

    fake.hold_first.set()
    syncing.join(30)
    disconnecting.join(30)

    assert errors == []
    assert "sync" in results
    assert results["disconnect"].status_code == 204
    assert counts(c) == (0, 0, 0)


# S5 - every new route is the owner's alone


@pytest.mark.parametrize(("method", "suffix"), ROUTES, ids=ROUTE_IDS)
def test_foreign_connection_404(
    fake: SyncFake,
    owner: tuple[Caller, str],
    other: tuple[Caller, str],
    method: str,
    suffix: str,
) -> None:
    """C50."""
    caller, business_a = owner
    stranger, business_b = other
    mine = _with_transactions(fake, business_a)
    theirs = _with_transactions(fake, business_b)
    fake.calls.clear()
    before = (snapshot(mine.business_id), snapshot(theirs.business_id))

    not_member = call(stranger, method, path(business_a, mine.connection_id, suffix))
    foreign = call(caller, method, path(business_a, theirs.connection_id, suffix))
    missing = call(caller, method, path(business_a, uuid.uuid4(), suffix))

    assert not_member.status_code == 404
    assert not_member.json()["detail"] == "Business not found."
    for response in (foreign, missing):
        assert response.status_code == 404
        assert response.json()["detail"] == NOT_FOUND
    assert fake.calls == []
    assert (snapshot(mine.business_id), snapshot(theirs.business_id)) == before


@pytest.mark.parametrize(("method", "suffix"), ROUTES, ids=ROUTE_IDS)
def test_non_owner_403(
    fake: SyncFake,
    owner: tuple[Caller, str],
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    suffix: str,
) -> None:
    """C51."""
    caller, business_id = owner
    c = _with_transactions(fake, business_id)
    fake.calls.clear()

    malformed = call(caller, method, path(business_id, "not-a-uuid", suffix))
    assert malformed.status_code == 422
    assert malformed.json()["errors"][0]["loc"] == ["path", "connection_id"]

    before = snapshot(c.business_id)
    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="viewer"),
    )
    response = call(caller, method, path(business_id, c.connection_id, suffix))

    assert response.status_code == 403
    assert response.json()["detail"] == "You don't have permission to do this."
    assert fake.calls == []
    assert snapshot(c.business_id) == before


def test_no_secrets_leak(
    fake: SyncFake, owner: tuple[Caller, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """C52."""
    caller, business_id = owner
    token, message = "access-sandbox-c52-secret", "c52-plaid-message"
    c = stored(business_id, [checking()], token=token)

    def failing() -> PlaidError:
        error = other_error()
        error.args = (message,)
        return error

    configure_logging()
    capsys.readouterr()
    responses = [
        call(caller, "POST", path(business_id, c.connection_id, "/link-token"))
    ]
    fake.script = [failing()]
    responses.append(
        call(caller, "POST", path(business_id, c.connection_id, "/repair"))
    )
    fake.fail["remove"] = failing()
    responses.append(call(caller, "DELETE", path(business_id, c.connection_id)))
    del fake.fail["remove"]
    responses.append(call(caller, "DELETE", path(business_id, c.connection_id)))

    assert [r.status_code for r in responses] == [200, 502, 502, 204]
    output = capsys.readouterr().out
    details = json.dumps([a.details for a in audits(c.business_id)])
    for text in [*(r.text for r in responses), output, details]:
        assert token not in text
        assert message not in text
