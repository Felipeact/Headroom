"""Spec 15: `python -m app.jobs.run_due`, the command Railway runs every hour.

Like `test_nightly_sync.py`, this runs against a database of its own, because the
nightly job syncs every connection it finds.
"""

import json
import os
import subprocess
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

import app.monitoring
from app import events, jobs, subscriptions
from app.db import get_engine, get_sessionmaker
from app.jobs import nightly
from app.jobs.run_due import main, run_due
from app.log import configure_logging
from app.main import app as api
from app.modules.bank_sync.models import BankConnection, BankTransaction
from app.settings import get_settings
from tests.test_nightly_sync import (
    TORONTO,
    Conn,
    NightlyFake,
    login_required,
    new_connection,
    utc,
)
from tests.test_sentry import FakeTransport, reset_sentry
from tests.test_transaction_sync import page, tx

pytestmark = pytest.mark.usefixtures("isolated_database")

CORE = Path(__file__).resolve().parents[1]
DSN = "https://public@o0.ingest.sentry.io/0"


@pytest.fixture(autouse=True)
def _empty_bank_tables_and_no_sentry(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # .env.local may hold a real DSN; these runs must not report to it.
    monkeypatch.setenv("SENTRY_DSN", "")
    get_settings.cache_clear()
    with get_sessionmaker()() as session:
        session.execute(
            text("TRUNCATE bank_transactions, bank_accounts, bank_connections")
        )
        session.commit()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> NightlyFake:
    plaid = NightlyFake()
    monkeypatch.setattr(nightly, "get_plaid_client", lambda: plaid)
    return plaid


@pytest.fixture
def fresh_subscriptions(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`app.subscriptions` with nothing registered yet; unsubscribes what tests add."""
    registered: set[tuple[str, events.Handler]] = set()
    monkeypatch.setattr(subscriptions, "_registered", registered)
    yield
    for name, handler in list(registered):
        events.unsubscribe(name, handler)


def due_now() -> Conn:
    """A Toronto connection connected three days ago, so it is due at any time today."""
    return new_connection(TORONTO, created_at=datetime.now(UTC) - timedelta(days=3))


def json_lines(output: str) -> list[dict[str, Any]]:
    lines = []
    for line in output.splitlines():
        try:
            lines.append(json.loads(line))
        except ValueError:
            continue
    return lines


def run_module(**env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "python", "-m", "app.jobs.run_due"],
        cwd=CORE,
        env={**os.environ, "SENTRY_DSN": "", **env},
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


# S4 - the command does its work, reports it, and exits


def test_exit_zero(fake: NightlyFake, isolated_database: str) -> None:
    c = due_now()
    fake.raises[c.token] = login_required()

    assert main() == 0
    assert len(fake.times(c.token)) == 1

    with get_sessionmaker()() as session:
        session.execute(
            text("TRUNCATE bank_transactions, bank_accounts, bank_connections")
        )
        session.commit()
    result = run_module(DATABASE_URL=isolated_database)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "jobs.run_finished" in [
        line.get("event") for line in json_lines(result.stdout)
    ]


def test_exit_one_when_runner_cannot_start() -> None:
    unreachable = run_module(
        DATABASE_URL="postgresql+psycopg://headroom:pw-secret@127.0.0.1:1/none"
    )
    invalid = run_module(TOKEN_ENCRYPTION_KEYS="not-a-key")

    for result, secret in ((unreachable, "pw-secret"), (invalid, "not-a-key")):
        assert result.returncode == 1, result.stdout + result.stderr
        failed = [
            line
            for line in json_lines(result.stdout)
            if line.get("event") == "jobs.run_failed"
        ]
        assert len(failed) == 1
        assert failed[0]["error_type"]
        assert secret not in result.stdout + result.stderr


def test_failing_job_does_not_stop_others(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ran: list[datetime] = []

    def raising_job(now: datetime) -> dict[str, int]:
        raise ValueError("job-secret")

    def recording_job(now: datetime) -> dict[str, int]:
        ran.append(now)
        return {}

    monkeypatch.setattr(jobs, "JOBS", (raising_job, recording_job))

    assert main() == 0

    assert len(ran) == 1
    failed = [
        line
        for line in json_lines(capsys.readouterr().out)
        if line.get("event") == "jobs.job_failed"
    ]
    assert [(f["job"], f["error_type"]) for f in failed] == [
        ("raising_job", "ValueError")
    ]


def mixed_run(fake: NightlyFake, *, other_failure: bool) -> list[Conn]:
    """Due connections that sync, fail at Plaid, are held locked, and (optionally) fail
    with a non-Plaid error, in that order."""
    synced = new_connection(TORONTO)
    fake.updates[synced.token] = [
        page(
            [synced.account],
            added=[tx("secret-tx", synced.account, name="Coffee secret-name")],
            cursor="m1",
        )
    ]
    plaid_failed = new_connection(TORONTO)
    fake.raises[plaid_failed.token] = login_required()
    conns = [synced, plaid_failed, new_connection(TORONTO)]
    if other_failure:
        other_failed = new_connection(TORONTO)
        fake.raises[other_failed.token] = RuntimeError("boom-secret")
        conns.append(other_failed)
    return conns


def run_holding_lock(locked: Conn, fake: NightlyFake, now: datetime) -> None:
    holder = get_sessionmaker()()
    try:
        holder.execute(
            select(BankConnection)
            .where(BankConnection.id == locked.connection_id)
            .with_for_update()
        ).one()
        fake.clock = now
        run_due(now)
    finally:
        holder.commit()
        holder.close()


def test_run_finished_counts(
    fake: NightlyFake, capsys: pytest.CaptureFixture[str]
) -> None:
    _, plaid_failed, locked = mixed_run(fake, other_failure=False)
    configure_logging()
    capsys.readouterr()

    run_holding_lock(locked, fake, utc(2026, 10, 20, 6))

    lines = json_lines(capsys.readouterr().out)
    finished = [line for line in lines if line.get("event") == "jobs.run_finished"]
    assert len(finished) == 1
    assert {
        k: finished[0][k] for k in ("due", "synced", "failed", "skipped_locked")
    } == {
        "due": 3,
        "synced": 1,
        "failed": 1,
        "skipped_locked": 1,
    }
    failed = [line for line in lines if line.get("event") == "bank_sync.sync_failed"]
    assert [
        (f["connection_id"], f["error_type"], f["error_code"], f["request_id"])
        for f in failed
    ] == [
        (str(plaid_failed.connection_id), "ITEM_ERROR", "ITEM_LOGIN_REQUIRED", "req-n1")
    ]


def test_no_secrets_in_job_logs(
    fake: NightlyFake, capsys: pytest.CaptureFixture[str]
) -> None:
    conns = mixed_run(fake, other_failure=True)
    locked, other_failed = conns[2], conns[3]
    configure_logging()
    capsys.readouterr()

    run_holding_lock(locked, fake, utc(2026, 10, 20, 6))

    out = capsys.readouterr()
    logs = out.out + out.err
    leaks = [c.token for c in conns] + ["boom-secret", "secret-name"]
    assert [value for value in leaks if value in logs] == []
    other = [
        line
        for line in json_lines(out.out)
        if line.get("event") == "bank_sync.sync_failed"
        and line["connection_id"] == str(other_failed.connection_id)
    ]
    assert len(other) == 1
    assert other[0]["error_type"] == "RuntimeError"
    assert "error_code" not in other[0]
    assert "request_id" not in other[0]


def test_engine_disposed(fake: NightlyFake) -> None:
    due_now()

    assert main() == 0

    assert get_engine().pool.checkedin() == 0


def test_main_sets_up_before_jobs(
    monkeypatch: pytest.MonkeyPatch, fresh_subscriptions: None
) -> None:
    transport = FakeTransport()
    real_init: Callable[..., Any] = sentry_sdk.init

    def init_with_fake_transport(*args: Any, **kwargs: Any) -> Any:
        return real_init(*args, transport=transport, **kwargs)

    monkeypatch.setattr(app.monitoring.sentry_sdk, "init", init_with_fake_transport)
    heard: list[events.Event] = []
    probe = f"probe.{uuid.uuid4().hex}"
    monkeypatch.setattr(subscriptions, "SUBSCRIPTIONS", ((probe, heard.append),))
    seen: dict[str, bool] = {}

    def setup_probe(now: datetime) -> dict[str, int]:
        seen["sentry"] = sentry_sdk.get_client().is_active()
        events.publish(events.Event(name=probe, business_id=uuid.uuid4(), payload={}))
        seen["registered"] = len(heard) == 1
        return {}

    monkeypatch.setattr(jobs, "JOBS", (setup_probe,))
    try:
        monkeypatch.setenv("SENTRY_DSN", DSN)
        get_settings.cache_clear()
        assert main() == 0
        assert seen == {"sentry": True, "registered": True}
    finally:
        reset_sentry()

    monkeypatch.setenv("SENTRY_DSN", "")
    get_settings.cache_clear()
    assert main() == 0
    assert seen["sentry"] is False


def test_subscriptions_reach_job_events(
    fake: NightlyFake, monkeypatch: pytest.MonkeyPatch, fresh_subscriptions: None
) -> None:
    c = due_now()
    fake.updates[c.token] = [
        page([c.account], added=[tx("heard", c.account)], cursor="h1")
    ]
    heard: list[tuple[events.Event, int]] = []

    def recorder(event: events.Event) -> None:
        with get_sessionmaker()() as session:
            stored = session.scalar(
                select(func.count())
                .select_from(BankTransaction)
                .where(BankTransaction.business_id == event.business_id)
            )
        heard.append((event, stored or 0))

    monkeypatch.setattr(
        subscriptions, "SUBSCRIPTIONS", (("transactions.synced", recorder),)
    )

    # The jobs process: main() registers, and the nightly sync publishes after commit.
    assert main() == 0
    assert [(e.name, e.business_id, n) for e, n in heard] == [
        ("transactions.synced", c.business_id, 1)
    ]

    # The API process: the lifespan registers the same handlers.
    events.unsubscribe("transactions.synced", recorder)
    subscriptions._registered.clear()
    heard.clear()
    with TestClient(api):
        events.publish(
            events.Event(
                name="transactions.synced", business_id=c.business_id, payload={}
            )
        )
    assert len(heard) == 1

    # A second register() subscribes nothing more.
    heard.clear()
    subscriptions.register()
    subscriptions.register()
    events.publish(
        events.Event(name="transactions.synced", business_id=c.business_id, payload={})
    )
    assert len(heard) == 1


def test_jobs_registered() -> None:
    """Spec 22 ACC-11: the accuracy job runs every hour, after the nightly sync."""
    from app.jobs.forecast_accuracy import forecast_accuracy

    assert jobs.JOBS == (nightly.nightly_bank_sync, forecast_accuracy)
