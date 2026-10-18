"""Spec 16: labels that depend on the business-local date, through the nightly sync.

`run_due(now)` is the one sync path that takes a clock, so the in-transit window is proven
here. Like spec 15's tests, these run against a database of their own, with the bank
tables emptied before each test. Every business is in `America/Toronto`, so the nightly
sync runs at 06:00 UTC (02:00 local) and "today" is that UTC date.
"""

import dataclasses
import json
import uuid
from collections.abc import Iterator, Sequence
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text, update

from app import events
from app.db import get_sessionmaker
from app.jobs import nightly
from app.jobs.run_due import run_due
from app.log import configure_logging
from app.modules.accounts import repository as accounts_repository
from app.modules.bank_sync import repository, service
from app.modules.bank_sync.models import BankConnection
from app.modules.bank_sync.plaid import PlaidAccount, PlaidTransaction
from app.modules.bank_sync.tokens import encrypt_access_token
from tests import test_transaction_sync as sync_tests
from tests.test_nightly_sync import CREATED_AT, NightlyFake
from tests.test_transaction_labels import (
    LABELS,
    assert_paired,
    assert_unpaired,
    card,
    move,
    operating,
    savings,
)
from tests.test_transaction_sync import credit_line, page, rows

pytestmark = pytest.mark.usefixtures("isolated_database")

TORONTO = "America/Toronto"


def at_2am(day: date) -> datetime:
    """02:00 in Toronto on `day` (EDT through 2026-11-01), when its nightly sync runs."""
    return datetime(day.year, day.month, day.day, 6, tzinfo=ZoneInfo("UTC"))


@dataclasses.dataclass(frozen=True)
class Bank:
    business_id: uuid.UUID
    connection_id: uuid.UUID
    token: str


def new_business() -> uuid.UUID:
    with get_sessionmaker()() as session:
        business = accounts_repository.insert_business(
            session,
            name=f"Labels {uuid.uuid4().hex[:6]}",
            province="ON",
            time_zone=TORONTO,
        )
        session.commit()
        return business.id


def new_bank(business_id: uuid.UUID, accounts: Sequence[PlaidAccount]) -> Bank:
    token = f"access-sandbox-labels-{uuid.uuid4().hex}"
    with get_sessionmaker()() as session:
        connection = repository.insert_connection(
            session,
            business_id=business_id,
            provider_item_id=f"item-{uuid.uuid4().hex}",
            provider_institution_id=f"ins_{uuid.uuid4().hex[:8]}",
            institution_name="TD Canada Trust",
            access_token_ciphertext=encrypt_access_token(token),
        )
        repository.insert_accounts(
            session,
            [
                service._account(
                    a, business_id=business_id, connection_id=connection.id
                )
                for a in accounts
            ],
        )
        connection.created_at = CREATED_AT
        session.commit()
        return Bank(business_id, connection.id, token)


def will_add(fake: NightlyFake, bank: Bank, added: Sequence[PlaidTransaction]) -> None:
    """The bank's next sync adds `added`."""
    fake.updates.setdefault(bank.token, []).append(page([], added=added))


def night(fake: NightlyFake, day: date) -> None:
    fake.clock = at_2am(day)
    run_due(at_2am(day))


def transfer_out(account: PlaidAccount, detailed: str) -> PlaidTransaction:
    return move(
        "out",
        account,
        -400_000,
        date(2026, 10, 9),
        category="TRANSFER_OUT",
        detailed=detailed,
    )


@pytest.fixture(autouse=True)
def _unique_transaction_ids() -> None:
    sync_tests._run["id"] = uuid.uuid4().hex[:12]


@pytest.fixture(autouse=True)
def _empty_bank_tables() -> None:
    with get_sessionmaker()() as session:
        session.execute(
            text("TRUNCATE bank_transactions, bank_accounts, bank_connections")
        )
        session.commit()


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> NightlyFake:
    plaid = NightlyFake()
    monkeypatch.setattr(nightly, "get_plaid_client", lambda: plaid)
    return plaid


@pytest.fixture
def published() -> Iterator[list[events.Event]]:
    seen: list[events.Event] = []
    events.subscribe("transactions.synced", seen.append)
    yield seen
    events.unsubscribe("transactions.synced", seen.append)


# S3 - a transfer whose other half hasn't arrived is in transit, then normal


@pytest.mark.parametrize(
    ("detailed", "label"),
    [
        ("TRANSFER_OUT_ACCOUNT_TRANSFER", "in_transit"),
        ("TRANSFER_OUT_SAVINGS", "in_transit"),
        ("TRANSFER_OUT_WITHDRAWAL", "normal"),
        ("TRANSFER_OUT_INVESTMENT_AND_RETIREMENT_FUNDS", "normal"),
    ],
)
def test_in_transit_by_category(fake: NightlyFake, detailed: str, label: str) -> None:
    """C14"""
    chq = operating()
    bank = new_bank(new_business(), [chq])
    will_add(fake, bank, [transfer_out(chq, detailed)])

    night(fake, date(2026, 10, 15))

    assert_unpaired(rows(bank.business_id), "out", label)


def test_in_transit_expires(fake: NightlyFake) -> None:
    """C15"""
    chq = operating()
    bank = new_bank(new_business(), [chq])
    will_add(fake, bank, [transfer_out(chq, "TRANSFER_OUT_ACCOUNT_TRANSFER")])

    night(fake, date(2026, 10, 15))
    assert_unpaired(rows(bank.business_id), "out", "in_transit")

    night(fake, date(2026, 10, 16))
    assert_unpaired(rows(bank.business_id), "out", "normal")


def test_in_transit_then_paired(fake: NightlyFake) -> None:
    """C16"""
    chq, sav = operating(), savings()
    bank = new_bank(new_business(), [chq, sav])
    will_add(fake, bank, [transfer_out(chq, "TRANSFER_OUT_ACCOUNT_TRANSFER")])
    night(fake, date(2026, 10, 13))
    assert_unpaired(rows(bank.business_id), "out", "in_transit")

    will_add(fake, bank, [move("in", sav, 400_000, date(2026, 10, 14))])
    night(fake, date(2026, 10, 14))

    assert_paired(rows(bank.business_id), "out", "in", "internal_transfer")


# S4 - labels stay current and consistent through every sync


def test_all_labels_consistent(fake: NightlyFake) -> None:
    """C18"""
    sav, chq, visa, loc = savings(), operating(), card(), credit_line()
    bank = new_bank(new_business(), [sav, chq, visa, loc])
    will_add(
        fake,
        bank,
        [
            move("t-out", sav, -1_000_000, date(2026, 9, 14)),
            move("t-in", chq, 1_000_000, date(2026, 9, 16)),
            move("buy", visa, -8_500, date(2026, 9, 14)),
            move("pay", chq, -245_000, date(2026, 10, 8)),
            move("paid", visa, 245_000, date(2026, 10, 9)),
            move("draw", loc, -1_500_000, date(2026, 9, 14)),
            move("drawn", chq, 1_500_000, date(2026, 9, 15)),
            move("repay", chq, -700_000, date(2026, 9, 21)),
            move("repaid", loc, 700_000, date(2026, 9, 22)),
            transfer_out(chq, "TRANSFER_OUT_ACCOUNT_TRANSFER"),
            move("other", chq, 50_000, date(2026, 9, 14)),
        ],
    )

    night(fake, date(2026, 10, 15))

    found = list(rows(bank.business_id).values())
    by_id = {r.id: r for r in found}
    assert {r.label for r in found} == LABELS
    linked = {r.label for r in found if r.linked_transaction_id is not None}
    assert linked <= {
        "internal_transfer",
        "card_payment",
        "credit_draw",
        "credit_repayment",
    }
    for row in found:
        if row.linked_transaction_id is not None:
            assert by_id[row.linked_transaction_id].linked_transaction_id == row.id


def test_nightly_path_relabels(fake: NightlyFake) -> None:
    """C20, the nightly path"""
    business_id = new_business()
    chq, sav = operating(), savings()
    first = new_bank(business_id, [chq])
    second = new_bank(business_id, [sav])
    will_add(fake, first, [move("in", chq, 1_000_000, date(2026, 10, 13))])
    night(fake, date(2026, 10, 14))
    assert_unpaired(rows(business_id), "in", "normal")

    will_add(fake, second, [move("out", sav, -1_000_000, date(2026, 10, 13))])
    night(fake, date(2026, 10, 15))

    assert_paired(rows(business_id), "out", "in", "internal_transfer")


def test_same_day_resync_unchanged(
    fake: NightlyFake,
    published: list[events.Event],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C24"""
    sav, chq = savings(), operating()
    bank = new_bank(new_business(), [sav, chq])
    will_add(
        fake,
        bank,
        [
            move("out", sav, -1_000_000, date(2026, 9, 14)),
            move("in", chq, 1_000_000, date(2026, 9, 16)),
        ],
    )
    night(fake, date(2026, 10, 14))
    before = labels_and_links(bank.business_id)
    # Make the connection due again on the same local date, 16:00 in Toronto.
    with get_sessionmaker()() as session:
        session.execute(
            update(BankConnection)
            .where(BankConnection.id == bank.connection_id)
            .values(nightly_synced_on=None)
        )
        session.commit()
    published.clear()
    configure_logging()
    capsys.readouterr()

    later = datetime(2026, 10, 14, 20, tzinfo=ZoneInfo("UTC"))
    fake.clock = later
    run_due(later)

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    synced = [line for line in lines if line["event"] == "bank_sync.synced"]
    assert [line["relabeled"] for line in synced] == [0]
    assert published == []
    assert labels_and_links(bank.business_id) == before
    assert before["out"][0] == "internal_transfer"


def labels_and_links(business_id: uuid.UUID) -> dict[str, tuple[str, str | None]]:
    found = rows(business_id)
    names = {r.id: name for name, r in found.items()}
    return {
        name: (
            r.label,
            None if r.linked_transaction_id is None else names[r.linked_transaction_id],
        )
        for name, r in found.items()
    }


def test_relabel_only_publishes(
    fake: NightlyFake, published: list[events.Event]
) -> None:
    """C26, the relabel-only sync"""
    chq = operating()
    bank = new_bank(new_business(), [chq])
    will_add(fake, bank, [transfer_out(chq, "TRANSFER_OUT_ACCOUNT_TRANSFER")])
    night(fake, date(2026, 10, 15))
    published.clear()

    night(fake, date(2026, 10, 16))

    assert published == [
        events.Event(
            name="transactions.synced",
            business_id=bank.business_id,
            payload={
                "connection_id": str(bank.connection_id),
                "added": 0,
                "modified": 0,
                "removed": 0,
                "balances_changed": False,
                "relabeled": 1,
            },
        )
    ]
