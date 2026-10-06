"""Spec 13: choose cash accounts. Uses spec 12's fake Plaid client; nothing here calls Plaid."""

import json
import threading
import uuid
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.audit import AuditLog
from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync import service
from app.modules.bank_sync.models import BankAccount, BankConnection
from app.modules.bank_sync.plaid import PlaidAccount, get_plaid_client
from tests.test_bank_connect import FakePlaid, connect, connections_path
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


ACCOUNT_KEYS = {
    "id",
    "name",
    "type",
    "mask",
    "currency",
    "balance_cents",
    "available_cents",
    "included",
    "primary",
}
NOT_CASH_CREDIT = "Credit cards and lines of credit can't count as cash."
NOT_CASH_OTHER = "This type of account can't count as cash."
NOT_CASH_CURRENCY = "Only Canadian dollar accounts can count as cash for now."
PRIMARY_NOT_INCLUDED = "Only an account that counts as cash can be primary."
EXCLUDE_PRIMARY = "Choose another primary account first."

KINDS: dict[str, tuple[str, str | None]] = {
    "checking": ("depository", "checking"),
    "savings": ("depository", "savings"),
    "credit_card": ("credit", "credit card"),
    "line_of_credit": ("credit", "line of credit"),
    "other": ("depository", "money market"),
}


def acct(
    name: str,
    kind: str = "checking",
    *,
    current: float | None = 100.0,
    available: float | None = None,
    currency: str = "CAD",
    mask: str | None = "0001",
) -> PlaidAccount:
    plaid_type, subtype = KINDS[kind]
    return PlaidAccount(
        account_id=f"acc-{uuid.uuid4().hex}",
        name=name,
        type=plaid_type,
        subtype=subtype,
        mask=mask,
        current=current,
        iso_currency_code=currency,
        unofficial_currency_code=None,
        available=available,
    )


def connect_with(
    fake: FakePlaid,
    caller: Caller,
    business_id: str,
    accounts: list[PlaidAccount],
    institution: str = "ins_42",
) -> dict[str, Any]:
    fake.accounts = lambda: accounts
    fake.institution_id = institution
    response = connect(caller, business_id)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def by_name(connection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["name"]: a for a in connection["accounts"]}


def account_path(business_id: str, account_id: str) -> str:
    return f"/v1/businesses/{business_id}/bank/accounts/{account_id}"


def patch(caller: Caller, business_id: str, account_id: str, body: Any) -> Any:
    return client.patch(
        account_path(business_id, account_id), json=body, headers=caller.headers
    )


def rows(business_id: str) -> dict[str, BankAccount]:
    with get_sessionmaker()() as session:
        found = list(
            session.scalars(
                select(BankAccount).where(
                    BankAccount.business_id == uuid.UUID(business_id)
                )
            )
        )
        session.expunge_all()
    return {r.name: r for r in found}


def snapshot(business_id: str) -> dict[str, tuple[bool, bool]]:
    return {n: (r.included, r.is_primary) for n, r in rows(business_id).items()}


def primaries(business_id: str) -> list[str]:
    return [n for n, r in rows(business_id).items() if r.is_primary]


def updated_audits(business_id: str) -> list[AuditLog]:
    with get_sessionmaker()() as session:
        found = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.business_id == uuid.UUID(business_id),
                    AuditLog.action == "bank_account.updated",
                )
            )
        )
        session.expunge_all()
    return found


def mixed_bank() -> list[PlaidAccount]:
    return [
        acct("Chequing", "checking", current=5000.0),
        acct("Reserve", "savings", current=20000.0),
        acct("Visa", "credit_card", current=800.0, available=4200.0),
        acct("Credit line", "line_of_credit", current=0.0, available=20000.0),
        acct("Money market", "other"),
        acct("US chequing", "checking", currency="USD"),
        acct("US savings", "savings", currency="USD"),
    ]


# S1 - the cash rules


def test_connect_includes_cad_checking_only(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    body = connect_with(
        fake,
        owner,
        business_id,
        [
            acct("A checking"),
            acct("B savings", "savings"),
            acct("C card", "credit_card"),
            acct("D line", "line_of_credit"),
            acct("E other", "other"),
            acct("F usd", "checking", currency="USD"),
        ],
    )

    returned = {a["name"]: a["included"] for a in body["accounts"]}
    expected = {
        "A checking": True,
        "B savings": False,
        "C card": False,
        "D line": False,
        "E other": False,
        "F usd": False,
    }
    assert returned == expected
    assert {n: r.included for n, r in rows(business_id).items()} == expected


@pytest.mark.parametrize(
    ("available", "expected"),
    [(20000.0, 2000000), (1234.565, 123456), (None, None)],
)
def test_available_cents_mapping(
    available: float | None,
    expected: int | None,
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
) -> None:
    owner, business_id = owner_a
    body = connect_with(
        fake, owner, business_id, [acct("Line", "line_of_credit", available=available)]
    )

    assert body["accounts"][0]["available_cents"] == expected
    assert rows(business_id)["Line"].available_cents == expected


def test_include_cash_account(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake,
            owner,
            business_id,
            [acct("Main", current=900.0), acct("Ops", current=100.0)]
            + [acct("Reserve", "savings")],
        )
    )
    # Ops starts included; exclude it first so including it is a real change.
    assert (
        patch(
            owner, business_id, accounts["Ops"]["id"], {"included": False}
        ).status_code
        == 200
    )

    for name in ("Reserve", "Ops"):
        response = patch(owner, business_id, accounts[name]["id"], {"included": True})
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == accounts[name]["id"]
        assert body["included"] is True
        assert rows(business_id)[name].included is True


@pytest.mark.parametrize(
    ("name", "detail"),
    [
        ("Visa", NOT_CASH_CREDIT),
        ("Credit line", NOT_CASH_CREDIT),
        ("Money market", NOT_CASH_OTHER),
        ("US chequing", NOT_CASH_CURRENCY),
        ("US savings", NOT_CASH_CURRENCY),
    ],
    ids=[
        "include_credit_conflicts-card",
        "include_credit_conflicts-line",
        "include_other_conflicts",
        "include_non_cad_conflicts-checking",
        "include_non_cad_conflicts-savings",
    ],
)
def test_include_not_cash(
    name: str, detail: str, owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    accounts = by_name(connect_with(fake, owner, business_id, mixed_bank()))
    before = snapshot(business_id)

    response = patch(owner, business_id, accounts[name]["id"], {"included": True})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == detail
    assert snapshot(business_id) == before


def test_exclude_non_primary(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake,
            owner,
            business_id,
            [acct("Main", current=900.0), acct("Ops", current=100.0)],
        )
    )
    assert accounts["Ops"]["primary"] is False

    response = patch(owner, business_id, accounts["Ops"]["id"], {"included": False})

    assert response.status_code == 200
    assert response.json()["included"] is False
    assert rows(business_id)["Ops"].included is False


def test_included_cash_constraint(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    accounts = by_name(connect_with(fake, owner, business_id, mixed_bank()))

    for name in ("Visa", "Money market", "US chequing"):
        with get_sessionmaker()() as session:
            with pytest.raises(IntegrityError, match="ck_bank_accounts_included_cash"):
                session.execute(
                    text("UPDATE bank_accounts SET included = true WHERE id = :id"),
                    {"id": uuid.UUID(accounts[name]["id"])},
                )
            session.rollback()


# S2 - one primary account


@pytest.mark.parametrize(
    ("accounts", "expected"),
    [
        (
            [
                acct("Low", current=50.0),
                acct("High", current=90.0),
                acct("None", current=None),
                acct("Big savings", "savings", current=200.0),
            ],
            "High",
        ),
        ([acct("B", current=None), acct("A", current=None)], "A"),
        ([acct("Ops", current=70.0), acct("Main", current=70.0)], "Main"),
    ],
    ids=["largest_balance", "null_last_then_name", "tie_by_name"],
)
def test_first_connect_primary(
    accounts: list[PlaidAccount],
    expected: str,
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
) -> None:
    owner, business_id = owner_a
    body = connect_with(fake, owner, business_id, accounts)

    assert [a["name"] for a in body["accounts"] if a["primary"]] == [expected]
    assert primaries(business_id) == [expected]


def test_no_included_no_primary(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    body = connect_with(
        fake,
        owner,
        business_id,
        [acct("Reserve", "savings"), acct("Visa", "credit_card")],
    )

    assert [a["primary"] for a in body["accounts"]] == [False, False]
    assert primaries(business_id) == []


def test_second_connect_keeps_primary(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    connect_with(fake, owner, business_id, [acct("First", current=10.0)])
    second = connect_with(
        fake, owner, business_id, [acct("Second", current=99999.0)], institution="ins_2"
    )

    assert [a["primary"] for a in second["accounts"]] == [False]
    assert primaries(business_id) == ["First"]


def test_move_primary(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake,
            owner,
            business_id,
            [acct("Main", current=900.0), acct("Ops", current=100.0)],
        )
    )

    response = patch(owner, business_id, accounts["Ops"]["id"], {"primary": True})

    assert response.status_code == 200
    assert response.json()["primary"] is True
    assert snapshot(business_id) == {"Main": (True, False), "Ops": (True, True)}


def test_include_and_make_primary(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake, owner, business_id, [acct("Main"), acct("Reserve", "savings")]
        )
    )

    response = patch(
        owner,
        business_id,
        accounts["Reserve"]["id"],
        {"included": True, "primary": True},
    )

    assert response.status_code == 200
    assert (response.json()["included"], response.json()["primary"]) == (True, True)
    assert snapshot(business_id) == {"Main": (True, False), "Reserve": (True, True)}


def test_primary_requires_included(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake, owner, business_id, [acct("Main"), acct("Reserve", "savings")]
        )
    )
    before = snapshot(business_id)

    response = patch(owner, business_id, accounts["Reserve"]["id"], {"primary": True})

    assert response.status_code == 409
    assert response.json()["detail"] == PRIMARY_NOT_INCLUDED
    assert snapshot(business_id) == before


def test_exclude_primary_conflicts(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake, owner, business_id, [acct("Main", current=900.0), acct("Ops")]
        )
    )
    before = snapshot(business_id)

    response = patch(owner, business_id, accounts["Main"]["id"], {"included": False})

    assert response.status_code == 409
    assert response.json()["detail"] == EXCLUDE_PRIMARY
    assert snapshot(business_id) == before


def test_first_include_becomes_primary(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake,
            owner,
            business_id,
            [acct("Reserve", "savings"), acct("Visa", "credit_card")],
        )
    )

    response = patch(owner, business_id, accounts["Reserve"]["id"], {"included": True})

    assert response.status_code == 200
    assert (response.json()["included"], response.json()["primary"]) == (True, True)
    assert primaries(business_id) == ["Reserve"]


def test_primary_constraints(
    owner_a: tuple[Caller, str], owner_b: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    other, other_business = owner_b
    accounts = by_name(
        connect_with(
            fake,
            owner,
            business_id,
            [acct("Main", current=900.0), acct("Ops"), acct("Reserve", "savings")],
        )
    )
    # A primary in a second business is fine: the index is per business.
    other_accounts = connect_with(
        fake, other, other_business, [acct("Theirs")], "ins_9"
    )
    assert [a["primary"] for a in other_accounts["accounts"]] == [True]

    statements = [
        (
            "UPDATE bank_accounts SET is_primary = true WHERE id = :id",
            "Ops",
            "uq_bank_accounts_primary_business_id",
        ),
        (
            "UPDATE bank_accounts SET is_primary = true WHERE id = :id",
            "Reserve",
            "ck_bank_accounts_primary_included",
        ),
    ]
    for sql, name, constraint in statements:
        with get_sessionmaker()() as session:
            if name == "Reserve":
                # Clear the real primary first, so only the check constraint can fire.
                session.execute(
                    text("UPDATE bank_accounts SET is_primary = false WHERE id = :id"),
                    {"id": uuid.UUID(accounts["Main"]["id"])},
                )
            with pytest.raises(IntegrityError, match=constraint):
                session.execute(text(sql), {"id": uuid.UUID(accounts[name]["id"])})
            session.rollback()


def run_together(
    work: list[Callable[[], object]],
) -> tuple[list[object], list[BaseException]]:
    barrier = threading.Barrier(len(work))
    results: list[object] = []
    errors: list[BaseException] = []

    def run(job: Callable[[], object]) -> None:
        try:
            barrier.wait()
            results.append(job())
        except BaseException as exc:  # noqa: BLE001 - reported by the caller's assertion
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(job,)) for job in work]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results, errors


def test_concurrent_primary_moves(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake,
            owner,
            business_id,
            [acct("Main", current=900.0), acct("Ops"), acct("Spare", current=1.0)],
        )
    )

    def move(name: str) -> Callable[[], object]:
        def job() -> object:
            with get_sessionmaker()() as session:
                return service.update_account(
                    session,
                    business_id=uuid.UUID(business_id),
                    account_id=uuid.UUID(accounts[name]["id"]),
                    user_id=owner.id,
                    included=None,
                    primary=True,
                )

        return job

    results, errors = run_together([move("Ops"), move("Spare")])

    assert errors == []
    assert len(results) == 2
    assert len(primaries(business_id)) == 1
    assert primaries(business_id)[0] in {"Ops", "Spare"}


def test_concurrent_connects_one_primary(owner_a: tuple[Caller, str]) -> None:
    owner, business_id = owner_a

    def connect_bank(institution: str, name: str) -> Callable[[], object]:
        plaid = FakePlaid()
        plaid.institution_id = institution
        plaid.accounts = lambda: [acct(name)]

        def job() -> object:
            with get_sessionmaker()() as session:
                return service.connect_bank(
                    session,
                    plaid,
                    business_id=uuid.UUID(business_id),
                    user_id=owner.id,
                    public_token="public-sandbox-1",
                )

        return job

    results, errors = run_together(
        [connect_bank("ins_1", "One"), connect_bank("ins_2", "Two")]
    )

    assert errors == []
    assert len(results) == 2
    with get_sessionmaker()() as session:
        count = len(
            list(
                session.scalars(
                    select(BankConnection.id).where(
                        BankConnection.business_id == uuid.UUID(business_id)
                    )
                )
            )
        )
    assert count == 2
    assert len(primaries(business_id)) == 1


# S3 - listing and updating are the owner's, for their business only


def test_list_connections(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    empty = client.get(connections_path(business_id), headers=owner.headers)
    assert empty.status_code == 200
    assert empty.json() == {"items": []}

    first = connect_with(
        fake, owner, business_id, [acct("Zed"), acct("Alpha", "savings")]
    )
    second = connect_with(fake, owner, business_id, [acct("Mid")], institution="ins_2")

    response = client.get(connections_path(business_id), headers=owner.headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items"}
    assert [c["id"] for c in body["items"]] == [first["id"], second["id"]]
    for connection in body["items"]:
        # Spec 17 added status and last_synced_at (AD-063).
        assert set(connection) == {
            "id",
            "institution_name",
            "created_at",
            "accounts",
            "status",
            "last_synced_at",
        }
    assert [a["name"] for a in body["items"][0]["accounts"]] == ["Alpha", "Zed"]


def test_account_json_keys(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    created = connect_with(fake, owner, business_id, mixed_bank())
    listed = client.get(connections_path(business_id), headers=owner.headers)
    account = created["accounts"][0]
    patched = patch(
        owner, business_id, account["id"], {"included": account["included"]}
    )

    returned = [
        *created["accounts"],
        *listed.json()["items"][0]["accounts"],
        patched.json(),
    ]
    assert all(set(a) == ACCOUNT_KEYS for a in returned)
    stored = rows(business_id).values()
    plaid_ids = [r.plaid_account_id for r in stored] + fake.item_ids
    for body in (json.dumps(created), listed.text, patched.text):
        assert not any(pid in body for pid in plaid_ids)


def test_non_member_gets_404(
    owner_a: tuple[Caller, str], owner_b: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_a = owner_a
    stranger, _ = owner_b
    accounts = by_name(
        connect_with(fake, owner, business_a, [acct("Main"), acct("Ops")])
    )
    before = snapshot(business_a)

    listed = client.get(connections_path(business_a), headers=stranger.headers)
    patched = patch(stranger, business_a, accounts["Ops"]["id"], {"primary": True})

    for response in (listed, patched):
        assert response.status_code == 404
        assert response.json()["detail"] == "Business not found."
    assert snapshot(business_a) == before


def test_non_owner_gets_403(
    owner_a: tuple[Caller, str], fake: FakePlaid, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(fake, owner, business_id, [acct("Main"), acct("Ops")])
    )
    before = snapshot(business_id)
    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="viewer"),
    )

    listed = client.get(connections_path(business_id), headers=owner.headers)
    patched = patch(owner, business_id, accounts["Ops"]["id"], {"primary": True})

    for response in (listed, patched):
        assert response.status_code == 403
        assert response.json()["detail"] == "You don't have permission to do this."
    assert snapshot(business_id) == before


def test_foreign_account_gets_404(
    owner_a: tuple[Caller, str], owner_b: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_a = owner_a
    other, business_b = owner_b
    accounts = by_name(
        connect_with(fake, owner, business_a, [acct("Main"), acct("Ops")])
    )
    before = snapshot(business_a)

    foreign = patch(other, business_b, accounts["Ops"]["id"], {"primary": True})
    missing = patch(owner, business_a, str(uuid.uuid4()), {"primary": True})

    for response in (foreign, missing):
        assert response.status_code == 404
        assert response.json()["detail"] == "Account not found."
    assert snapshot(business_a) == before


def test_account_routes_require_member() -> None:
    walked = {
        (method, route.path)
        for route in _routes(app.routes)
        if "{business_id}" in route.path
        for method in route.methods
    }
    assert ("GET", "/businesses/{business_id}/bank/connections") in walked
    assert ("PATCH", "/businesses/{business_id}/bank/accounts/{account_id}") in walked
    assert business_routes_missing_member(app) == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"included": True, "extra": 1},
        {"primary": False},
        {"primary": None},
        {"included": "yes"},
    ],
    ids=["empty", "extra", "primary_false", "primary_null", "included_not_bool"],
)
def test_patch_validation(
    body: dict[str, Any], owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(fake, owner, business_id, [acct("Main"), acct("Ops")])
    )
    before = snapshot(business_id)

    response = patch(owner, business_id, accounts["Ops"]["id"], body)

    assert response.status_code == 422
    assert response.json()["errors"]
    assert snapshot(business_id) == before


def test_patch_validation_malformed_ids(
    owner_a: tuple[Caller, str], fake: FakePlaid
) -> None:
    owner, business_id = owner_a
    cases = [
        (
            client.get(connections_path("not-a-uuid"), headers=owner.headers),
            "business_id",
        ),
        (
            patch(owner, "not-a-uuid", str(uuid.uuid4()), {"primary": True}),
            "business_id",
        ),
        (patch(owner, business_id, "not-a-uuid", {"primary": True}), "account_id"),
    ]
    for response, param in cases:
        assert response.status_code == 422
        assert any(e["loc"][-1] == param for e in response.json()["errors"])


def test_update_audited(owner_a: tuple[Caller, str], fake: FakePlaid) -> None:
    owner, business_id = owner_a
    accounts = by_name(
        connect_with(
            fake,
            owner,
            business_id,
            [acct("Main"), acct("Reserve", "savings"), acct("Rainy", "savings")]
            + [acct("Visa", "credit_card")],
        )
    )

    assert (
        patch(
            owner, business_id, accounts["Reserve"]["id"], {"included": True}
        ).status_code
        == 200
    )
    first = updated_audits(business_id)
    assert len(first) == 1
    entry = first[0]
    assert entry.business_id == uuid.UUID(business_id)
    assert entry.actor_user_id == str(owner.id)
    assert entry.target_type == "bank_account"
    assert entry.target_id == accounts["Reserve"]["id"]
    assert entry.details == {"included": True}

    both = patch(
        owner, business_id, accounts["Rainy"]["id"], {"included": True, "primary": True}
    )
    assert both.status_code == 200
    second = [
        e for e in updated_audits(business_id) if e.target_id == accounts["Rainy"]["id"]
    ]
    assert [e.details for e in second] == [{"included": True, "primary": True}]

    unchanged = patch(owner, business_id, accounts["Main"]["id"], {"included": True})
    refused = patch(owner, business_id, accounts["Visa"]["id"], {"included": True})
    assert unchanged.status_code == 200
    assert refused.status_code == 409
    assert len(updated_audits(business_id)) == 2


def test_update_logged(
    owner_a: tuple[Caller, str],
    fake: FakePlaid,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner, business_id = owner_a
    plaid_accounts = [
        acct("Main", mask="2381", current=8000.0),
        acct("Reserve", "savings", mask="9025", current=34300.0),
    ]
    accounts = by_name(connect_with(fake, owner, business_id, plaid_accounts))
    configure_logging()
    capsys.readouterr()

    patch(owner, business_id, accounts["Reserve"]["id"], {"included": True})

    out = capsys.readouterr().out
    lines = [json.loads(line) for line in out.splitlines()]
    events = [line for line in lines if line["event"] == "bank_account.updated"]
    assert len(events) == 1
    assert events[0]["business_id"] == business_id
    assert events[0]["account_id"] == accounts["Reserve"]["id"]
    assert events[0]["included"] is True
    for secret in ("Main", "Reserve", "2381", "9025", "800000", "3430000", "34300"):
        assert secret not in out
