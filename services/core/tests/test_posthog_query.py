"""Spec 32 C16, C17: the PostHog Query API client. The HTTP layer is a mock transport."""

import json

import httpx
import pytest

from app.analytics import PostHogError, PostHogHttpQuery

KEY = "phx_secret_personal_key"
BODY_MARKER = "response-body-marker"


def client(handler: httpx.MockTransport | object) -> PostHogHttpQuery:
    transport = (
        handler
        if isinstance(handler, httpx.MockTransport)
        else httpx.MockTransport(handler)
    )  # type: ignore[arg-type]
    return PostHogHttpQuery(
        app_host="https://us.posthog.test/",
        project_id="667024",
        personal_api_key=KEY,
        transport=transport,
    )


def test_request_shape() -> None:
    """C16."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"results": [[7]]})

    assert client(handler).count("SELECT count() FROM events") == 7

    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == "https://us.posthog.test/api/projects/667024/query/"
    assert request.headers["Authorization"] == f"Bearer {KEY}"
    assert json.loads(request.content) == {
        "query": {"kind": "HogQLQuery", "query": "SELECT count() FROM events"}
    }
    assert request.extensions["timeout"] == {
        "connect": 15,
        "read": 15,
        "write": 15,
        "pool": 15,
    }


def test_failures_raise_posthog_error() -> None:
    """C17."""

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"{KEY} {BODY_MARKER}")

    cases = {
        "timeout": timeout,
        "http_401": lambda r: httpx.Response(401, text=f"{BODY_MARKER} {KEY}"),
        "http_429": lambda r: httpx.Response(429, text=BODY_MARKER),
        "http_500": lambda r: httpx.Response(500, text=BODY_MARKER),
        "malformed_response": lambda r: httpx.Response(200, text=BODY_MARKER),
    }
    for error_type, handler in cases.items():
        with pytest.raises(PostHogError) as raised:
            client(handler).count("SELECT 1")
        assert raised.value.error_type == error_type
        message = str(raised.value) + repr(raised.value)
        assert KEY not in message
        assert BODY_MARKER not in message


def test_a_result_that_is_not_a_number_is_malformed() -> None:
    """C17: a well-formed body with a string in the cell is still not a count."""
    with pytest.raises(PostHogError) as raised:
        client(lambda r: httpx.Response(200, json={"results": [["many"]]})).count("q")
    assert raised.value.error_type == "malformed_response"
