"""Spec 28: one-click unsubscribe without signing in (C37-C42)."""

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.main import app
from app.modules.notifications import senders
from app.modules.notifications import service as notifications_service
from app.modules.notifications.models import EmailPreferences
from tests.email_support import Mail
from tests.test_businesses import Caller
from tests.test_expected_payments_api import is_problem

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)
PREFS = "/v1/me/email-preferences"


def token_of(caller: Caller) -> str:
    with get_sessionmaker()() as session:
        return notifications_service.unsubscribe_token(session, caller.id)


def updated_at(caller: Caller) -> Any:
    with get_sessionmaker()() as session:
        row = session.get(EmailPreferences, caller.id)
        assert row is not None
        return row.updated_at


def post(token: str, **kwargs: Any) -> Any:
    return client.post(f"/v1/unsubscribe/{token}", **kwargs)


def test_unsubscribes_without_login() -> None:
    """C37: no session, one call, both kinds off at once."""
    caller = Caller()
    token = token_of(caller)

    response = post(token)

    assert response.status_code == 200
    assert response.json() == {"status": "unsubscribed"}
    assert caller.get(PREFS).json() == {"alerts": False, "weekly_digest": False}

    alerts_only = Caller()
    client.put(
        PREFS,
        json={"alerts": True, "weekly_digest": False},
        headers=alerts_only.headers,
    )
    assert post(token_of(alerts_only)).status_code == 200
    assert alerts_only.get(PREFS).json() == {"alerts": False, "weekly_digest": False}


def test_twice() -> None:
    """C38: a second call is 200 and changes nothing."""
    caller = Caller()
    token = token_of(caller)
    assert post(token).status_code == 200
    first = updated_at(caller)

    response = post(token)

    assert response.status_code == 200
    assert response.json() == {"status": "unsubscribed"}
    assert caller.get(PREFS).json() == {"alerts": False, "weekly_digest": False}
    assert updated_at(caller) == first


@pytest.mark.parametrize(
    "token", ["A" * 43, "x" * 500, "x"], ids=["unknown", "too_long", "short"]
)
def test_unknown_token(token: str) -> None:
    """C39: an unknown token is 404 problem details and changes nobody."""
    caller = Caller()
    token_of(caller)

    is_problem(post(token), 404)

    assert caller.get(PREFS).json() == {"alerts": True, "weekly_digest": True}


@pytest.mark.parametrize("body", ["form", "empty", "json"])
def test_one_click_body(body: str) -> None:
    """C40: RFC 8058's form body, no body and a JSON body all unsubscribe."""
    caller = Caller()
    token = token_of(caller)
    kwargs: dict[str, Any] = {
        "form": {
            "content": "List-Unsubscribe=One-Click",
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        },
        "empty": {},
        "json": {"json": {"anything": True}},
    }[body]

    response = post(token, **kwargs)

    assert response.status_code == 200
    assert caller.get(PREFS).json() == {"alerts": False, "weekly_digest": False}


def test_takes_effect_immediately(mail: Mail) -> None:
    """C41: a pending delivery is skipped at its next attempt; new requests are skipped."""
    user = mail.user()
    mail.sender.fail_next(senders.SendError(error_type="503_x", retryable=True))
    delivery_id = mail.request(user, key="before")
    assert delivery_id is not None
    assert mail.deliveries(user)[0].state == "pending"

    assert post(mail.token(user)).status_code == 200

    assert notifications_service.deliver(delivery_id) == "skipped"
    assert mail.request(user, key="after") is None
    assert [row.state for row in mail.deliveries(user)] == ["skipped", "skipped"]
    assert mail.sender.sent == []


def test_token_shape(mail: Mail) -> None:
    """C42: 43 URL-safe characters, the same in every email, unique per user."""
    user, other = mail.user(), mail.user()

    mail.request(user, key="day-1")
    mail.set_preferences(user, alerts=True, weekly_digest=False)
    mail.request(user, key="day-2")

    token = mail.token(user)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    links = [email.headers["List-Unsubscribe"] for email in mail.sender.sent]
    assert links == [f"<https://api.example.test/v1/unsubscribe/{token}>"] * 2
    assert mail.token(other) != token
