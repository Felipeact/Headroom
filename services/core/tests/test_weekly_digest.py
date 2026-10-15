"""Spec 30: the weekly digest job, from the clock to the delivery (C1-C11, C15-C22, C29, C30).

The job reads every business in its database, so the module has a database of its own.
Each planting helper first clears every forecast, so a business left by an earlier test
has none and is skipped. Times are UTC, as the job receives them: on Monday 2026-10-26
Toronto is on EDT (UTC-4), Vancouver on PDT (UTC-7) and St. John's on NDT (UTC-2:30).
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete, select, update

from app import jobs, subscriptions
from app.db import get_sessionmaker
from app.jobs.run_due import run_due
from app.jobs.weekly_digest import weekly_digest
from app.log import configure_logging
from app.modules.accounts import repository as accounts_repository
from app.modules.accounts.models import Business
from app.modules.alerts.models import Alert, AlertFix, AlertItem
from app.modules.bank_sync.models import BankAccount
from app.modules.forecasting.models import (
    ExpectedPayment,
    ForecastPin,
    ForecastSnapshot,
    ForecastWeek,
    MinimumBalance,
)
from app.modules.notifications import service as notifications_service
from app.modules.notifications.models import EmailDelivery
from tests.alert_email_support import DANA, send_sample
from tests.email_support import Mail, log_lines
from tests.test_expected_payments_api import owner_business

pytestmark = pytest.mark.usefixtures("isolated_database")

SUBJECT = "Your cash for the next 13 weeks"
MONDAY = date(2026, 10, 26)
LAST_MONDAY = date(2026, 10, 19)
TORONTO = "America/Toronto"
VANCOUVER = "America/Vancouver"
ST_JOHNS = "America/St_Johns"


def utc(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


TORONTO_8AM = utc(10, 26, 12)


@dataclass
class Biz:
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    owner_sub: str


def flat(value: int, *, week: int = 3, low: int | None = None) -> list[int]:
    """13 end-of-week balances at `value`, with `low` in the given week when set."""
    ends = [value] * 13
    if low is not None:
        ends[week - 1] = low
    return ends


def plant_forecast(
    business_id: uuid.UUID,
    first_monday: date,
    *,
    opening: int,
    ends: list[int],
    computed_at: datetime,
    pin: date | None = None,
) -> uuid.UUID:
    snapshot = ForecastSnapshot(
        id=uuid.uuid4(),
        business_id=business_id,
        inputs_sha256=uuid.uuid4().hex * 2,
        strategy="recurring_pattern",
        as_of=first_monday - timedelta(days=2),
        currency="CAD",
        opening_balance_cents=opening,
        last_computed_at=computed_at,
    )
    with get_sessionmaker()() as session:
        session.add(snapshot)
        session.flush()
        session.add_all(
            ForecastWeek(
                snapshot_id=snapshot.id,
                number=n,
                starts_on=first_monday + timedelta(weeks=n - 1),
                end_balance_cents=end,
                low_cents=end,
                high_cents=end,
                money_in_cents=0,
                money_out_cents=0,
            )
            for n, end in enumerate(ends, 1)
        )
        if pin is not None:
            session.add(
                ForecastPin(
                    business_id=business_id, week_start=pin, snapshot_id=snapshot.id
                )
            )
        session.commit()
    return snapshot.id


def wipe_forecasts() -> None:
    with get_sessionmaker()() as session:
        session.execute(delete(ForecastSnapshot))
        session.commit()


def business(
    mail: Mail,
    *,
    name: str = "Digest",
    zone: str = TORONTO,
    minimum: int | None = 500000,
    forecast: bool = True,
    opening: int = 4230000,
    ends: list[int] | None = None,
) -> Biz:
    """A business with one owner in the fake Clerk, a minimum and a forecast."""
    wipe_forecasts()
    owner, business_id = owner_business(name)
    found = uuid.UUID(business_id)
    with get_sessionmaker()() as session:
        session.execute(
            update(Business).where(Business.id == found).values(time_zone=zone)
        )
        row = session.get(Business, found)
        assert row is not None
        found_name = row.name
        if minimum is not None:
            session.add(
                MinimumBalance(
                    business_id=found,
                    amount_cents=minimum,
                    currency="CAD",
                    updated_by=owner.id,
                )
            )
        session.commit()
    mail.clerk.set(owner.sub, f"{owner.sub}@example.test", "Dana")
    if forecast:
        plant_forecast(
            found,
            MONDAY,
            opening=opening,
            ends=ends or flat(620000, low=315000),
            computed_at=utc(10, 24, 10),
        )
    return Biz(id=found, name=found_name, owner_id=owner.id, owner_sub=owner.sub)


def second_owner(mail: Mail, biz: Biz, email: str) -> uuid.UUID:
    user_id = mail.user(email)
    with get_sessionmaker()() as session:
        accounts_repository.insert_membership(
            session, business_id=biz.id, user_id=user_id, role="owner"
        )
        session.commit()
    return user_id


def digests(business_id: uuid.UUID | None = None) -> list[EmailDelivery]:
    with get_sessionmaker()() as session:
        query = (
            select(EmailDelivery)
            .where(EmailDelivery.kind == "weekly_digest")
            .order_by(EmailDelivery.created_at, EmailDelivery.user_id)
        )
        if business_id is not None:
            query = query.where(EmailDelivery.business_id == business_id)
        rows = list(session.scalars(query))
        session.expunge_all()
    return rows


def digest_sends(mail: Mail) -> list[Any]:
    return [e for e in mail.sender.sent if e.subject == SUBJECT]


def plant_alert(
    biz: Biz,
    *,
    state: str = "open",
    starts_on: date = date(2026, 11, 9),
    fixes: int = 3,
    minimum: int = 500000,
    low: int = 315000,
) -> uuid.UUID:
    alert_id = uuid.uuid4()
    now = utc(10, 24, 10)
    with get_sessionmaker()() as session:
        session.add(
            Alert(
                id=alert_id,
                business_id=biz.id,
                state=state,
                starts_on=starts_on,
                ends_on=starts_on + timedelta(days=6),
                lowest_week_starts_on=starts_on,
                lowest_balance_cents=low,
                minimum_cents=minimum,
                shortfall_cents=minimum - low,
                notified_shortfall_cents=minimum - low,
                currency="CAD",
                snapshot_id=uuid.uuid4(),
                created_at=now,
                updated_at=now,
                dismissed_at=now if state == "dismissed" else None,
                resolved_at=None,
            )
        )
        session.flush()
        session.add_all(
            AlertFix(
                alert_id=alert_id,
                position=n,
                kind="financing",
                amount_cents=100000,
                currency="CAD",
                date=starts_on,
                new_lowest_balance_cents=low + 100000,
            )
            for n in range(fixes)
        )
        session.commit()
    return alert_id


def plant_payment(
    biz: Biz,
    description: str,
    amount: int,
    day: date,
    created_at: datetime,
) -> None:
    with get_sessionmaker()() as session:
        session.add(
            ExpectedPayment(
                business_id=biz.id,
                account_id=uuid.uuid4(),
                description=description,
                amount_cents=amount,
                currency="CAD",
                date=day,
                repeats=None,
                created_at=created_at,
                updated_at=created_at,
            )
        )
        session.commit()


def params_of(biz: Biz) -> dict[str, Any]:
    (row,) = digests(biz.id)
    return json.loads(json.dumps(row.params))


def test_emails_each_owner(mail: Mail) -> None:
    """C1."""
    biz = business(mail)
    second = second_owner(mail, biz, "sam@example.test")
    weekly_digest(TORONTO_8AM)
    rows = digests(biz.id)
    assert {r.user_id for r in rows} == {biz.owner_id, second}
    for row in rows:
        assert row.kind == "weekly_digest"
        assert row.template == "weekly_digest"
        assert row.dedup_key == f"weekly_digest:{biz.id}:2026-10-26"
        assert row.reason == (
            f"You're getting this email because you're an owner of {biz.name}"
            " on Headroom."
        )
        assert row.state == "sent"
    assert sorted(e.to for e in digest_sends(mail)) == sorted(
        [f"{biz.owner_sub}@example.test", "sam@example.test"]
    )


@pytest.mark.parametrize(
    "now",
    [
        utc(10, 26, 11, 59),
        utc(10, 26, 13, 0),
        utc(10, 25, 12, 30),
        utc(10, 27, 12, 0),
    ],
)
def test_only_the_eight_o_clock_hour_outside(mail: Mail, now: datetime) -> None:
    """C2: 07:59, 09:00, Sunday 08:30 and Tuesday 08:00 local send nothing."""
    biz = business(mail)
    assert weekly_digest(now) == {"digests_requested": 0, "digests_failed": 0}
    assert digests(biz.id) == []


@pytest.mark.parametrize("now", [utc(10, 26, 12, 0), utc(10, 26, 12, 59)])
def test_only_the_eight_o_clock_hour(mail: Mail, now: datetime) -> None:
    """C2: 08:00 and 08:59 local send."""
    biz = business(mail)
    weekly_digest(now)
    assert len(digests(biz.id)) == 1


def three_zones(mail: Mail) -> dict[str, Biz]:
    first = business(mail, name="NL", zone=ST_JOHNS)
    others = {
        TORONTO: business(mail, name="ON", zone=TORONTO),
        VANCOUVER: business(mail, name="BC", zone=VANCOUVER),
    }
    # Each helper call clears forecasts: plant them again for all three.
    found = {ST_JOHNS: first, **others}
    for biz in found.values():
        plant_forecast(
            biz.id,
            MONDAY,
            opening=4230000,
            ends=flat(620000, low=315000),
            computed_at=utc(10, 24, 10),
        )
    return found


def due(found: dict[str, Biz]) -> set[str]:
    return {zone for zone, biz in found.items() if digests(biz.id)}


def test_newfoundland_half_hour(mail: Mail) -> None:
    """C3: 08:30 NDT, then after the clocks change 07:30 NST does not send."""
    found = three_zones(mail)
    weekly_digest(utc(10, 26, 11, 0))
    assert due(found) == {ST_JOHNS}
    weekly_digest(utc(11, 2, 11, 0))
    assert len(digests(found[ST_JOHNS].id)) == 1
    weekly_digest(utc(11, 2, 12, 0))
    keys = sorted(r.dedup_key for r in digests(found[ST_JOHNS].id))
    assert keys == [
        f"weekly_digest:{found[ST_JOHNS].id}:2026-10-26",
        f"weekly_digest:{found[ST_JOHNS].id}:2026-11-02",
    ]


def test_eastern_and_pacific(mail: Mail) -> None:
    """C4."""
    found = three_zones(mail)
    weekly_digest(utc(10, 26, 12, 0))
    assert due(found) == {TORONTO}
    weekly_digest(utc(10, 26, 15, 0))
    assert due(found) == {TORONTO, VANCOUVER}


def test_same_hour_twice(mail: Mail) -> None:
    """C5."""
    biz = business(mail)
    weekly_digest(TORONTO_8AM)
    weekly_digest(TORONTO_8AM)
    weekly_digest(utc(10, 26, 12, 30))
    assert len(digests(biz.id)) == 1
    assert len(digest_sends(mail)) == 1


def test_owner_opted_out(mail: Mail) -> None:
    """C6."""
    biz = business(mail)
    second = second_owner(mail, biz, "sam@example.test")
    mail.set_preferences(biz.owner_id, alerts=True, weekly_digest=False)
    weekly_digest(TORONTO_8AM)
    by_user = {r.user_id: r for r in digests(biz.id)}
    assert by_user[biz.owner_id].state == "skipped"
    assert by_user[second].state == "sent"
    assert [e.to for e in digest_sends(mail)] == ["sam@example.test"]


def test_alerts_off_still_gets_the_digest(mail: Mail) -> None:
    """C6: only alert emails turned off."""
    biz = business(mail)
    mail.set_preferences(biz.owner_id, alerts=False, weekly_digest=True)
    weekly_digest(TORONTO_8AM)
    (row,) = digests(biz.id)
    assert row.state == "sent"


def test_only_this_business_owners(mail: Mail) -> None:
    """C7."""
    first = business(mail, name="First")
    second = business(mail, name="Second")
    plant_forecast(
        first.id,
        MONDAY,
        opening=4230000,
        ends=flat(620000, low=315000),
        computed_at=utc(10, 24, 10),
    )
    weekly_digest(TORONTO_8AM)
    assert {r.user_id for r in digests()} >= {first.owner_id, second.owner_id}
    for biz in (first, second):
        (row,) = digests(biz.id)
        assert row.user_id == biz.owner_id
        assert row.business_id == biz.id
        assert row.params["business_name"] == biz.name


def test_skipped_without_forecast_or_minimum(
    mail: Mail, capsys: pytest.CaptureFixture[str]
) -> None:
    """C8."""
    no_forecast = business(mail, name="NoForecast", forecast=False)
    no_minimum = business(mail, name="NoMinimum", minimum=None)
    complete = business(mail, name="Complete")
    plant_forecast(
        no_minimum.id,
        MONDAY,
        opening=4230000,
        ends=flat(620000),
        computed_at=utc(10, 24, 10),
    )
    plant_forecast(
        complete.id,
        MONDAY,
        opening=4230000,
        ends=flat(620000),
        computed_at=utc(10, 24, 10),
    )
    configure_logging()
    capsys.readouterr()
    weekly_digest(TORONTO_8AM)
    skipped = {
        line["business_id"]: line["reason"]
        for line in log_lines(capsys.readouterr().out)
        if line.get("event") == "email.digest_skipped"
    }
    assert skipped[str(no_forecast.id)] == "no_forecast"
    assert skipped[str(no_minimum.id)] == "no_minimum"
    assert digests(no_forecast.id) == []
    assert digests(no_minimum.id) == []
    assert len(digests(complete.id)) == 1


def test_one_failure_does_not_stop_the_rest(
    mail: Mail, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C9."""
    boom = business(mail, name="Boom")
    fine = business(mail, name="Fine")
    plant_forecast(
        boom.id,
        MONDAY,
        opening=4230000,
        ends=flat(620000),
        computed_at=utc(10, 24, 10),
    )
    real = notifications_service.digest.digest_params

    def fails_for_boom(**kwargs: Any) -> dict[str, Any]:
        if kwargs["business_name"] == boom.name:
            raise RuntimeError("planted")
        return real(**kwargs)

    monkeypatch.setattr(notifications_service.digest, "digest_params", fails_for_boom)
    configure_logging()
    capsys.readouterr()
    counts = weekly_digest(TORONTO_8AM)
    failed = [
        line
        for line in log_lines(capsys.readouterr().out)
        if line.get("event") == "email.digest_failed"
    ]
    assert [(f["business_id"], f["error_type"]) for f in failed] == [
        (str(boom.id), "RuntimeError")
    ]
    assert digests(boom.id) == []
    assert len(digests(fine.id)) == 1
    assert counts["digests_failed"] == 1


def test_requested_logged_and_counted(
    mail: Mail, capsys: pytest.CaptureFixture[str]
) -> None:
    """C10."""
    biz = business(mail)
    second_owner(mail, biz, "sam@example.test")
    configure_logging()
    capsys.readouterr()
    assert weekly_digest(TORONTO_8AM) == {"digests_requested": 2, "digests_failed": 0}
    [line] = [
        line
        for line in log_lines(capsys.readouterr().out)
        if line.get("event") == "email.digest_requested"
    ]
    assert line["business_id"] == str(biz.id)
    assert line["monday"] == "2026-10-26"
    assert line["deliveries"] == 2
    assert weekly_digest(utc(10, 26, 20)) == {
        "digests_requested": 0,
        "digests_failed": 0,
    }


def test_registered_in_jobs() -> None:
    """C11."""
    names = [job.__name__ for job in jobs.JOBS]
    assert names == [
        "nightly_bank_sync",
        "forecast_accuracy",
        "weekly_digest",
        "email_retries",
    ]
    assert "weekly_digest" in names


def test_cash_on_hand_from_snapshot(mail: Mail) -> None:
    """C15."""
    biz = business(mail, opening=4230000)
    weekly_digest(TORONTO_8AM)
    assert params_of(biz)["cash_on_hand_cents"] == 4230000


def test_projected_low(mail: Mail) -> None:
    """C16: the lowest end-of-week balance, the earlier week on a tie."""
    biz = business(mail, ends=flat(900000, week=5, low=315000))
    ends = flat(900000, week=5, low=315000)
    ends[8] = 315000
    plant_forecast(
        biz.id,
        MONDAY,
        opening=4230000,
        ends=ends,
        computed_at=utc(10, 25, 10),
    )
    weekly_digest(TORONTO_8AM)
    assert params_of(biz)["low"] == {
        "balance_cents": 315000,
        "week_starts_on": "2026-11-23",
    }


def test_alerts_by_start_date(mail: Mail) -> None:
    """C17: open alerts only, by start date, with their fix counts."""
    biz = business(mail)
    later = plant_alert(biz, starts_on=date(2026, 12, 14), fixes=0)
    earlier = plant_alert(biz, starts_on=date(2026, 11, 9), fixes=3)
    plant_alert(biz, state="dismissed", starts_on=date(2027, 1, 4))
    weekly_digest(TORONTO_8AM)
    assert [(a["alert_id"], a["fix_count"]) for a in params_of(biz)["alerts"]] == [
        (str(earlier), 3),
        (str(later), 0),
    ]
    (sent,) = digest_sends(mail)
    assert "Open alerts (2)" in sent.text
    assert sent.html.index("Nov 9.") < sent.html.index("Dec 14.")


def test_all_clear_params(mail: Mail) -> None:
    """C18."""
    biz = business(mail, ends=flat(620000))
    weekly_digest(TORONTO_8AM)
    assert params_of(biz)["alerts"] == []
    (sent,) = digest_sends(mail)
    assert "All clear." in sent.text


def test_dismissed_gap(mail: Mail) -> None:
    """C19."""
    biz = business(mail)
    plant_alert(biz, state="dismissed")
    weekly_digest(TORONTO_8AM)
    assert params_of(biz)["alerts"] == []
    (sent,) = digest_sends(mail)
    assert "Open alerts" not in sent.text
    assert "All clear" not in sent.text


def test_changes_since_last_monday(mail: Mail) -> None:
    """C20: the differences from last Monday's pin, and the new payments named."""
    biz = business(mail, opening=4230000, ends=flat(900000, low=300000))
    plant_forecast(
        biz.id,
        LAST_MONDAY,
        opening=3818000,
        ends=flat(900000, low=360000),
        computed_at=utc(10, 19, 5),
        pin=LAST_MONDAY,
    )
    # The latest forecast is the one computed last; plant it again so it is.
    plant_forecast(
        biz.id,
        MONDAY,
        opening=4230000,
        ends=flat(900000, low=300000),
        computed_at=utc(10, 25, 10),
    )
    monday_start = datetime(2026, 10, 19, 0, 0, tzinfo=UTC) + timedelta(hours=4)
    plant_payment(biz, "Small", 100000, date(2026, 11, 2), monday_start)
    plant_payment(biz, "Acme Co", 800000, date(2026, 10, 6), monday_start)
    plant_payment(biz, "Medium", 300000, date(2026, 11, 3), monday_start)
    plant_payment(biz, "Tiny", 50000, date(2026, 11, 4), monday_start)
    plant_payment(
        biz,
        "Before the cutoff",
        9900000,
        date(2026, 11, 5),
        monday_start - timedelta(seconds=1),
    )
    weekly_digest(TORONTO_8AM)
    changes = params_of(biz)["changes"]
    assert changes["cash_change_cents"] == 412000
    assert changes["low_change_cents"] == -60000
    assert [p["name"] for p in changes["new_payments"]] == [
        "Acme Co",
        "Medium",
        "Small",
    ]
    assert changes["new_payments"][0] == {
        "name": "Acme Co",
        "amount_cents": 800000,
        "date": "2026-10-06",
    }


def test_no_baseline_pin(mail: Mail) -> None:
    """C22: pins for two Mondays ago and for this Monday are not last week's."""
    biz = business(mail)
    plant_forecast(
        biz.id,
        date(2026, 10, 12),
        opening=1,
        ends=flat(1),
        computed_at=utc(10, 12, 5),
        pin=date(2026, 10, 12),
    )
    plant_forecast(
        biz.id,
        MONDAY,
        opening=4230000,
        ends=flat(620000, low=315000),
        computed_at=utc(10, 25, 10),
        pin=MONDAY,
    )
    weekly_digest(TORONTO_8AM)
    assert params_of(biz)["changes"] is None
    (sent,) = digest_sends(mail)
    assert "What changed" not in sent.text


def test_sample_end_to_end(mail: Mail, monkeypatch: pytest.MonkeyPatch) -> None:
    """C29: Harbor Street through the real runner at its Monday 08:00 local."""
    sample = send_sample()
    mail.clerk.set(sample.owner_clerk_id, DANA, "Dana")
    monkeypatch.setattr(jobs, "JOBS", (weekly_digest,))
    subscriptions.register()
    run_due(utc(9, 28, 12))
    sent = [e for e in mail.sender.sent if e.subject == SUBJECT]
    assert [e.to for e in sent] == [DANA]
    assert "$3,150" in sent[0].text
    assert "Week of Nov 9" in sent[0].html
    assert "Cash falls below your $5,000 minimum the week of Nov 9." in sent[0].html


def test_params_hold_no_account(mail: Mail) -> None:
    """C30: exactly the door 3 keys, and nothing that names an account."""
    sample = send_sample()
    mail.clerk.set(sample.owner_clerk_id, DANA, "Dana")
    biz = Biz(
        id=sample.business_id,
        name="",
        owner_id=sample.owner_id,
        owner_sub=sample.owner_clerk_id,
    )
    plant_forecast(
        biz.id,
        date(2026, 9, 21),
        opening=1000,
        ends=flat(1000),
        computed_at=utc(9, 21, 5),
        pin=date(2026, 9, 21),
    )
    with get_sessionmaker()() as session:
        accounts = list(
            session.scalars(
                select(BankAccount).where(BankAccount.business_id == biz.id)
            )
        )
        source_ids = [
            i.source_id
            for i in session.scalars(
                select(AlertItem)
                .join(Alert, Alert.id == AlertItem.alert_id)
                .where(Alert.business_id == biz.id)
            )
            if i.source_id
        ]
        session.expunge_all()
    payment_account = accounts[0].id
    with get_sessionmaker()() as session:
        session.add(
            ExpectedPayment(
                business_id=biz.id,
                account_id=payment_account,
                description="Invoice 40021",
                amount_cents=-250000,
                currency="CAD",
                date=date(2026, 10, 6),
                repeats=None,
                created_at=utc(9, 22, 12),
                updated_at=utc(9, 22, 12),
            )
        )
        session.commit()
    weekly_digest(utc(9, 28, 12))
    (row,) = digests(biz.id)
    params = json.loads(json.dumps(row.params))
    assert set(params) == {
        "business_name",
        "currency",
        "monday",
        "cash_on_hand_cents",
        "minimum_cents",
        "low",
        "alerts",
        "changes",
    }
    assert set(params["low"]) == {"balance_cents", "week_starts_on"}
    assert all(
        set(a) == {"alert_id", "minimum_cents", "lowest_week_starts_on", "fix_count"}
        for a in params["alerts"]
    )
    assert set(params["changes"]) == {
        "cash_change_cents",
        "low_change_cents",
        "new_payments",
    }
    assert params["changes"]["new_payments"] == [
        {"name": "Invoice 40021", "amount_cents": 250000, "date": "2026-10-06"}
    ]
    stored = json.dumps(params)
    (sent,) = [e for e in mail.sender.sent if e.subject == SUBJECT]
    forbidden = [str(a.id) for a in accounts]
    forbidden += [a.plaid_account_id for a in accounts]
    forbidden += [a.mask for a in accounts if a.mask]
    forbidden += [str(s) for s in source_ids] + [sample.owner_clerk_id]
    for value in forbidden:
        assert value not in stored
        assert value not in sent.html
        assert value not in sent.text
