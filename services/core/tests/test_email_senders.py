"""Spec 28: the senders (C4, C13, C15) and the module's shape (C19)."""

import tomllib
import uuid
from pathlib import Path
from typing import Any

import pytest
import resend

from app.modules.notifications import senders
from app.modules.notifications import service as notifications_service
from app.modules.notifications.senders import (
    ConsoleSender,
    OutgoingEmail,
    ResendSender,
    get_email_sender,
)
from tests.email_support import Mail

CORE = Path(__file__).resolve().parents[1]

EMAIL = OutgoingEmail(
    to="dana@example.test",
    sender="Headroom <test@example.test>",
    subject="Test subject",
    html="<p>Hi</p>",
    text="Hi there",
    headers={
        "List-Unsubscribe": "<https://api.example.test/v1/unsubscribe/tok>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
    idempotency_key="0f8f4a5e-1111-4222-8333-444455556666",
)


def test_resend_sender_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """C4, C13: Resend gets the idempotency key as an option and the headers as params."""
    calls: list[tuple[Any, Any]] = []

    def fake_send(params: Any, options: Any = None) -> dict[str, str]:
        calls.append((params, options))
        return {"id": "re_msg_1"}

    monkeypatch.setattr(resend.Emails, "send", fake_send)

    provider_id = ResendSender("re_test_key").send(EMAIL)

    assert provider_id == "re_msg_1"
    [(params, options)] = calls
    assert options == {"idempotency_key": EMAIL.idempotency_key}
    assert params == {
        "from": "Headroom <test@example.test>",
        "to": ["dana@example.test"],
        "subject": "Test subject",
        "html": "<p>Hi</p>",
        "text": "Hi there",
        "headers": {
            "List-Unsubscribe": "<https://api.example.test/v1/unsubscribe/tok>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }


def test_console_sender(capsys: pytest.CaptureFixture[str]) -> None:
    """C15: the console sender prints the recipient, subject and text part."""
    ConsoleSender().send(EMAIL)

    out = capsys.readouterr().out
    assert "To: dana@example.test" in out
    assert "Subject: Test subject" in out
    assert "Hi there" in out


@pytest.mark.usefixtures("migrated_database")
def test_console_sender_never_calls_resend(
    mail: Mail, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C15: with EMAIL_SENDER=console a delivery is sent and Resend is never called."""

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Resend was called")

    monkeypatch.setattr(resend.Emails, "send", refuse)
    # The real factory, which reads EMAIL_SENDER=console (conftest), not the fixture's fake.
    get_email_sender.cache_clear()
    monkeypatch.setattr(senders, "get_email_sender", get_email_sender)
    user = mail.user()

    delivery_id = mail.request(user)

    assert delivery_id is not None
    assert [row.state for row in mail.deliveries(user)] == ["sent"]
    assert isinstance(senders.get_email_sender(), ConsoleSender)


def test_module_layout() -> None:
    """C19: the three packages are dependencies, and the module has the AD-023 files."""
    pyproject = tomllib.loads((CORE / "pyproject.toml").read_text(encoding="utf-8"))
    names = {
        dep.split(">")[0].split("=")[0].split("[")[0].strip()
        for dep in pyproject["project"]["dependencies"]
    }
    assert {"resend", "jinja2", "clerk-backend-api"} <= names
    lock = (CORE / "uv.lock").read_text(encoding="utf-8")
    for name in ("resend", "jinja2", "clerk-backend-api"):
        assert f'name = "{name}"' in lock

    module = CORE / "app" / "modules" / "notifications"
    for name in ("api.py", "service.py", "models.py", "repository.py"):
        assert (module / name).is_file(), name
    env = (CORE / "migrations" / "env.py").read_text(encoding="utf-8")
    assert "import app.modules.notifications.models" in env
    assert callable(notifications_service.request_email)
    assert uuid.UUID(EMAIL.idempotency_key)
