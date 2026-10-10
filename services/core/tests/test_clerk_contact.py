"""Spec 28 C8: a user's contact comes from Clerk's primary address (door 6)."""

import uuid
from typing import Any

import httpx
import pytest
from clerk_backend_api import models

from app.db import get_sessionmaker
from app.modules.accounts import clerk
from app.modules.accounts import service as accounts_service
from app.modules.accounts.clerk import BackendClerkUsers

pytestmark = pytest.mark.usefixtures("migrated_database")


def clerk_user(
    primary: str | None, addresses: list[tuple[str, str]], first_name: str | None
) -> models.User:
    return models.User.model_validate(
        {
            "id": "user_x",
            "object": "user",
            "primary_email_address_id": primary,
            "primary_phone_number_id": None,
            "primary_web3_wallet_id": None,
            "first_name": first_name,
            "last_name": None,
            "username": None,
            "image_url": "https://img.example.test/x.png",
            "has_image": False,
            "external_id": None,
            "public_metadata": {},
            "private_metadata": {},
            "unsafe_metadata": {},
            "email_addresses": [
                {
                    "id": address_id,
                    "object": "email_address",
                    "email_address": address,
                    "reserved": False,
                    "verification": None,
                    "linked_to": [],
                    "created_at": 1,
                    "updated_at": 1,
                }
                for address_id, address in addresses
            ],
            "phone_numbers": [],
            "web3_wallets": [],
            "passkeys": [],
            "password_enabled": False,
            "two_factor_enabled": False,
            "totp_enabled": False,
            "backup_code_enabled": False,
            "external_accounts": [],
            "saml_accounts": [],
            "enterprise_accounts": [],
            "last_sign_in_at": None,
            "banned": False,
            "locked": False,
            "lockout_expires_in_seconds": None,
            "verification_attempts_remaining": None,
            "updated_at": 1,
            "created_at": 1,
            "delete_self_enabled": True,
            "create_organization_enabled": True,
            "last_active_at": None,
            "mfa_enabled_at": None,
            "mfa_disabled_at": None,
            "legal_accepted_at": None,
        }
    )


class FakeUsersApi:
    def __init__(self, result: Any) -> None:
        self.result = result

    def get(self, *, user_id: str) -> Any:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def backend(result: Any) -> BackendClerkUsers:
    users = BackendClerkUsers("sk_test_not_a_key")
    users._clerk = type("FakeClerk", (), {"users": FakeUsersApi(result)})()  # type: ignore[assignment]
    return users


def contact_for(
    monkeypatch: pytest.MonkeyPatch, result: Any
) -> accounts_service.Contact | None:
    monkeypatch.setattr(clerk, "get_clerk_users", lambda: backend(result))
    with get_sessionmaker()() as session:
        user = accounts_service.get_or_create_user(
            session, f"user_contact_{uuid.uuid4().hex[:12]}"
        )
        return accounts_service.contact(session, user.id)


def not_found() -> models.ClerkErrors:
    response = httpx.Response(
        404, json={"errors": []}, request=httpx.Request("GET", "https://x.test")
    )
    return models.ClerkErrors(models.ClerkErrorsData(errors=[]), response)


def test_primary_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """C8: the address whose id is the primary one, not the first; and the first name."""
    user = clerk_user(
        "idn_2",
        [("idn_1", "old@example.test"), ("idn_2", "dana@example.test")],
        "Dana",
    )

    assert contact_for(monkeypatch, user) == accounts_service.Contact(
        email="dana@example.test", first_name="Dana"
    )


def test_primary_address_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """C8: no primary address id gives no contact."""
    user = clerk_user(None, [("idn_1", "old@example.test")], "Dana")

    assert contact_for(monkeypatch, user) is None


def test_primary_address_user_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """C8: Clerk's 404 gives no contact."""
    assert contact_for(monkeypatch, not_found()) is None


def test_primary_address_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A network error is `ContactUnavailableError`, which the sender retries (C20)."""
    with pytest.raises(accounts_service.ContactUnavailableError):
        contact_for(monkeypatch, httpx.ReadTimeout("timed out"))
