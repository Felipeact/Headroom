"""Spec 18: `python -m app.fixtures.load harbor_street` (AD-069)."""

import json
import uuid
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app import db, events
from app.audit import AuditLog
from app.db import get_engine, get_sessionmaker
from app.fixtures import harbor_street, load
from app.fixtures.plaid import FixturePlaidClient
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.accounts.models import Business
from app.modules.bank_sync.models import BankAccount, BankConnection, BankTransaction
from app.modules.bank_sync.plaid import LinkTokenRequest, PlaidError
from app.modules.bank_sync.tokens import decrypt_access_token
from app.settings import get_settings
from tests.tokens import bearer, token

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

SAMPLE = harbor_street.generate(0)
SYNCED_AT = datetime(2026, 9, 26, 10, 2, tzinfo=UTC)
TRANSFER_OUT = ("TRANSFER_OUT_ACCOUNT_TRANSFER", "TRANSFER_OUT_SAVINGS")
CARD_PAYMENT = "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"
COUNTED = (Business, BankConnection, BankAccount, BankTransaction, AuditLog)


@dataclass
class Loaded:
    clerk_user_id: str
    business_id: str
    code: int
    out: str
    err: str

    @property
    def headers(self) -> dict[str, str]:
        return bearer(token(self.clerk_user_id))


def run(capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, str, str]:
    capsys.readouterr()
    code = load.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def plain_lines(out: str) -> list[str]:
    """Stdout lines that are not JSON log lines."""
    lines = []
    for line in out.splitlines():
        try:
            json.loads(line)
        except ValueError:
            lines.append(line)
    return lines


def load_new(capsys: pytest.CaptureFixture[str], *extra: str) -> Loaded:
    clerk_user_id = f"user_sample_{uuid.uuid4().hex[:10]}"
    code, out, err = run(
        capsys, ["harbor_street", "--clerk-user-id", clerk_user_id, *extra]
    )
    lines = plain_lines(out)
    assert code == 0, err
    assert len(lines) == 1, out
    return Loaded(clerk_user_id, str(uuid.UUID(lines[0].strip())), code, out, err)


def counts() -> dict[str, int]:
    with get_sessionmaker()() as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            or 0
            for model in COUNTED
        }


def transactions_via_api(loaded: Loaded) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 500}
        if cursor:
            params["cursor"] = cursor
        response = client.get(
            f"/v1/businesses/{loaded.business_id}/bank/transactions",
            params=params,
            headers=loaded.headers,
        )
        assert response.status_code == 200
        body = response.json()
        items += body["items"]
        cursor = body["next_cursor"]
        if cursor is None:
            return items


@pytest.fixture(scope="module")
def recorded() -> Iterator[list[events.Event]]:
    seen: list[events.Event] = []
    events.subscribe("transactions.synced", seen.append)
    yield seen
    events.unsubscribe("transactions.synced", seen.append)


@pytest.fixture(scope="module")
def shared(recorded: list[events.Event]) -> tuple[Loaded, list[events.Event]]:
    """One load for the read-only checks, with its `transactions.synced` events."""
    clerk_user_id = f"user_sample_{uuid.uuid4().hex[:10]}"
    recorded.clear()
    code = load.main(["harbor_street", "--clerk-user-id", clerk_user_id])
    assert code == 0
    with get_sessionmaker()() as session:
        user = accounts_service.get_or_create_user(session, clerk_user_id)
        (business,) = accounts_service.list_businesses(session, user.id)
    loaded = Loaded(clerk_user_id, str(business.id), code, "", "")
    return loaded, list(recorded)


def test_load_creates_owned_business(capsys: pytest.CaptureFixture[str]) -> None:
    """C19."""
    loaded = load_new(capsys)
    with get_sessionmaker()() as session:
        user = accounts_service.get_or_create_user(session, loaded.clerk_user_id)
        businesses = accounts_service.list_businesses(session, user.id)
    assert [
        (str(b.id), b.name, b.province, b.time_zone, b.role) for b in businesses
    ] == [
        (
            loaded.business_id,
            "Harbor Street Plumbing",
            "ON",
            "America/Toronto",
            "owner",
        )
    ]


def test_default_owner(capsys: pytest.CaptureFixture[str]) -> None:
    """C19."""
    code, out, err = run(capsys, ["harbor_street"])
    assert code == 0, err
    (line,) = plain_lines(out)
    business_id = uuid.UUID(line.strip())
    with get_sessionmaker()() as session:
        user = accounts_service.get_or_create_user(session, "user_sample_harbor_street")
        owned = accounts_service.list_businesses(session, user.id)
    assert [b.id for b in owned] == [business_id]


def test_accounts_through_api(shared: tuple[Loaded, list[events.Event]]) -> None:
    """C20."""
    loaded, _ = shared
    response = client.get(
        f"/v1/businesses/{loaded.business_id}/bank/connections",
        headers=loaded.headers,
    )
    assert response.status_code == 200
    connections = response.json()["items"]
    assert [c["institution_name"] for c in connections] == [
        "Harbor Community Bank",
        "Summit Federal",
    ]
    for connection in connections:
        assert connection["status"] == "synced"
        # The instant; the offset it is written with follows the database session.
        assert datetime.fromisoformat(connection["last_synced_at"]) == SYNCED_AT
    got = {
        (c["institution_name"], a["name"]): (
            a["type"],
            a["mask"],
            a["balance_cents"],
            a["available_cents"],
            a["currency"],
            a["included"],
            a["primary"],
        )
        for c in connections
        for a in c["accounts"]
    }
    assert got == {
        ("Harbor Community Bank", "Operating checking"): (
            "checking",
            "2381",
            800000,
            None,
            "CAD",
            True,
            True,
        ),
        ("Harbor Community Bank", "Reserve savings"): (
            "savings",
            "9025",
            3430000,
            None,
            "CAD",
            True,
            False,
        ),
        ("Harbor Community Bank", "Line of credit"): (
            "line_of_credit",
            "7702",
            0,
            2000000,
            "CAD",
            False,
            False,
        ),
        ("Summit Federal", "Business Visa"): (
            "credit_card",
            "5530",
            245000,
            None,
            "CAD",
            False,
            False,
        ),
    }
    assert [a["name"] for a in connections[0]["accounts"]] == [
        "Line of credit",
        "Operating checking",
        "Reserve savings",
    ]


def test_transactions_through_api(shared: tuple[Loaded, list[events.Event]]) -> None:
    """C21."""
    loaded, _ = shared
    items = transactions_via_api(loaded)
    assert len(items) == len(SAMPLE.history)
    got = Counter(
        (i["date"], i["amount_cents"], i["currency"], i["description"]) for i in items
    )
    want = Counter(
        (t.date.isoformat(), t.amount_cents, t.currency, t.description)
        for t in SAMPLE.history
    )
    assert got == want


def test_labels_after_load(shared: tuple[Loaded, list[events.Event]]) -> None:
    """C22."""
    loaded, _ = shared
    with get_sessionmaker()() as session:
        rows = list(
            session.scalars(
                select(BankTransaction).where(
                    BankTransaction.business_id == uuid.UUID(loaded.business_id)
                )
            )
        )
        types = {
            a.id: a.name
            for a in session.scalars(
                select(BankAccount).where(
                    BankAccount.business_id == uuid.UUID(loaded.business_id)
                )
            )
        }
    assert len(rows) == len(SAMPLE.history)
    transfers = [
        r
        for r in rows
        if (r.category_detailed or "").startswith(("TRANSFER_OUT", "TRANSFER_IN"))
        and types[r.account_id] in ("Operating checking", "Reserve savings")
    ]
    card = [
        r
        for r in rows
        if r.category_detailed == CARD_PAYMENT
        and (types[r.account_id] == "Business Visa" or r.amount_cents < 0)
    ]
    assert transfers and card
    assert {r.label for r in transfers} == {"internal_transfer"}
    assert {r.label for r in card} == {"card_payment"}
    assert all(r.linked_transaction_id is not None for r in transfers + card)
    assert not [r for r in rows if r.label == "in_transit"]


def test_publishes_transactions_synced(
    shared: tuple[Loaded, list[events.Event]],
) -> None:
    """C23."""
    loaded, seen = shared
    assert len(seen) == 2
    assert {str(e.business_id) for e in seen} == {loaded.business_id}
    by_bank = Counter()
    for bank in SAMPLE.banks:
        keys = {a.key for a in bank.accounts}
        by_bank[bank.key] = sum(1 for t in SAMPLE.history if t.account_key in keys)
    with get_sessionmaker()() as session:
        connection_bank = {
            str(c.id): c.institution_name
            for c in session.scalars(
                select(BankConnection).where(
                    BankConnection.business_id == uuid.UUID(loaded.business_id)
                )
            )
        }
    names = {b.institution_name: b.key for b in SAMPLE.banks}
    got = {
        names[connection_bank[str(e.payload["connection_id"])]]: e.payload["added"]
        for e in seen
    }
    assert got == dict(by_bank)


def test_second_load_is_noop(capsys: pytest.CaptureFixture[str]) -> None:
    """C24."""
    loaded = load_new(capsys)
    before = counts()
    code, out, err = run(
        capsys, ["harbor_street", "--clerk-user-id", loaded.clerk_user_id]
    )
    assert code == 0, err
    (line,) = plain_lines(out)
    assert "already loaded" in line
    assert loaded.business_id in line
    assert counts() == before


def _other_business(capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    clerk_user_id = f"user_other_{uuid.uuid4().hex[:10]}"
    with get_sessionmaker()() as session:
        user = accounts_service.get_or_create_user(session, clerk_user_id)
        business = accounts_service.create_business(
            session,
            user_id=user.id,
            name="Bayview Bakery",
            province="BC",
            time_zone="America/Vancouver",
        )
    return clerk_user_id, str(business.id)


def _partial_sample(capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    loaded = load_new(capsys)
    with get_sessionmaker()() as session:
        connection = session.scalars(
            select(BankConnection).where(
                BankConnection.business_id == uuid.UUID(loaded.business_id),
                BankConnection.institution_name == "Summit Federal",
            )
        ).one()
        accounts = select(BankAccount.id).where(
            BankAccount.connection_id == connection.id
        )
        session.execute(
            delete(BankTransaction).where(BankTransaction.account_id.in_(accounts))
        )
        session.execute(
            delete(BankAccount).where(BankAccount.connection_id == connection.id)
        )
        session.delete(connection)
        session.commit()
    return loaded.clerk_user_id, loaded.business_id


@pytest.mark.parametrize(
    "owner", [_other_business, _partial_sample], ids=["other", "partial"]
)
def test_owner_with_other_business(
    capsys: pytest.CaptureFixture[str], owner: Any
) -> None:
    """C25."""
    clerk_user_id, business_id = owner(capsys)
    before = counts()
    code, _, err = run(capsys, ["harbor_street", "--clerk-user-id", clerk_user_id])
    assert code == 1
    lines = [line for line in err.splitlines() if line.strip()]
    assert len(lines) == 1
    assert business_id in lines[0]
    assert counts() == before


def _clear_caches() -> None:
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()


def test_refuses_non_local_database(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C26."""
    engines: list[str] = []
    monkeypatch.setattr(db, "create_engine", lambda *a, **k: engines.append("x"))
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:pw@db.example.com:5432/headroom"
    )
    _clear_caches()
    try:
        code, _, err = run(capsys, ["harbor_street"])
    finally:
        monkeypatch.undo()
        _clear_caches()
    assert code == 1
    assert "Refusing to load sample data into a non-local database." in err
    assert engines == []
    for url in (
        "postgresql+psycopg://u:p@localhost:5432/headroom",
        "postgresql+psycopg://u:p@127.0.0.1:5432/headroom",
        "postgresql+psycopg://u:p@[::1]:5432/headroom",
    ):
        assert load.is_local_database(url), url
    assert not load.is_local_database(
        "postgresql+psycopg://u:p@db.example.com:5432/headroom"
    )


def test_unknown_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    """C27."""
    with pytest.raises(SystemExit) as exc:
        load.main(["acme"])
    assert exc.value.code == 2
    assert "harbor_street" in capsys.readouterr().err


def test_logs_fixture_loaded(capsys: pytest.CaptureFixture[str]) -> None:
    """C28."""
    loaded = load_new(capsys)
    logged = []
    for line in loaded.out.splitlines():
        try:
            logged.append(json.loads(line))
        except ValueError:
            continue
    done = [e for e in logged if e.get("event") == "fixture.loaded"]
    assert len(done) == 1
    assert done[0]["fixture"] == "harbor_street"
    assert done[0]["seed"] == 0
    assert done[0]["business_id"] == loaded.business_id
    assert done[0]["transactions"] == len(SAMPLE.history)
    assert load.ACCESS_TOKEN == "sample-not-a-token"
    assert "sample-not-a-token" not in loaded.out
    assert "sample-not-a-token" not in loaded.err


def test_fixture_plaid_identifiers(shared: tuple[Loaded, list[events.Event]]) -> None:
    """C29."""
    loaded, _ = shared
    business_id = uuid.UUID(loaded.business_id)
    with get_sessionmaker()() as session:
        connections = list(
            session.scalars(
                select(BankConnection).where(BankConnection.business_id == business_id)
            )
        )
        account_ids = list(
            session.scalars(
                select(BankAccount.provider_account_id).where(
                    BankAccount.business_id == business_id
                )
            )
        )
        transaction_ids = list(
            session.scalars(
                select(BankTransaction.provider_transaction_id).where(
                    BankTransaction.business_id == business_id
                )
            )
        )
    assert len(connections) == 2 and len(account_ids) == 4
    assert len(transaction_ids) == len(SAMPLE.history)
    for value in (
        [c.provider_item_id for c in connections] + account_ids + transaction_ids
    ):
        assert value.startswith("sample-"), value
    for c in connections:
        assert decrypt_access_token(c.access_token_ciphertext) == "sample-not-a-token"
        assert "sample-not-a-token" not in c.access_token_ciphertext

    fake = FixturePlaidClient(SAMPLE.banks[0], SAMPLE.history, business_id=business_id)
    request = LinkTokenRequest(
        client_user_id="u",
        client_name="Headroom",
        language="en",
        country_codes=("CA",),
        products=(),
        days_requested=None,
    )
    calls = [
        lambda: fake.create_link_token(request),
        lambda: fake.remove_item("sample-not-a-token"),
        lambda: fake.get_webhook_verification_key("key"),
    ]
    for call in calls:
        with pytest.raises(PlaidError) as exc:
            call()
        assert exc.value.error_code == "NOT_SUPPORTED"
