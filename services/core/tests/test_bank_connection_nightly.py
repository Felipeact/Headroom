"""Spec 17: the nightly sync records a login problem, and clears it when a retry works.

Runs against a database of its own, like spec 15's nightly tests, because `run_due` syncs
every connection in the database.
"""

import pytest
from sqlalchemy import select, text

from app.db import get_sessionmaker
from app.jobs import nightly
from app.modules.bank_sync.models import BankConnection
from tests.test_nightly_sync import TORONTO, Conn, NightlyFake, new_connection, run, utc

pytestmark = pytest.mark.usefixtures("isolated_database")


def stored(c: Conn) -> BankConnection:
    with get_sessionmaker()() as session:
        found = session.scalars(
            select(BankConnection).where(BankConnection.id == c.connection_id)
        ).one()
        session.expunge_all()
    return found


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


def test_nightly_login_error(fake: NightlyFake) -> None:
    """C20."""
    c = new_connection(TORONTO)
    fake.fail_times[c.token] = 1

    run(fake, utc(2026, 10, 6, 6))

    failed = stored(c)
    assert failed.login_required is True
    assert failed.nightly_attempts == 1
    assert failed.next_nightly_attempt_at == utc(2026, 10, 6, 7)
    assert failed.last_synced_at is None

    run(fake, utc(2026, 10, 6, 7))

    repaired = stored(c)
    assert repaired.login_required is False
    assert repaired.last_synced_at == utc(2026, 10, 6, 7)
