"""Callers, businesses and invitations for the bookkeeper tests (spec 31)."""

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_sessionmaker
from app.main import app
from tests.email_support import Mail
from tests.test_businesses import HARBOR, Caller

client = TestClient(app)

OWNER_EMAIL = "dana@example.test"
PAT = "pat@example.test"
LINK = re.compile(r"/invite/([A-Za-z0-9_-]+)")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def signed_in(mail: Mail, email: str | None, first_name: str | None = "Pat") -> Caller:
    """A new signed-in user whose primary address in the fake Clerk is `email`."""
    caller = Caller()
    mail.clerk.set(caller.sub, email, first_name)
    return caller


@dataclass
class Team:
    """An owner with a business, a bookkeeper who accepted, and a stranger."""

    owner: Caller
    business_id: str
    bookkeeper: Caller
    stranger: Caller

    def path(self, tail: str = "") -> str:
        return f"/v1/businesses/{self.business_id}{tail}"


def owner_business(mail: Mail) -> tuple[Caller, str]:
    owner = signed_in(mail, OWNER_EMAIL, "Dana")
    created = owner.post(HARBOR)
    assert created.status_code == 201
    return owner, created.json()["id"]


def invite(owner: Caller, business_id: str, email: str) -> Any:
    return client.post(
        f"/v1/businesses/{business_id}/invitations",
        json={"email": email},
        headers=owner.headers,
    )


def token_from(mail: Mail) -> str:
    """The token in the last invitation email sent."""
    found = LINK.search(mail.sender.sent[-1].text)
    assert found is not None
    return found.group(1)


def accept(caller: Caller, token: str) -> Any:
    return client.post(f"/v1/invitations/{token}/accept", headers=caller.headers)


def team(mail: Mail) -> Team:
    owner, business_id = owner_business(mail)
    pat = signed_in(mail, PAT)
    assert invite(owner, business_id, PAT).status_code == 201
    assert accept(pat, token_from(mail)).status_code == 200
    return Team(owner, business_id, pat, signed_in(mail, "stranger@example.test"))


def sql(statement: str, **params: object) -> list[Any]:
    with get_sessionmaker()() as session:
        rows = session.execute(text(statement), params)
        result = list(rows.all()) if rows.returns_rows else []
        session.commit()
    return result


def expire_invitations(business_id: str) -> None:
    sql(
        "UPDATE invitations SET expires_at = now() - interval '1 second'"
        " WHERE business_id = :b",
        b=uuid.UUID(business_id),
    )
