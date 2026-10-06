"""Spec 16: transaction labels, through real syncs against Postgres.

Amounts in these tests are our sign, in cents: money in positive, money out negative.
`move` turns one into the Plaid amount the fake reports (Plaid's sign is the opposite).
Claims that depend on the business-local date live in `test_transaction_labels_nightly.py`.
"""

import json
import threading
import tomllib
import uuid
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError

from app import events
from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.bank_sync import repository, service
from app.modules.bank_sync.models import BankTransaction
from app.modules.bank_sync.plaid import (
    PlaidAccount,
    PlaidError,
    PlaidTransaction,
    get_plaid_client,
)
from app.modules.bank_sync.tokens import encrypt_access_token
from tests import test_transaction_sync as sync_tests
from tests.test_bank_connect import connect, plaid_account
from tests.test_businesses import BAYVIEW, HARBOR, Caller, _owner
from tests.test_nightly_sync import NightlyFake
from tests.test_transaction_sync import (
    Connected,
    SyncFake,
    credit_line,
    make_connection,
    page,
    rows,
    sync,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

CORE = Path(__file__).resolve().parents[1]
LABELS = {
    "internal_transfer",
    "in_transit",
    "card_purchase",
    "card_payment",
    "credit_draw",
    "credit_repayment",
    "normal",
}


@pytest.fixture(autouse=True)
def _unique_transaction_ids() -> None:
    # `tx` makes Plaid transaction IDs unique per test through this run ID.
    sync_tests._run["id"] = uuid.uuid4().hex[:12]


@pytest.fixture
def fake() -> Iterator[SyncFake]:
    plaid = SyncFake()
    app.dependency_overrides[get_plaid_client] = lambda: plaid
    yield plaid
    app.dependency_overrides.pop(get_plaid_client, None)


@pytest.fixture
def published() -> Iterator[list[events.Event]]:
    seen: list[events.Event] = []
    events.subscribe("transactions.synced", seen.append)
    yield seen
    events.unsubscribe("transactions.synced", seen.append)


def savings() -> PlaidAccount:
    return plaid_account("Reserve", subtype="savings", mask="0002", current=34300.0)


def operating() -> PlaidAccount:
    return plaid_account("Operating", mask="0001", current=8000.0)


def payroll() -> PlaidAccount:
    return plaid_account("Payroll", mask="0003", current=500.0)


def card() -> PlaidAccount:
    return plaid_account(
        "Business Visa",
        type="credit",
        subtype="credit card",
        mask="0004",
        current=2450.0,
    )


def move(
    key: str, account: PlaidAccount, cents: int, day: date, **kwargs: Any
) -> PlaidTransaction:
    """Transaction `key` of `cents` in our sign (money in positive)."""
    return tx(key, account, -cents / 100, day=day, **kwargs)


def new_owner(body: dict[str, str] = HARBOR) -> tuple[Caller, str]:
    return _owner({**body, "name": f"Labels {uuid.uuid4().hex[:6]}"})


def business(accounts: Sequence[PlaidAccount]) -> Connected:
    """A new business with one connection holding `accounts`."""
    return make_connection(new_owner()[1], accounts)


def sync_once(
    fake: SyncFake,
    c: Connected,
    accounts: Sequence[PlaidAccount],
    added: Sequence[PlaidTransaction],
) -> service.SyncResult:
    fake.script = [page(accounts, added=added)]
    return sync(fake, c)


def assert_paired(
    found: dict[str, BankTransaction], a: str, b: str, label: str
) -> None:
    assert (found[a].label, found[b].label) == (label, label)
    assert found[a].linked_transaction_id == found[b].id
    assert found[b].linked_transaction_id == found[a].id


def assert_unpaired(found: dict[str, BankTransaction], name: str, label: str) -> None:
    assert (found[name].label, found[name].linked_transaction_id) == (label, None)


# S1 - a transfer between the business's own accounts is labelled on both sides


def test_savings_to_checking_paired(fake: SyncFake) -> None:
    """C1"""
    sav, chq = savings(), operating()
    c = business([sav, chq])

    sync_once(
        fake,
        c,
        [sav, chq],
        [
            move("out", sav, -1_000_000, date(2026, 9, 14)),
            move("in", chq, 1_000_000, date(2026, 9, 16)),
        ],
    )

    assert_paired(rows(c.business_id), "out", "in", "internal_transfer")


def test_across_connections_paired(fake: SyncFake) -> None:
    """C2"""
    _, business_id = new_owner()
    sav, chq = savings(), operating()
    a = make_connection(business_id, [sav])
    b = make_connection(business_id, [chq])

    sync_once(fake, a, [sav], [move("out", sav, -1_000_000, date(2026, 9, 14))])
    assert_unpaired(rows(a.business_id), "out", "normal")

    sync_once(fake, b, [chq], [move("in", chq, 1_000_000, date(2026, 9, 16))])
    assert_paired(rows(a.business_id), "out", "in", "internal_transfer")


def test_money_in_first_paired(fake: SyncFake) -> None:
    """C3"""
    sav, chq = savings(), operating()
    c = business([sav, chq])

    sync_once(
        fake,
        c,
        [sav, chq],
        [
            move("out", sav, -300_000, date(2026, 9, 17)),
            move("in", chq, 300_000, date(2026, 9, 15)),
        ],
    )

    assert_paired(rows(c.business_id), "out", "in", "internal_transfer")


@pytest.mark.parametrize(
    ("out_day", "in_day", "paired"),
    [
        (date(2026, 10, 9), date(2026, 10, 15), True),
        (date(2026, 10, 9), date(2026, 10, 16), False),
        (date(2026, 9, 18), date(2026, 9, 23), True),
        (date(2026, 9, 18), date(2026, 9, 24), False),
    ],
)
def test_window_edges(
    fake: SyncFake, out_day: date, in_day: date, paired: bool
) -> None:
    """C4"""
    sav, chq = savings(), operating()
    c = business([sav, chq])

    sync_once(
        fake,
        c,
        [sav, chq],
        [move("out", sav, -200_000, out_day), move("in", chq, 200_000, in_day)],
    )

    found = rows(c.business_id)
    if paired:
        assert_paired(found, "out", "in", "internal_transfer")
    else:
        assert_unpaired(found, "out", "normal")
        assert_unpaired(found, "in", "normal")


@pytest.mark.parametrize(
    "case", ["cent_short", "usd", "same_account", "other_business"]
)
def test_near_misses_not_paired(fake: SyncFake, case: str) -> None:
    """C5"""
    sav, chq = savings(), operating()
    c = business([sav, chq])
    out = move("out", sav, -1_000_000, date(2026, 9, 14))
    other: Connected | None = None
    other_chq = operating()
    if case == "cent_short":
        incoming = move("in", chq, 999_999, date(2026, 9, 14))
    elif case == "usd":
        incoming = move("in", chq, 1_000_000, date(2026, 9, 14), iso="USD")
    elif case == "same_account":
        incoming = move("in", sav, 1_000_000, date(2026, 9, 14))
    else:
        other = make_connection(new_owner(BAYVIEW)[1], [other_chq])
        incoming = move("in", other_chq, 1_000_000, date(2026, 9, 14))

    if other is None:
        sync_once(fake, c, [sav, chq], [out, incoming])
        found = rows(c.business_id)
    else:
        sync_once(fake, other, [other_chq], [incoming])
        sync_once(fake, c, [sav, chq], [out])
        found = {**rows(c.business_id), **rows(other.business_id)}

    assert_unpaired(found, "out", "normal")
    assert_unpaired(found, "in", "normal")


@pytest.mark.parametrize("case", ["fewest_days", "earliest_date", "lowest_id"])
def test_pairing_order(fake: SyncFake, case: str) -> None:
    """C6"""
    sav, chq, pay = savings(), operating(), payroll()
    c = business([sav, chq, pay])
    if case == "fewest_days":
        first, second = date(2026, 9, 17), date(2026, 9, 21)
    elif case == "earliest_date":
        first, second = date(2026, 9, 15), date(2026, 9, 17)
    else:
        first = second = date(2026, 9, 17)

    sync_once(
        fake,
        c,
        [sav, chq, pay],
        [
            move("out", sav, -500_000, date(2026, 9, 16)),
            move("a", chq, 500_000, first),
            move("b", pay, 500_000, second),
        ],
    )

    found = rows(c.business_id)
    if case == "lowest_id":
        winner = min(("a", "b"), key=lambda name: found[name].id)
    else:
        winner = "a"
    loser = "b" if winner == "a" else "a"
    assert_paired(found, "out", winner, "internal_transfer")
    assert_unpaired(found, loser, "normal")
    assert sum(r.linked_transaction_id is not None for r in found.values()) == 2


# S2 - card and credit line activity is labelled for what it is


def test_card_purchase_labelled(fake: SyncFake) -> None:
    """C7"""
    visa = card()
    c = business([visa])

    sync_once(fake, c, [visa], [move("buy", visa, -8_500, date(2026, 9, 14))])

    assert_unpaired(rows(c.business_id), "buy", "card_purchase")


def test_card_payment_paired(fake: SyncFake) -> None:
    """C8"""
    chq, visa = operating(), card()
    c = business([chq, visa])

    sync_once(
        fake,
        c,
        [chq, visa],
        [
            move("pay", chq, -245_000, date(2026, 10, 8)),
            move("paid", visa, 245_000, date(2026, 10, 9)),
        ],
    )

    assert_paired(rows(c.business_id), "pay", "paid", "card_payment")


@pytest.mark.parametrize(
    ("category", "label"),
    [
        ("LOAN_PAYMENTS", "card_payment"),
        ("TRANSFER_IN", "card_payment"),
        (None, "card_payment"),
        ("GENERAL_MERCHANDISE", "card_purchase"),
    ],
)
def test_card_credit_by_category(
    fake: SyncFake, category: str | None, label: str
) -> None:
    """C9"""
    visa = card()
    c = business([visa])

    sync_once(
        fake,
        c,
        [visa],
        [move("credit", visa, 12_000, date(2026, 9, 14), category=category)],
    )

    assert_unpaired(rows(c.business_id), "credit", label)


def test_card_payment_unconnected_card(fake: SyncFake) -> None:
    """C10"""
    chq = operating()
    c = business([chq])

    sync_once(
        fake,
        c,
        [chq],
        [
            move(
                "pay",
                chq,
                -60_000,
                date(2026, 9, 14),
                category="LOAN_PAYMENTS",
                detailed="LOAN_PAYMENTS_CREDIT_CARD_PAYMENT",
            )
        ],
    )

    assert_unpaired(rows(c.business_id), "pay", "card_payment")


def test_credit_draw(fake: SyncFake) -> None:
    """C11"""
    loc, chq = credit_line(), operating()
    c = business([loc, chq])
    sync_once(
        fake,
        c,
        [loc, chq],
        [
            move("draw", loc, -1_500_000, date(2026, 9, 14)),
            move("in", chq, 1_500_000, date(2026, 9, 15)),
        ],
    )
    assert_paired(rows(c.business_id), "draw", "in", "credit_draw")

    alone = credit_line()
    d = business([alone])
    sync_once(fake, d, [alone], [move("draw-2", alone, -40_000, date(2026, 9, 14))])
    assert_unpaired(rows(d.business_id), "draw-2", "credit_draw")


def test_credit_repayment(fake: SyncFake) -> None:
    """C12"""
    loc, chq = credit_line(), operating()
    c = business([loc, chq])
    sync_once(
        fake,
        c,
        [loc, chq],
        [
            move("out", chq, -700_000, date(2026, 9, 14)),
            move("repaid", loc, 700_000, date(2026, 9, 15)),
        ],
    )
    assert_paired(rows(c.business_id), "out", "repaid", "credit_repayment")

    alone = credit_line()
    d = business([alone])
    sync_once(fake, d, [alone], [move("repaid-2", alone, 40_000, date(2026, 9, 14))])
    assert_unpaired(rows(d.business_id), "repaid-2", "credit_repayment")


def test_card_beats_credit_line(fake: SyncFake) -> None:
    """C13"""
    loc, visa = credit_line(), card()
    c = business([loc, visa])

    sync_once(
        fake,
        c,
        [loc, visa],
        [
            move("draw", loc, -90_000, date(2026, 9, 14)),
            move("paid", visa, 90_000, date(2026, 9, 15)),
        ],
    )

    assert_paired(rows(c.business_id), "draw", "paid", "card_payment")


@pytest.mark.parametrize("case", ["purchase", "refund", "payment"])
def test_card_side_pairing(fake: SyncFake, case: str) -> None:
    """C29"""
    visa, chq = card(), operating()
    c = business([visa, chq])
    if case == "purchase":
        added = [
            move(
                "card", visa, -50_000, date(2026, 9, 14), category="GENERAL_MERCHANDISE"
            ),
            move("cash", chq, 50_000, date(2026, 9, 15), category="INCOME"),
        ]
    elif case == "refund":
        added = [
            move(
                "card", visa, 30_000, date(2026, 9, 14), category="GENERAL_MERCHANDISE"
            ),
            move("cash", chq, -30_000, date(2026, 9, 15), category="GENERAL_SERVICES"),
        ]
    else:
        added = [
            move("card", visa, 30_000, date(2026, 9, 15), category="LOAN_PAYMENTS"),
            move("cash", chq, -30_000, date(2026, 9, 14)),
        ]

    sync_once(fake, c, [visa, chq], added)

    found = rows(c.business_id)
    if case == "payment":
        assert_paired(found, "cash", "card", "card_payment")
    else:
        assert_unpaired(found, "card", "card_purchase")
        assert_unpaired(found, "cash", "normal")


# S3 - everything no rule covers is normal


@pytest.mark.parametrize(
    ("cents", "category", "detailed"),
    [
        (50_000, None, None),
        (50_000, "INCOME", "INCOME_OTHER_INCOME"),
        (50_000, "TRANSFER_IN", "TRANSFER_IN_ACCOUNT_TRANSFER"),
        (-50_000, None, None),
        (
            -50_000,
            "GENERAL_MERCHANDISE",
            "GENERAL_MERCHANDISE_OTHER_GENERAL_MERCHANDISE",
        ),
    ],
)
def test_everything_else_normal(
    fake: SyncFake, cents: int, category: str | None, detailed: str | None
) -> None:
    """C17"""
    chq = operating()
    c = business([chq])

    sync_once(
        fake,
        c,
        [chq],
        [
            move(
                "t",
                chq,
                cents,
                date(2026, 9, 14),
                category=category,
                detailed=detailed,
            )
        ],
    )

    assert_unpaired(rows(c.business_id), "t", "normal")


# S4 - labels stay current and consistent through every sync


def three_rows(fake: SyncFake) -> dict[str, BankTransaction]:
    sav, chq = savings(), operating()
    c = business([sav, chq])
    sync_once(
        fake,
        c,
        [sav, chq],
        [
            move("a", sav, -1_000, date(2026, 9, 1)),
            move("b", chq, -2_000, date(2026, 9, 1)),
            move("c", chq, -3_000, date(2026, 9, 1)),
        ],
    )
    return rows(c.business_id)


@pytest.mark.parametrize(
    ("case", "constraint"),
    [
        ("bad_label", "ck_bank_transactions_label"),
        ("link_on_normal", "ck_bank_transactions_linked_label"),
        ("self_link", "ck_bank_transactions_linked_not_self"),
        ("second_link", "uq_bank_transactions_linked_transaction_id"),
    ],
)
def test_constraints_refuse(fake: SyncFake, case: str, constraint: str) -> None:
    """C19"""
    found = three_rows(fake)
    a, b, c = found["a"].id, found["b"].id, found["c"].id

    def set_row(row_id: uuid.UUID, **values: Any) -> Any:
        return (
            update(BankTransaction).where(BankTransaction.id == row_id).values(**values)
        )

    with get_sessionmaker()() as session, pytest.raises(IntegrityError) as excinfo:
        if case == "bad_label":
            session.execute(set_row(a, label="transfer"))
        elif case == "link_on_normal":
            session.execute(set_row(a, linked_transaction_id=b))
        elif case == "self_link":
            session.execute(
                set_row(a, label="internal_transfer", linked_transaction_id=a)
            )
        else:
            session.execute(
                set_row(a, label="internal_transfer", linked_transaction_id=c)
            )
            session.execute(
                set_row(b, label="internal_transfer", linked_transaction_id=c)
            )
        session.flush()

    assert constraint in str(excinfo.value)


@pytest.mark.parametrize("path", ["webhook", "connect"])
def test_every_sync_path_relabels(fake: SyncFake, path: str) -> None:
    """C20 (the nightly path is in test_transaction_labels_nightly.py)"""
    caller, business_id = new_owner()
    chq, sav = operating(), savings()
    stored = make_connection(business_id, [chq])
    sync_once(fake, stored, [chq], [move("in", chq, 1_000_000, date(2026, 9, 16))])
    assert_unpaired(rows(stored.business_id), "in", "normal")

    out = move("out", sav, -1_000_000, date(2026, 9, 14))
    if path == "webhook":
        other = make_connection(business_id, [sav])
        fake.script = [page([sav], added=[out])]
        service.sync_in_background(
            fake, business_id=other.business_id, connection_id=other.connection_id
        )
    else:
        fake.accounts = lambda: [sav]
        fake.script = [page([sav], added=[out])]
        assert connect(caller, business_id).status_code == 201

    assert_paired(rows(stored.business_id), "out", "in", "internal_transfer")


def test_relabel_same_transaction(fake: SyncFake) -> None:
    """C21"""
    _, business_id = new_owner()
    sav, chq = savings(), operating()
    a = make_connection(business_id, [sav])
    b = make_connection(business_id, [chq])
    sync_once(fake, a, [sav], [move("out", sav, -1_000_000, date(2026, 9, 14))])
    sync_once(fake, b, [chq], [move("in", chq, 1_000_000, date(2026, 9, 16))])

    found = rows(a.business_id)
    with get_sessionmaker()() as session:
        xmins = dict(
            session.execute(
                text(
                    "SELECT id, xmin::text FROM bank_transactions"
                    " WHERE id IN (:out, :incoming)"
                ),
                {"out": found["out"].id, "incoming": found["in"].id},
            ).all()
        )
    assert found["out"].label == "internal_transfer"
    assert xmins[found["out"].id] == xmins[found["in"].id]


def test_failed_sync_keeps_labels(fake: SyncFake) -> None:
    """C22"""
    sav, chq = savings(), operating()
    c = business([sav, chq])
    sync_once(
        fake,
        c,
        [sav, chq],
        [
            move("out", sav, -1_000_000, date(2026, 9, 14)),
            move("in", chq, 1_000_000, date(2026, 9, 16)),
        ],
    )
    stranger = operating()
    fake.script = [
        page([sav, chq], removed=["out"], cursor="c2", more=True),
        page([sav, chq], added=[move("x", stranger, -100, date(2026, 9, 20))]),
    ]

    with pytest.raises(PlaidError):
        sync(fake, c)

    assert_paired(rows(c.business_id), "out", "in", "internal_transfer")


def test_removed_half_relabels(fake: SyncFake) -> None:
    """C23"""
    sav, chq = savings(), operating()
    c = business([sav, chq])
    sync_once(
        fake,
        c,
        [sav, chq],
        [
            move("out", sav, -1_000_000, date(2026, 9, 14)),
            move("in", chq, 1_000_000, date(2026, 9, 16)),
        ],
    )
    fake.script = [page([sav, chq], removed=["out"], cursor="c2")]
    sync(fake, c)
    found = rows(c.business_id)
    assert "out" not in found
    assert_unpaired(found, "in", "normal")

    sav2, chq2 = savings(), operating()
    d = business([sav2, chq2])
    sync_once(
        fake,
        d,
        [sav2, chq2],
        [
            move("p", sav2, -1_000_000, date(2026, 9, 14), pending=True),
            move("in-2", chq2, 1_000_000, date(2026, 9, 15)),
        ],
    )
    assert_paired(rows(d.business_id), "p", "in-2", "internal_transfer")
    fake.script = [
        page(
            [sav2, chq2],
            added=[move("posted", sav2, -1_000_000, date(2026, 9, 15), pending_id="p")],
            cursor="c2",
        )
    ]
    sync(fake, d)
    found = rows(d.business_id)
    assert "p" not in found
    assert_paired(found, "posted", "in-2", "internal_transfer")


def test_concurrent_syncs_pair() -> None:
    """C25"""
    _, business_id = new_owner()
    sav, chq = savings(), operating()
    plaid = NightlyFake()
    a = connection_with_token(business_id, [sav], "access-sandbox-labels-a")
    b = connection_with_token(business_id, [chq], "access-sandbox-labels-b")
    plaid.updates = {
        "access-sandbox-labels-a": [
            page([sav], added=[move("out", sav, -1_000_000, date(2026, 9, 14))])
        ],
        "access-sandbox-labels-b": [
            page([chq], added=[move("in", chq, 1_000_000, date(2026, 9, 15))])
        ],
    }
    plaid.hold = threading.Event()
    errors: list[BaseException] = []

    def run(c: Connected) -> None:
        try:
            with get_sessionmaker()() as session:
                service.sync_connection(
                    session,
                    plaid,
                    business_id=c.business_id,
                    connection_id=c.connection_id,
                )
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion
            errors.append(exc)

    first = threading.Thread(target=run, args=(a,))
    first.start()
    assert plaid.entered.wait(10)
    second = threading.Thread(target=run, args=(b,))
    second.start()
    for _ in range(100):
        if len(plaid.synced) == 2:
            break
        threading.Event().wait(0.1)
    started = len(plaid.synced)
    plaid.hold.set()
    first.join(30)
    second.join(30)

    assert started == 2
    assert errors == []
    assert_paired(rows(a.business_id), "out", "in", "internal_transfer")


def connection_with_token(
    business_id: str, accounts: Sequence[PlaidAccount], token: str
) -> Connected:
    bid = uuid.UUID(business_id)
    with get_sessionmaker()() as session:
        connection = repository.insert_connection(
            session,
            business_id=bid,
            plaid_item_id=f"item-{uuid.uuid4().hex}",
            plaid_institution_id=f"ins_{uuid.uuid4().hex[:8]}",
            institution_name="TD Canada Trust",
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
        return Connected(bid, connection.id, connection.plaid_item_id)


def test_event_counts_relabeled(fake: SyncFake, published: list[events.Event]) -> None:
    """C26 (the relabel-only sync is in test_transaction_labels_nightly.py)"""
    sav, chq = savings(), operating()
    c = business([sav, chq])

    sync_once(
        fake,
        c,
        [sav, chq],
        [
            move("out", sav, -1_000_000, date(2026, 9, 14)),
            move("in", chq, 1_000_000, date(2026, 9, 16)),
        ],
    )

    assert published == [
        events.Event(
            name="transactions.synced",
            business_id=c.business_id,
            payload={
                "connection_id": str(c.connection_id),
                "added": 2,
                "modified": 0,
                "removed": 0,
                "balances_changed": False,
                "relabeled": 2,
            },
        )
    ]


def test_log_relabeled_no_details(
    fake: SyncFake, capsys: pytest.CaptureFixture[str]
) -> None:
    """C27"""
    sav, chq = savings(), operating()
    c = business([sav, chq])
    configure_logging()
    capsys.readouterr()

    sync_once(
        fake,
        c,
        [sav, chq],
        [
            move(
                "out",
                sav,
                -1_000_000,
                date(2026, 9, 14),
                name="Online transfer to Operating",
                counterparties=("Reserve Account",),
            ),
            move(
                "in",
                chq,
                1_000_000,
                date(2026, 9, 16),
                name="Online transfer from Reserve",
                merchant="Reserve Account",
            ),
        ],
    )

    out = capsys.readouterr()
    logs = out.out + out.err
    lines = [json.loads(line) for line in out.out.splitlines()]
    synced = [line for line in lines if line["event"] == "bank_sync.synced"]
    assert [line["relabeled"] for line in synced] == [2]
    leaks = [
        "Online transfer to Operating",
        "Online transfer from Reserve",
        "Reserve Account",
        "10000",
    ]
    assert [v for v in leaks if v in logs] == []


def test_holidays_dependency() -> None:
    """C28"""
    project = tomllib.loads((CORE / "pyproject.toml").read_text(encoding="utf-8"))
    names = {
        dep.split(">")[0].split("=")[0].split("<")[0].strip()
        for dep in project["project"]["dependencies"]
    }
    lock = tomllib.loads((CORE / "uv.lock").read_text(encoding="utf-8"))
    locked = {package["name"] for package in lock["package"]}

    assert "holidays" in names
    assert "holidays" in locked


def test_labels_are_the_seven() -> None:
    """The model's label set is exactly door 1's."""
    from app.modules.bank_sync.models import TRANSACTION_LABELS

    assert set(TRANSACTION_LABELS) == LABELS
