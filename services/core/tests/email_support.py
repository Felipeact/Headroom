"""Fakes and helpers for the email tests (spec 28). No test calls Resend or Clerk."""

import json
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment

from app.db import get_sessionmaker
from app.modules.accounts import clerk
from app.modules.accounts import service as accounts_service
from app.modules.notifications import rendering, senders
from app.modules.notifications import service as notifications_service
from app.modules.notifications.models import EmailDelivery, EmailKind
from app.modules.notifications.senders import OutgoingEmail, SendError

# The test-only email of the checks: subject "Test subject", a heading and a paragraph.
TEST_TEMPLATES = {
    "test_message.subject.txt": "Test subject",
    "test_message.html": (
        '{% extends "base.html" %}{% block content %}'
        "<h1>{{ heading }}</h1><p>{% if first_name %}Hi {{ first_name }}, {% endif %}"
        "{{ body }}</p>{% endblock %}"
    ),
    "test_message.txt": (
        '{% extends "base.txt" %}{% block content %}{{ heading }}\n\n'
        "{% if first_name %}Hi {{ first_name }}, {% endif %}{{ body }}{% endblock %}"
    ),
}
REASON = (
    "You're getting this email because you're an owner of Harbor Street Plumbing"
    " on Headroom."
)


class FakeEmailSender:
    """Records every email; `fail_next` queues errors raised by the next sends."""

    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []
        self.calls = 0
        self._failures: list[SendError] = []
        # Recipient address -> the error every send to it raises.
        self.fail_to: dict[str, SendError] = {}

    def fail_next(self, *errors: SendError) -> None:
        self._failures.extend(errors)

    def send(self, email: OutgoingEmail) -> str:
        self.calls += 1
        if email.to in self.fail_to:
            raise self.fail_to[email.to]
        if self._failures:
            raise self._failures.pop(0)
        self.sent.append(email)
        return f"fake-{len(self.sent)}"


class FakeClerkUsers:
    """Clerk users by Clerk ID; `unavailable` makes the next lookups time out."""

    def __init__(self) -> None:
        self.users: dict[str, clerk.ClerkUser] = {}
        self.unavailable = 0

    def set(
        self, clerk_user_id: str, email: str | None, first_name: str | None = "Dana"
    ) -> None:
        addresses = (("idn_other", "old@example.test"),)
        if email is not None:
            addresses += (("idn_primary", email),)
        self.users[clerk_user_id] = clerk.ClerkUser(
            primary_email_address_id="idn_primary" if email is not None else None,
            email_addresses=addresses,
            first_name=first_name,
        )

    def get(self, clerk_user_id: str) -> clerk.ClerkUser | None:
        if self.unavailable:
            self.unavailable -= 1
            raise clerk.ClerkUnavailableError("ReadTimeout")
        return self.users.get(clerk_user_id)


@dataclass
class Mail:
    sender: FakeEmailSender
    clerk: FakeClerkUsers
    business_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def user(
        self, email: str | None = "dana@example.test", first_name: str | None = "Dana"
    ) -> uuid.UUID:
        """A new user with this primary address in the fake Clerk."""
        clerk_user_id = f"user_mail_{uuid.uuid4().hex[:12]}"
        with get_sessionmaker()() as session:
            user_id = accounts_service.get_or_create_user(session, clerk_user_id).id
        self.clerk.set(clerk_user_id, email, first_name)
        return user_id

    def clerk_id(self, user_id: uuid.UUID) -> str:
        from app.modules.accounts import repository

        with get_sessionmaker()() as session:
            found = repository.clerk_user_id(session, user_id)
        assert found is not None
        return found

    def request(
        self,
        user_id: uuid.UUID,
        *,
        key: str = "evt-1",
        kind: EmailKind = "alert",
        params: Mapping[str, Any] | None = None,
        deliver: bool = True,
    ) -> uuid.UUID | None:
        """Request a test email, commit, and attempt it once, as a caller would."""
        with get_sessionmaker()() as session:
            delivery_id = notifications_service.request_email(
                session,
                dedup_key=key,
                user_id=user_id,
                business_id=self.business_id,
                kind=kind,
                template="test_message",
                params=params or {"heading": "Cash gap", "body": "Cash falls."},
                reason=REASON,
            )
            session.commit()
        if delivery_id is not None and deliver:
            notifications_service.deliver(delivery_id)
        return delivery_id

    def deliveries(self, user_id: uuid.UUID) -> list[EmailDelivery]:
        from sqlalchemy import select

        with get_sessionmaker()() as session:
            rows = list(
                session.scalars(
                    select(EmailDelivery)
                    .where(EmailDelivery.user_id == user_id)
                    .order_by(EmailDelivery.created_at, EmailDelivery.dedup_key)
                )
            )
            session.expunge_all()
        return rows

    def token(self, user_id: uuid.UUID) -> str:
        with get_sessionmaker()() as session:
            return notifications_service.unsubscribe_token(session, user_id)

    def set_preferences(
        self, user_id: uuid.UUID, *, alerts: bool, weekly_digest: bool
    ) -> None:
        with get_sessionmaker()() as session:
            notifications_service.set_preferences(
                session, user_id, alerts=alerts, weekly_digest=weekly_digest
            )


def with_test_templates() -> Environment:
    base = rendering.environment()
    env = base.overlay(loader=ChoiceLoader([DictLoader(TEST_TEMPLATES), base.loader]))  # type: ignore[list-item]
    return env


@pytest.fixture
def mail(monkeypatch: pytest.MonkeyPatch) -> Iterator[Mail]:
    """Fake sender and Clerk, and the test-only template, for one test."""
    fake_sender = FakeEmailSender()
    fake_clerk = FakeClerkUsers()
    monkeypatch.setattr(senders, "get_email_sender", lambda: fake_sender)
    monkeypatch.setattr(clerk, "get_clerk_users", lambda: fake_clerk)
    env = with_test_templates()
    monkeypatch.setattr(rendering, "environment", lambda: env)
    yield Mail(sender=fake_sender, clerk=fake_clerk)


def log_lines(out: str) -> list[dict[str, Any]]:
    lines = []
    for line in out.splitlines():
        try:
            lines.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return lines
