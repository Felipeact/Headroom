"""Spec 28: email preferences (C25-C29)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.main import app
from app.modules.notifications.models import EmailPreferences
from tests.test_businesses import Caller
from tests.test_expected_payments_api import is_problem
from tests.tokens import bearer, token

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)
PATH = "/v1/me/email-preferences"


def put(caller: Caller, body: Any, **params: str) -> Any:
    return client.put(PATH, json=body, headers=caller.headers, params=params)


def test_defaults() -> None:
    """C25: never changed means both on, and reading creates no row."""
    caller = Caller()

    response = caller.get(PATH)

    assert response.status_code == 200
    assert response.json() == {"alerts": True, "weekly_digest": True}
    with get_sessionmaker()() as session:
        assert session.get(EmailPreferences, caller.id) is None


def test_put_saves() -> None:
    """C26: PUT saves both values, GET returns them, a second PUT replaces them."""
    caller = Caller()

    response = put(caller, {"alerts": False, "weekly_digest": True})
    assert response.status_code == 200
    assert response.json() == {"alerts": False, "weekly_digest": True}
    assert caller.get(PATH).json() == {"alerts": False, "weekly_digest": True}

    response = put(caller, {"alerts": True, "weekly_digest": False})
    assert response.status_code == 200
    assert caller.get(PATH).json() == {"alerts": True, "weekly_digest": False}


@pytest.mark.parametrize(
    "body",
    [
        {"alerts": False},
        {"weekly_digest": False},
        {},
        {"alerts": False, "weekly_digest": True, "sms": True},
        {"alerts": "no", "weekly_digest": True},
        {"alerts": None, "weekly_digest": True},
    ],
    ids=["no_weekly_digest", "no_alerts", "empty", "extra", "string", "null"],
)
def test_invalid_body(body: dict[str, Any]) -> None:
    """C27: each bad body is 422 problem details and saves nothing."""
    caller = Caller()
    assert put(caller, {"alerts": True, "weekly_digest": False}).status_code == 200

    is_problem(put(caller, body), 422)

    assert caller.get(PATH).json() == {"alerts": True, "weekly_digest": False}


@pytest.mark.parametrize("method", ["get", "put"])
@pytest.mark.parametrize("auth", ["none", "invalid"])
def test_unauthenticated(method: str, auth: str) -> None:
    """C28: no token, or a bad one, is 401 problem details."""
    headers = {} if auth == "none" else bearer(token("user_x") + "tampered")
    body = {"alerts": False, "weekly_digest": False}

    if method == "get":
        response = client.get(PATH, headers=headers)
    else:
        response = client.put(PATH, json=body, headers=headers)

    is_problem(response, 401)


def test_own_preferences_only() -> None:
    """C29: one user's changes never reach another's; a user_id parameter is ignored."""
    a, b = Caller(), Caller()

    assert put(a, {"alerts": False, "weekly_digest": True}).status_code == 200
    assert b.get(PATH).json() == {"alerts": True, "weekly_digest": True}

    response = put(b, {"alerts": True, "weekly_digest": False}, user_id=str(a.id))
    assert response.status_code == 200
    assert a.get(PATH).json() == {"alerts": False, "weekly_digest": True}
    assert b.get(PATH).json() == {"alerts": True, "weekly_digest": False}
    assert a.get(f"{PATH}?user_id={b.id}").json() == {
        "alerts": False,
        "weekly_digest": True,
    }
