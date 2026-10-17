"""Spec 29: alert emails, from the event to the delivery (C1-C10, C14, C24, C26)."""

import json
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app import events, subscriptions
from app.db import get_sessionmaker
from app.log import configure_logging
from app.modules.accounts import clerk
from app.modules.accounts import repository as accounts_repository
from app.modules.accounts.models import Business
from app.modules.alerts import service as alerts_service
from app.modules.alerts.models import Alert, AlertItem
from app.modules.bank_sync.models import BankAccount
from app.modules.notifications import sample_alert
from app.modules.notifications import service as notifications_service
from app.modules.notifications.models import EmailDelivery
from tests.alert_email_support import DANA, SampleEmail, send_sample
from tests.email_support import Mail, log_lines
from tests.test_alert_check import MINIMUM, Fake, forecast, install_fake
from tests.test_expected_payments_api import owner_business

pytestmark = pytest.mark.usefixtures("migrated_database")


@pytest.fixture(autouse=True)
def _registered() -> None:
    # Alert events reach email_alert through the bus, the same in every test order.
    subscriptions.register()


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Fake:
    return install_fake(monkeypatch)


def owned(mail: Mail, fake: Fake, *, shortfall: int = 100000) -> uuid.UUID:
    """A business whose owner is in the fake Clerk, with a gap in week 7."""
    owner, business_id = owner_business("Mail")
    found = uuid.UUID(business_id)
    mail.clerk.set(owner.sub, f"{owner.sub}@example.test", "Dana")
    fake.minimums[found] = (MINIMUM, "CAD")
    fake.forecasts[found] = forecast({7: shortfall})
    return found


def second_owner(mail: Mail, business_id: uuid.UUID, email: str) -> uuid.UUID:
    user_id = mail.user(email)
    with get_sessionmaker()() as session:
        accounts_repository.insert_membership(
            session, business_id=business_id, user_id=user_id, role="owner"
        )
        session.commit()
    return user_id


def owners(business_id: uuid.UUID) -> list[uuid.UUID]:
    with get_sessionmaker()() as session:
        return accounts_repository.member_ids(
            session, business_id=business_id, roles=["owner"]
        )


def check(business_id: uuid.UUID) -> None:
    alerts_service.check_cash_gaps(
        events.Event(name="forecast.updated", business_id=business_id, payload={})
    )


def the_alert(business_id: uuid.UUID) -> Alert:
    with get_sessionmaker()() as session:
        (alert,) = session.scalars(
            select(Alert).where(Alert.business_id == business_id)
        )
        session.expunge_all()
    return alert


def deliveries(business_id: uuid.UUID | None = None) -> list[EmailDelivery]:
    with get_sessionmaker()() as session:
        query = select(EmailDelivery).order_by(
            EmailDelivery.created_at, EmailDelivery.user_id
        )
        if business_id is not None:
            query = query.where(EmailDelivery.business_id == business_id)
        rows = list(session.scalars(query))
        session.expunge_all()
    return rows


def alert_event(name: str, business_id: uuid.UUID, alert_id: uuid.UUID) -> events.Event:
    return events.Event(
        name=name, business_id=business_id, payload={"alert_id": str(alert_id)}
    )


def test_created_emails_each_owner(mail: Mail, fake: Fake) -> None:
    """C1."""
    business_id = owned(mail, fake)
    second = second_owner(mail, business_id, "sam@example.test")
    check(business_id)
    alert = the_alert(business_id)
    rows = deliveries(business_id)
    assert {r.user_id for r in rows} == set(owners(business_id))
    assert second in {r.user_id for r in rows}
    assert len(rows) == 2
    with get_sessionmaker()() as session:
        name = session.get(Business, business_id).name  # type: ignore[union-attr]
    for row in rows:
        assert row.kind == "alert"
        assert row.template == "alert"
        assert row.dedup_key == f"alert:{alert.id}:{alert.notified_shortfall_cents}"
        assert row.reason == (
            f"You're getting this email because you're an owner of {name} on Headroom."
        )
        assert row.state == "sent"
    assert sorted(e.to for e in mail.sender.sent) == sorted(
        [f"{mail.clerk_id(owners(business_id)[0])}@example.test", "sam@example.test"]
    )


def test_updated_emails_again(mail: Mail, fake: Fake) -> None:
    """C2."""
    business_id = owned(mail, fake, shortfall=100000)
    check(business_id)
    first = the_alert(business_id)
    assert first.notified_shortfall_cents == 100000
    fake.forecasts[business_id] = forecast({7: 300000})
    check(business_id)
    rows = deliveries(business_id)
    assert [r.dedup_key for r in rows] == [
        f"alert:{first.id}:100000",
        f"alert:{first.id}:300000",
    ]
    assert len(mail.sender.sent) == 2


def test_same_event_twice(mail: Mail, fake: Fake) -> None:
    """C3."""
    business_id = owned(mail, fake)
    check(business_id)
    alert = the_alert(business_id)
    notifications_service.email_alert(
        alert_event("alert.created", business_id, alert.id)
    )
    assert len(deliveries(business_id)) == 1
    assert len(mail.sender.sent) == 1

    fake.forecasts[business_id] = forecast({7: 300000})
    check(business_id)
    notifications_service.email_alert(
        alert_event("alert.updated", business_id, alert.id)
    )
    assert len(deliveries(business_id)) == 2
    assert len(mail.sender.sent) == 2


def test_subscriptions_and_resolved(mail: Mail, fake: Fake) -> None:
    """C4."""
    rows = subscriptions.SUBSCRIPTIONS
    created = rows.index(("alert.created", notifications_service.email_alert))
    updated = rows.index(("alert.updated", notifications_service.email_alert))
    last_check = max(
        i for i, (_, h) in enumerate(rows) if h is alerts_service.check_cash_gaps
    )
    assert created > last_check
    assert updated > last_check
    assert all(name != "alert.resolved" for name, _ in rows)

    business_id = owned(mail, fake)
    check(business_id)
    assert len(deliveries(business_id)) == 1
    fake.forecasts[business_id] = forecast({})
    check(business_id)
    assert the_alert(business_id).state == "resolved"
    assert len(deliveries(business_id)) == 1


def test_not_open_skipped(
    mail: Mail, fake: Fake, capsys: pytest.CaptureFixture[str]
) -> None:
    """C5."""
    dismissed = owned(mail, fake)
    check(dismissed)
    alert = the_alert(dismissed)
    with get_sessionmaker()() as session:
        alerts_service.dismiss_alert(
            session,
            business_id=dismissed,
            alert_id=alert.id,
            now=alerts_service.clock(),
        )
    resolved = owned(mail, fake)
    check(resolved)
    gone = the_alert(resolved)
    fake.forecasts[resolved] = forecast({})
    check(resolved)
    with get_sessionmaker()() as session:
        session.execute(
            EmailDelivery.__table__.delete().where(
                EmailDelivery.business_id.in_([dismissed, resolved])
            )
        )
        session.commit()
    configure_logging()
    capsys.readouterr()

    notifications_service.email_alert(alert_event("alert.created", dismissed, alert.id))
    notifications_service.email_alert(alert_event("alert.created", resolved, gone.id))

    assert deliveries(dismissed) == []
    assert deliveries(resolved) == []
    skipped = [
        (line["alert_id"], line["state"])
        for line in log_lines(capsys.readouterr().out)
        if line["event"] == "email.alert_skipped"
    ]
    assert skipped == [(str(alert.id), "dismissed"), (str(gone.id), "resolved")]


def test_foreign_alert_skipped(
    mail: Mail, fake: Fake, capsys: pytest.CaptureFixture[str]
) -> None:
    """C6."""
    a = owned(mail, fake)
    b = owned(mail, fake, shortfall=0)
    fake.forecasts[b] = forecast({})
    check(a)
    alert = the_alert(a)
    before = len(deliveries())
    configure_logging()
    capsys.readouterr()
    stranger = uuid.uuid4()

    notifications_service.email_alert(alert_event("alert.created", b, alert.id))
    notifications_service.email_alert(alert_event("alert.created", a, stranger))

    assert len(deliveries()) == before
    skipped = [
        (line["alert_id"], line["state"])
        for line in log_lines(capsys.readouterr().out)
        if line["event"] == "email.alert_skipped"
    ]
    assert skipped == [(str(alert.id), "not_found"), (str(stranger), "not_found")]


def test_only_this_business_owners(mail: Mail, fake: Fake) -> None:
    """C7."""
    a = owned(mail, fake)
    b = owned(mail, fake)
    fake.forecasts[b] = forecast({})
    check(a)
    assert {r.user_id for r in deliveries(a)} == set(owners(a))
    (b_owner,) = owners(b)
    assert [r for r in deliveries() if r.user_id == b_owner] == []


def test_owner_opted_out(mail: Mail, fake: Fake) -> None:
    """C8."""
    business_id = owned(mail, fake)
    (first,) = owners(business_id)
    second_owner(mail, business_id, "sam@example.test")
    mail.set_preferences(first, alerts=False, weekly_digest=True)
    check(business_id)
    states = {r.user_id: r.state for r in deliveries(business_id)}
    assert states[first] == "skipped"
    assert sorted(states.values()) == ["sent", "skipped"]
    assert [e.to for e in mail.sender.sent] == ["sam@example.test"]


def test_requested_logged(
    mail: Mail, fake: Fake, capsys: pytest.CaptureFixture[str]
) -> None:
    """C9."""
    business_id = owned(mail, fake)
    second_owner(mail, business_id, "sam@example.test")
    configure_logging()
    capsys.readouterr()
    check(business_id)
    alert = the_alert(business_id)
    requested = [
        line
        for line in log_lines(capsys.readouterr().out)
        if line["event"] == "email.alert_requested"
    ]
    assert len(requested) == 1
    assert requested[0]["alert_id"] == str(alert.id)
    assert requested[0]["event_name"] == "alert.created"
    assert requested[0]["deliveries"] == 2


@pytest.fixture(scope="module")
def sample(migrated_database: None) -> SampleEmail:
    return send_sample()


def test_sample_end_to_end(sample: SampleEmail) -> None:
    """C10."""
    (email,) = sample.sent
    assert email.to == DANA
    assert email.subject == "Cash falls below your $5,000 minimum the week of Nov 9"


def view(
    items: list[alerts_service.AlertItemView],
    fixes: list[alerts_service.AlertFixView] | None = None,
) -> alerts_service.AlertView:
    now = datetime(2026, 9, 26, tzinfo=UTC)
    return alerts_service.AlertView(
        id=uuid.uuid4(),
        state="open",
        starts_on=date(2026, 11, 9),
        ends_on=date(2026, 11, 15),
        lowest_week_starts_on=date(2026, 11, 9),
        lowest_balance_cents=315000,
        minimum_cents=500000,
        shortfall_cents=185000,
        notified_shortfall_cents=185000,
        currency="CAD",
        created_at=now,
        updated_at=now,
        dismissed_at=None,
        resolved_at=None,
        items=items,
        fixes=fixes or [],
    )


def item(
    amount: int,
    day: date,
    *,
    kind: str = "cause",
    counterparty: str | None = None,
    description: str | None = "Payee",
) -> alerts_service.AlertItemView:
    return alerts_service.AlertItemView(
        kind=kind,  # type: ignore[arg-type]
        date=day,
        amount_cents=amount,
        currency="CAD",
        description=description,
        counterparty=counterparty,
        source="recurring_pattern",
        schedule=None,
    )


def test_params_causes() -> None:
    """C14: the order, the names, and no arrives_after item."""
    params = notifications_service.alert_params(
        view(
            [
                item(-5000, date(2026, 11, 10)),
                item(-9000, date(2026, 11, 12)),
                item(-9000, date(2026, 11, 11)),
                item(800000, date(2026, 11, 16), kind="arrives_after"),
            ]
        ),
        business_name="Acme",
        change="created",
    )
    assert [(c["amount_cents"], c["date"]) for c in params["causes"]] == [
        (9000, "2026-11-11"),
        (9000, "2026-11-12"),
        (5000, "2026-11-10"),
    ]
    named = notifications_service.alert_params(
        view(
            [
                item(
                    -1, date(2026, 11, 10), counterparty="Acme", description="Other, x"
                ),
                item(-1, date(2026, 11, 11), description="Birch & Co, invoice 1057"),
            ]
        ),
        business_name="Acme",
        change="created",
    )
    assert [c["name"] for c in named["causes"]] == ["Acme", "Birch & Co"]


def test_params_hold_no_account(sample: SampleEmail) -> None:
    """C24."""
    params = sample.params
    assert set(params) == {
        "alert_id",
        "business_name",
        "change",
        "currency",
        "minimum_cents",
        "lowest_balance_cents",
        "lowest_week_starts_on",
        "causes",
        "top_fix",
        "fix_count",
    }
    for cause in params["causes"]:
        assert set(cause) == {"name", "amount_cents", "date"}
    assert set(params["top_fix"]) == {"kind", "name", "amount_cents", "keeps_above"}

    with get_sessionmaker()() as session:
        accounts = list(
            session.scalars(
                select(BankAccount).where(BankAccount.business_id == sample.business_id)
            )
        )
        source_ids = [
            str(i.source_id)
            for i in session.scalars(
                select(AlertItem).where(AlertItem.alert_id == sample.alert_id)
            )
            if i.source_id is not None
        ]
    forbidden = [str(a.id) for a in accounts] + [
        a.provider_account_id for a in accounts
    ]
    forbidden += ["2381", "9025", "5530", "7702", sample.owner_clerk_id, *source_ids]
    assert accounts and source_ids
    (email,) = sample.sent
    for text in (json.dumps(params), email.html, email.text):
        for value in forbidden:
            assert value not in text


def test_no_real_clerk_in_tests() -> None:
    """C26."""
    users = clerk.get_clerk_users()
    assert not isinstance(users, clerk.BackendClerkUsers)
    assert users.get("user_anything") is None


def test_non_cad_fails_one_delivery(mail: Mail) -> None:
    """Door 4: a currency other than CAD fails that delivery; the next one still sends."""
    bad = mail.user(email="bad@example.test")
    good = mail.user(email="good@example.test")
    ids = []
    for user_id, currency in ((bad, "USD"), (good, "CAD")):
        with get_sessionmaker()() as session:
            ids.append(
                notifications_service.request_email(
                    session,
                    dedup_key=f"alert:non-cad:{currency}",
                    user_id=user_id,
                    business_id=mail.business_id,
                    kind="alert",
                    template="alert",
                    params={**sample_alert.SAMPLE, "currency": currency},
                    reason="You're getting this email because you're an owner.",
                )
            )
            session.commit()

    for delivery_id in ids:
        assert delivery_id is not None
        notifications_service.deliver(delivery_id)

    assert mail.deliveries(bad)[0].state == "failed"
    assert mail.deliveries(good)[0].state == "sent"
    assert [email.to for email in mail.sender.sent] == ["good@example.test"]
