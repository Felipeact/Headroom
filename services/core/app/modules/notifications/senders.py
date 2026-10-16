"""The email port (spec 28, door 5): the only place that hands an email to a provider.

`get_email_sender` picks Resend or the console from `EMAIL_SENDER`; tests replace it with a
fake. Every failure is a `SendError` saying whether a later attempt can succeed, carrying
only the provider's error type, never the response body.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

import resend
from resend.exceptions import ResendError

from app.settings import get_settings

# Resend 409s that clear on their own; every other 409 means the request itself is wrong.
RETRYABLE_CONFLICTS = frozenset({"concurrent_idempotent_requests", "resource_locked"})


class SendError(Exception):
    def __init__(self, *, error_type: str, retryable: bool) -> None:
        super().__init__(f"send failed: {error_type}")
        self.error_type = error_type
        self.retryable = retryable


@dataclass(frozen=True)
class OutgoingEmail:
    to: str = field(repr=False)
    sender: str
    subject: str = field(repr=False)
    html: str = field(repr=False)
    text: str = field(repr=False)
    headers: Mapping[str, str] = field(repr=False)
    # The delivery's id: the provider drops a repeat within its window (Resend: 24 hours).
    idempotency_key: str


class EmailSender(Protocol):
    def send(self, email: OutgoingEmail) -> str:
        """Hand the email over; return the provider's message id. Raises `SendError`."""
        ...


def is_retryable(code: int, error_type: str) -> bool:
    """Whether Resend's error can clear on its own: rate limits, locks, server errors."""
    if code == 429 or code >= 500:
        return True
    return code == 409 and error_type in RETRYABLE_CONFLICTS


class ResendSender:
    def __init__(self, api_key: str) -> None:
        resend.api_key = api_key

    def send(self, email: OutgoingEmail) -> str:
        params: resend.Emails.SendParams = {
            "from": email.sender,
            "to": [email.to],
            "subject": email.subject,
            "html": email.html,
            "text": email.text,
            "headers": dict(email.headers),
        }
        options: resend.Emails.SendOptions = {"idempotency_key": email.idempotency_key}
        try:
            response = resend.Emails.send(params, options)
        except ResendError as exc:
            # The SDK turns a network failure into a 500 `HttpClientError`.
            try:
                code = int(exc.code)
            except (TypeError, ValueError):
                code = 500
            raise SendError(
                error_type=f"{code}_{exc.error_type}",
                retryable=is_retryable(code, exc.error_type),
            ) from None
        return response["id"]


class ConsoleSender:
    """Prints each email for local runs. Stdout, never the logger: logs leave the machine."""

    def send(self, email: OutgoingEmail) -> str:
        print(
            f"--- email (console) ---\nTo: {email.to}\nSubject: {email.subject}\n\n"
            f"{email.text}\n--- end email ---",
            flush=True,
        )
        return f"console-{email.idempotency_key}"


@lru_cache
def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.email_sender == "resend":
        assert settings.resend_api_key is not None  # Settings requires it for resend.
        return ResendSender(settings.resend_api_key)
    return ConsoleSender()
