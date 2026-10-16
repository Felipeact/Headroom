"""The Clerk Backend API port: the only outbound call to Clerk (spec 28, door 6).

Headroom stores no email address (AD-020). When an email is sent, the address and first
name are read from Clerk through `get_clerk_users`, which tests replace with a fake.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx
from clerk_backend_api import Clerk, models

from app.settings import get_settings

TIMEOUT_MS = 10_000


class ClerkUnavailableError(Exception):
    """Clerk could not answer now (network, rate limit or server error); try again later."""

    def __init__(self, error_type: str) -> None:
        super().__init__(f"Clerk unavailable: {error_type}")
        self.error_type = error_type


@dataclass(frozen=True)
class ClerkUser:
    primary_email_address_id: str | None
    # (id, address) for every address on the user, in Clerk's order.
    email_addresses: tuple[tuple[str, str], ...]
    first_name: str | None


class ClerkUsers(Protocol):
    def get(self, clerk_user_id: str) -> ClerkUser | None:
        """The Clerk user, or None when Clerk has no such user."""
        ...


class BackendClerkUsers:
    def __init__(self, secret_key: str) -> None:
        self._clerk = Clerk(bearer_auth=secret_key, timeout_ms=TIMEOUT_MS)

    def get(self, clerk_user_id: str) -> ClerkUser | None:
        try:
            user = self._clerk.users.get(user_id=clerk_user_id)
        except models.ClerkBaseError as exc:
            if exc.status_code == 404:
                return None
            raise ClerkUnavailableError(f"http_{exc.status_code}") from None
        except (httpx.HTTPError, models.NoResponseError) as exc:
            raise ClerkUnavailableError(type(exc).__name__) from None
        return ClerkUser(
            primary_email_address_id=user.primary_email_address_id,
            email_addresses=tuple(
                (address.id, address.email_address)
                for address in user.email_addresses
                if address.id is not None
            ),
            first_name=user.first_name,
        )


@lru_cache
def get_clerk_users() -> ClerkUsers:
    return BackendClerkUsers(get_settings().clerk_secret_key)
