"""Spec 28: an email is sent once (C1-C7, C9, C13, C17, C18) and failures (C20, C23)."""

import json
import uuid
from typing import Any

import pytest
import requests
import resend
from markupsafe import escape
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.db import get_engine, get_sessionmaker
from app.log import configure_logging
from app.modules.notifications import senders
from app.modules.notifications import service as notifications_service
from app.modules.notifications.models import EmailDelivery, EmailPreferences
from app.modules.notifications.senders import ResendSender
from tests.email_support import REASON, Mail, log_lines

pytestmark = pytest.mark.usefixtures("migrated_database")


def test_request_sends_once(mail: Mail) -> None:
    """C1: one row, `sent` after the immediate attempt, one send to the Clerk address."""
    user = mail.user(email="dana@example.test")

    mail.request(user)

    [row] = mail.deliveries(user)
    assert row.state == "sent"
    assert row.attempts == 1
    assert len(mail.sender.sent) == 1
    assert mail.sender.sent[0].to == "dana@example.test"
    assert mail.sender.sent[0].subject == "Test subject"


def test_same_key_twice(mail: Mail) -> None:
    """C2: the same key twice for one user is one row and one send."""
    first, second = mail.user(), mail.user()

    assert mail.request(first, key="evt-1") is not None
    assert mail.request(first, key="evt-1") is None
    assert len(mail.deliveries(first)) == 1
    assert len(mail.sender.sent) == 1

    mail.request(second, key="evt-1")
    assert len(mail.deliveries(second)) == 1
    assert len(mail.sender.sent) == 2

    mail.request(first, key="evt-2")
    assert len(mail.deliveries(first)) == 2
    assert len(mail.sender.sent) == 3


def test_concurrent_attempts(mail: Mail) -> None:
    """C3: while one process holds the delivery, a second attempt sends nothing."""
    user = mail.user()
    delivery_id = mail.request(user, deliver=False)
    assert delivery_id is not None

    with get_sessionmaker()() as holder:
        held = holder.scalars(
            select(EmailDelivery)
            .where(EmailDelivery.id == delivery_id)
            .with_for_update()
        ).one()
        assert held.state == "pending"
        assert notifications_service.deliver(delivery_id) is None
        assert mail.sender.calls == 0
        holder.rollback()

    assert notifications_service.deliver(delivery_id) == "sent"
    assert notifications_service.deliver(delivery_id) is None
    assert len(mail.sender.sent) == 1


def test_idempotency_key(mail: Mail) -> None:
    """C4: the sender gets the delivery's id as the idempotency key."""
    user = mail.user()

    delivery_id = mail.request(user)

    assert mail.sender.sent[0].idempotency_key == str(delivery_id)


def test_skipped_at_request(mail: Mail) -> None:
    """C5: a kind turned off is recorded `skipped` and not sent; the other kind is."""
    user = mail.user()
    mail.set_preferences(user, alerts=False, weekly_digest=True)

    assert mail.request(user, key="a", kind="alert") is None

    [row] = mail.deliveries(user)
    assert row.state == "skipped"
    assert mail.sender.calls == 0

    other = mail.user()
    mail.set_preferences(other, alerts=True, weekly_digest=False)
    mail.request(other, key="b", kind="alert")
    assert [row.state for row in mail.deliveries(other)] == ["sent"]
    assert mail.request(other, key="c", kind="weekly_digest") is None
    assert len(mail.sender.sent) == 1


def test_skipped_at_send(mail: Mail) -> None:
    """C6: a pending delivery whose kind is turned off is skipped at its next attempt."""
    user = mail.user()
    mail.sender.fail_next(senders.SendError(error_type="503_x", retryable=True))
    delivery_id = mail.request(user)
    assert mail.deliveries(user)[0].state == "pending"

    mail.set_preferences(user, alerts=False, weekly_digest=True)

    assert delivery_id is not None
    assert notifications_service.deliver(delivery_id) == "skipped"
    assert mail.deliveries(user)[0].state == "skipped"
    assert mail.sender.sent == []
    assert mail.sender.calls == 1


def test_address_from_clerk(mail: Mail) -> None:
    """C7: the address and first name come from Clerk at attempt time; none is stored."""
    user = mail.user(email="first@example.test", first_name="Dana")
    mail.sender.fail_next(senders.SendError(error_type="503_x", retryable=True))
    delivery_id = mail.request(user)
    assert delivery_id is not None
    mail.clerk.set(mail.clerk_id(user), "second@example.test", "Dana")

    notifications_service.deliver(delivery_id)

    [email] = mail.sender.sent
    assert email.to == "second@example.test"
    assert "Hi Dana," in email.text

    nameless = mail.user(email="nameless@example.test", first_name=None)
    mail.request(nameless, key="n")
    assert "Hi " not in mail.sender.sent[-1].text

    with get_engine().connect() as conn:
        for table in ("email_deliveries", "email_preferences"):
            rows = conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
            dumped = json.dumps([dict(r) for r in rows], default=str)
            assert "@example.test" not in dumped


@pytest.mark.parametrize("case", ["no_primary_address", "no_clerk_user"])
def test_no_contact_fails(case: str, mail: Mail) -> None:
    """C9: no primary address, or no such Clerk user: `failed`, 0 sends, never retried."""
    if case == "no_primary_address":
        user = mail.user(email=None)
    else:
        user = mail.user()
        del mail.clerk.users[mail.clerk_id(user)]

    delivery_id = mail.request(user)

    [row] = mail.deliveries(user)
    assert row.state == "failed"
    assert row.attempts == 1
    assert mail.sender.calls == 0
    assert delivery_id is not None
    assert notifications_service.deliver(delivery_id) is None
    assert mail.deliveries(user)[0].attempts == 1


def test_unsubscribe_headers(mail: Mail) -> None:
    """C13: every send carries both List-Unsubscribe headers with the user's token."""
    user = mail.user()

    mail.request(user)

    token = mail.token(user)
    assert dict(mail.sender.sent[0].headers) == {
        "List-Unsubscribe": f"<https://api.example.test/v1/unsubscribe/{token}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def test_logs_no_pii(mail: Mail, capsys: pytest.CaptureFixture[str]) -> None:
    """C17: send logs carry ids, kinds and error types; never an address, token or body."""
    configure_logging()
    capsys.readouterr()
    sent = mail.user(email="sent-person@example.test")
    skipped = mail.user(email="skipped-person@example.test")
    retried = mail.user(email="retried-person@example.test")
    failed = mail.user(email="failed-person@example.test")
    mail.set_preferences(skipped, alerts=False, weekly_digest=True)
    secret = "Unique body text 4417"

    sent_id = mail.request(sent, params={"heading": "Heading 9921", "body": secret})
    mail.request(skipped, params={"heading": "Heading 9921", "body": secret})
    mail.sender.fail_next(senders.SendError(error_type="503_x", retryable=True))
    retried_id = mail.request(
        retried, params={"heading": "Heading 9921", "body": secret}
    )
    mail.sender.fail_next(senders.SendError(error_type="422_x", retryable=False))
    failed_id = mail.request(failed, params={"heading": "Heading 9921", "body": secret})

    out = capsys.readouterr().out
    lines = log_lines(out)
    forbidden = ["@example.test", secret, "Heading 9921", "Test subject", "re_"]
    forbidden += [mail.token(u) for u in (sent, retried, failed)]
    for part in forbidden:
        assert part not in out
    by_event = {
        line["event"]: line for line in lines if line["event"].startswith("email.")
    }
    assert by_event["email.sent"]["delivery_id"] == str(sent_id)
    assert by_event["email.sent"]["kind"] == "alert"
    assert by_event["email.sent"]["provider_id"].startswith("fake-")
    assert "email.skipped" in by_event
    assert by_event["email.send_failed"]["delivery_id"] == str(retried_id)
    assert by_event["email.send_failed"]["error_type"] == "503_x"
    assert by_event["email.send_failed"]["attempts"] == 1
    assert by_event["email.failed"]["delivery_id"] == str(failed_id)
    assert by_event["email.failed"]["kind"] == "alert"
    assert by_event["email.failed"]["error_type"] == "422_x"


def test_schema_constraints(mail: Mail) -> None:
    """C18: the unique key and both check constraints exist and hold."""
    user = mail.user()
    engine = get_engine()
    inspector = inspect(engine)
    uniques = {u["name"] for u in inspector.get_unique_constraints("email_deliveries")}
    checks = {c["name"] for c in inspector.get_check_constraints("email_deliveries")}
    assert "uq_email_deliveries_dedup_key_user_id" in uniques
    assert {"ck_email_deliveries_state", "ck_email_deliveries_kind"} <= checks
    assert inspector.get_pk_constraint("email_preferences")["constrained_columns"] == [
        "user_id"
    ]
    pref_uniques = inspector.get_unique_constraints("email_preferences")
    assert [u["column_names"] for u in pref_uniques] == [["unsubscribe_token"]]

    insert = (
        "INSERT INTO email_deliveries (id, business_id, user_id, dedup_key, kind,"
        " template, params, reason, state, attempts) VALUES (:id, :b, :u, :k, :kind,"
        " 't', '{}', 'r', :state, 0)"
    )

    def row(**overrides: Any) -> dict[str, Any]:
        values = {
            "id": uuid.uuid4(),
            "b": uuid.uuid4(),
            "u": user,
            "k": "dup",
            "kind": "alert",
            "state": "pending",
        }
        return values | overrides

    with engine.begin() as conn:
        conn.execute(text(insert), row())
    for bad, constraint in (
        (row(), "uq_email_deliveries_dedup_key_user_id"),
        (row(k="other-1", state="queued"), "ck_email_deliveries_state"),
        (row(k="other-2", kind="invite"), "ck_email_deliveries_kind"),
    ):
        with pytest.raises(IntegrityError) as raised, engine.begin() as conn:
            conn.execute(text(insert), bad)
        assert constraint in str(raised.value)


def _resend_answer(
    monkeypatch: pytest.MonkeyPatch, status: int | None, name: str = ""
) -> None:
    """Make Resend's HTTP layer answer `status` with error `name`, or time out (None)."""

    def fake_request(*args: Any, **kwargs: Any) -> Any:
        if status is None:
            raise requests.exceptions.ReadTimeout("timed out")
        response = requests.Response()
        response.status_code = status
        response.headers["content-type"] = "application/json"
        response._content = json.dumps(
            {"statusCode": status, "name": name, "message": "test"}
        ).encode()
        return response

    monkeypatch.setattr(resend.http_client_requests.requests, "request", fake_request)
    sender = ResendSender("re_test_key")
    monkeypatch.setattr(senders, "get_email_sender", lambda: sender)


RETRYABLE = [
    (None, ""),
    (429, "rate_limit_exceeded"),
    (409, "concurrent_idempotent_requests"),
    (409, "resource_locked"),
    (500, "application_error"),
    (503, "service_unavailable"),
]


@pytest.mark.parametrize(("status", "name"), RETRYABLE)
def test_retryable_errors(
    status: int | None,
    name: str,
    mail: Mail,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C20: each retryable Resend failure leaves the delivery pending, attempts + 1."""
    user = mail.user()
    _resend_answer(monkeypatch, status, name)
    configure_logging()
    capsys.readouterr()

    mail.request(user)

    [row] = mail.deliveries(user)
    assert row.state == "pending"
    assert row.attempts == 1
    failed = [
        line
        for line in log_lines(capsys.readouterr().out)
        if line["event"] == "email.send_failed"
    ]
    assert len(failed) == 1
    assert failed[0]["delivery_id"] == str(row.id)


def test_retryable_errors_clerk_timeout(
    mail: Mail, capsys: pytest.CaptureFixture[str]
) -> None:
    """C20: a Clerk lookup that times out leaves the delivery pending too."""
    user = mail.user()
    mail.clerk.unavailable = 1
    configure_logging()
    capsys.readouterr()

    mail.request(user)

    [row] = mail.deliveries(user)
    assert row.state == "pending"
    assert row.attempts == 1
    assert mail.sender.calls == 0
    events = [line["event"] for line in log_lines(capsys.readouterr().out)]
    assert "email.send_failed" in events


PERMANENT = [
    (400, "validation_error"),
    (401, "missing_api_key"),
    (403, "invalid_permission"),
    (409, "invalid_idempotent_request"),
    (422, "invalid_parameter"),
]


@pytest.mark.parametrize(("status", "name"), PERMANENT)
def test_permanent_errors(
    status: int,
    name: str,
    mail: Mail,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C23: each permanent Resend error marks the delivery failed, never retried."""
    user = mail.user()
    _resend_answer(monkeypatch, status, name)
    configure_logging()
    capsys.readouterr()

    delivery_id = mail.request(user)

    [row] = mail.deliveries(user)
    assert row.state == "failed"
    events = [line["event"] for line in log_lines(capsys.readouterr().out)]
    assert "email.failed" in events
    assert delivery_id is not None
    assert notifications_service.deliver(delivery_id) is None
    notifications_service.retry_pending()
    assert mail.deliveries(user)[0].attempts == 1
    assert mail.deliveries(user)[0].state == "failed"


def test_preferences_row_holds_token_only(mail: Mail) -> None:
    """Door 2: the row created at send time has both kinds on and a token."""
    user = mail.user()
    mail.request(user)

    with get_sessionmaker()() as session:
        row = session.get(EmailPreferences, user)
        assert row is not None
        assert (row.alerts, row.weekly_digest) == (True, True)


def test_footer_in_sent_email(mail: Mail) -> None:
    """C11, C12 at the send boundary: the delivered email's footer carries this user's
    links, from WEB_URL and their own token, and the mailing address."""
    user = mail.user()

    mail.request(user)

    [email] = mail.sender.sent
    token = mail.token(user)
    preferences = "https://app.example.test/settings/email"
    unsubscribe = f"https://app.example.test/unsubscribe/{token}"
    assert f'href="{preferences}"' in email.html
    assert f'href="{unsubscribe}"' in email.html
    assert "Headroom · 1 Test St, Toronto ON M5V 1A1" in email.html
    assert str(escape(REASON)) in email.html
    text_lines = email.text.splitlines()
    assert f"Email preferences: {preferences}" in text_lines
    assert f"Unsubscribe: {unsubscribe}" in text_lines
    assert "Headroom · 1 Test St, Toronto ON M5V 1A1" in text_lines
    assert REASON in text_lines
