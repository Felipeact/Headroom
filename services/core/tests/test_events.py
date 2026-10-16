"""Spec 14: the in-process event bus (AD-047)."""

import json
import uuid
from collections.abc import Iterator

import pytest

from app import events
from app.log import configure_logging

BUSINESS = uuid.UUID("9b2f6c1e-0000-4000-8000-000000000014")


@pytest.fixture
def subscribed() -> Iterator[list[tuple[str, events.Handler]]]:
    added: list[tuple[str, events.Handler]] = []
    yield added
    for name, handler in added:
        events.unsubscribe(name, handler)


def subscribe(
    added: list[tuple[str, events.Handler]], name: str, handler: events.Handler
) -> None:
    events.subscribe(name, handler)
    added.append((name, handler))


def test_publish_order_and_name(subscribed: list[tuple[str, events.Handler]]) -> None:
    calls: list[tuple[str, events.Event]] = []

    def h1(event: events.Event) -> None:
        calls.append(("h1", event))

    def h2(event: events.Event) -> None:
        calls.append(("h2", event))

    def h3(event: events.Event) -> None:
        calls.append(("h3", event))

    subscribe(subscribed, "a.happened", h1)
    subscribe(subscribed, "a.happened", h2)
    subscribe(subscribed, "b.happened", h3)
    event = events.Event(name="a.happened", business_id=BUSINESS, payload={"n": 1})

    events.publish(event)

    assert calls == [("h1", event), ("h2", event)]


def test_handler_failure_isolated(
    subscribed: list[tuple[str, events.Handler]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def before(event: events.Event) -> None:
        calls.append("before")

    def broken(event: events.Event) -> None:
        raise RuntimeError("secret detail 4471")

    def after(event: events.Event) -> None:
        calls.append("after")

    for handler in (before, broken, after):
        subscribe(subscribed, "c.happened", handler)
    configure_logging()
    capsys.readouterr()

    events.publish(events.Event(name="c.happened", business_id=BUSINESS, payload={}))

    assert calls == ["before", "after"]
    out = capsys.readouterr().out
    lines = [json.loads(line) for line in out.splitlines()]
    failed = [line for line in lines if line["event"] == "event.handler_failed"]
    assert len(failed) == 1
    assert failed[0]["event_name"] == "c.happened"
    assert failed[0]["handler"].endswith("broken")
    assert failed[0]["error_type"] == "RuntimeError"
    assert "secret detail 4471" not in out
