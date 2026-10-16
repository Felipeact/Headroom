"""Spec 31: the invitation email (C26). No database: it renders through a fake sender."""

import html
import re

import pytest

from app.modules.notifications import senders
from app.modules.notifications import service as notifications_service
from tests.email_support import FakeEmailSender

WEB = "https://app.example.test"
TOKEN = "tok_AbC-123_xyz"


@pytest.fixture
def sender(monkeypatch: pytest.MonkeyPatch) -> FakeEmailSender:
    fake = FakeEmailSender()
    monkeypatch.setattr(senders, "get_email_sender", lambda: fake)
    return fake


def test_renders_invitation(sender: FakeEmailSender) -> None:
    """C26."""
    notifications_service.send_invitation(
        "pat@example.test", "Harbor Street Plumbing", "Dana", TOKEN
    )
    (email,) = sender.sent
    assert email.to == "pat@example.test"
    assert email.subject == "Dana invited you to Harbor Street Plumbing on Headroom"
    link = f"{WEB}/invite/{TOKEN}"
    assert re.findall(r'href="([^"]+)"', email.html) == [link]
    assert re.findall(r"https?://\S+", email.text) == [link]
    reason = (
        "You're getting this email because Dana invited you to Harbor Street"
        " Plumbing on Headroom."
    )
    assert reason in html.unescape(email.html)
    assert reason in email.text
    for body in (email.html, email.text):
        assert "unsubscribe" not in body.lower()
        assert "Email preferences" not in body
    assert dict(email.headers) == {}


def test_inviter_without_a_first_name(sender: FakeEmailSender) -> None:
    notifications_service.send_invitation(
        "pat@example.test", "Harbor Street Plumbing", None, TOKEN
    )
    assert sender.sent[0].subject.startswith("An owner invited you to")


def test_send_failure_is_reported(sender: FakeEmailSender) -> None:
    sender.fail_next(senders.SendError(error_type="500_server", retryable=True))
    with pytest.raises(notifications_service.InvitationNotSentError):
        notifications_service.send_invitation(
            "pat@example.test", "Harbor Street Plumbing", "Dana", TOKEN
        )
