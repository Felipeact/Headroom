import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import sentry_sdk
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport
from sentry_sdk.types import Event

import app.monitoring
from app.log import configure_logging
from app.main import app as api
from app.settings import get_settings

CORE = Path(__file__).resolve().parents[1]
FAKE_DSN = "https://public@sentry.example.invalid/1"
SANDBOX_TOKEN = "access-sandbox-1b4e28ba-2fa1-11d2-883f-0016e5f2c3a1"


class FakeTransport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[Event] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


@pytest.fixture
def test_routes() -> Iterator[None]:
    router = APIRouter()

    @router.get("/test/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    @router.get("/test/missing")
    def missing() -> None:
        raise HTTPException(status_code=404)

    @router.get("/test/conflict")
    def conflict() -> None:
        raise HTTPException(status_code=409)

    @router.get("/test/unavailable")
    def unavailable() -> None:
        raise HTTPException(status_code=503)

    @router.get("/test/boom-with-token")
    def boom_with_token() -> None:
        sentry_sdk.set_extra("access_token", SANDBOX_TOKEN)
        raise RuntimeError("boom")

    before = list(api.router.routes)
    api.include_router(router)
    yield
    api.router.routes[:] = before


def reset_sentry() -> None:
    sentry_sdk.get_global_scope().set_client(None)
    sentry_sdk.get_isolation_scope().clear()


@pytest.fixture
def sentry_events(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Event]]:
    """Run the app's own Sentry init with SENTRY_DSN set, delivering to a fake."""
    transport = FakeTransport()
    real_init: Callable[..., Any] = sentry_sdk.init

    def init_with_fake_transport(*args: Any, **kwargs: Any) -> Any:
        return real_init(*args, transport=transport, **kwargs)

    monkeypatch.setattr(app.monitoring.sentry_sdk, "init", init_with_fake_transport)
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    get_settings.cache_clear()
    yield transport.events
    reset_sentry()
    get_settings.cache_clear()


@pytest.fixture
def lifespan_client(sentry_events: list[Event]) -> Iterator[TestClient]:
    with TestClient(api, raise_server_exceptions=False) as client:
        yield client
    sentry_sdk.flush()


def exception_types(events: list[Event]) -> list[str]:
    return [value["type"] for e in events for value in e["exception"]["values"]]


@pytest.mark.usefixtures("test_routes")
def test_unhandled_exception_sends_one_event(
    lifespan_client: TestClient, sentry_events: list[Event]
) -> None:
    response = lifespan_client.get("/test/boom")
    sentry_sdk.flush()

    assert response.status_code == 500
    assert len(sentry_events) == 1
    assert exception_types(sentry_events) == ["RuntimeError"]


@pytest.mark.usefixtures("test_routes")
def test_4xx_http_exception_sends_no_event(
    lifespan_client: TestClient, sentry_events: list[Event]
) -> None:
    assert lifespan_client.get("/test/missing").status_code == 404
    assert lifespan_client.get("/test/conflict").status_code == 409
    sentry_sdk.flush()

    assert sentry_events == []


@pytest.mark.usefixtures("test_routes")
def test_5xx_http_exception_sends_one_event(
    lifespan_client: TestClient, sentry_events: list[Event]
) -> None:
    assert lifespan_client.get("/test/unavailable").status_code == 503
    sentry_sdk.flush()

    assert exception_types(sentry_events) == ["HTTPException"]


@pytest.mark.usefixtures("test_routes")
def test_event_redacted_before_send(
    lifespan_client: TestClient, sentry_events: list[Event]
) -> None:
    lifespan_client.get(
        "/test/boom-with-token", headers={"Authorization": "Bearer abc.def-123"}
    )
    sentry_sdk.flush()

    assert len(sentry_events) == 1
    serialized = json.dumps(sentry_events[0], default=str)
    assert "abc.def-123" not in serialized
    assert SANDBOX_TOKEN not in serialized
    assert "ip_address" not in sentry_events[0].get("user", {})


def test_no_dsn_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", "")
    get_settings.cache_clear()
    reset_sentry()
    try:
        with TestClient(api) as client:
            active = sentry_sdk.get_client().is_active()
            response = client.get("/healthz/live")
    finally:
        get_settings.cache_clear()

    assert active is False
    assert response.status_code == 200


def test_sentry_check_without_dsn_exits_1() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.sentry_check"],
        cwd=CORE,
        env={**os.environ, "SENTRY_DSN": ""},
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 1
    assert "SENTRY_DSN is not set" in result.stderr
    assert result.stdout == ""


def test_error_log_is_one_event(
    lifespan_client: TestClient, sentry_events: list[Event]
) -> None:
    # Spec 34 door 4: an `error` log line is the team's alert; a warning is not.
    configure_logging()
    log = structlog.get_logger("tests.alerting")

    log.warning("bank_sync.sync_skipped", business_id="b-1")
    log.error(
        "bank_sync.sync_failed",
        business_id="b-1",
        connection_id="c-1",
        access_token=SANDBOX_TOKEN,
    )
    sentry_sdk.flush()

    assert len(sentry_events) == 1
    event = sentry_events[0]
    message = event.get("logentry", {}).get("message") or event.get("message")
    assert message == "bank_sync.sync_failed"
    assert SANDBOX_TOKEN not in json.dumps(event, default=str)
