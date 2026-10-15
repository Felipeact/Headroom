"""Spec 31: alert emails for bookkeepers who opted in (C22-C25)."""

import uuid

import pytest

from app.db import get_sessionmaker
from app.modules.accounts.models import Business
from app.modules.notifications import service as notifications_service
from tests.bookkeeper_support import client, sql
from tests.email_support import Mail
from tests.test_alert_check import Fake
from tests.test_alert_emails import (
    _registered,  # noqa: F401 - autouse: alert events reach the email handler
    alert_event,
    check,
    deliveries,
    fake,  # noqa: F401 - fixture: the fake forecast reader
    owned,
    the_alert,
)
from tests.test_bookkeeper_access import add_bookkeeper
from tests.test_businesses import Caller
from tests.test_weekly_digest import (
    TORONTO_8AM,
    business,
    digests,
    weekly_digest,
)
from tests.test_weekly_digest import (
    second_owner as digest_second_owner,
)

pytestmark = pytest.mark.usefixtures("migrated_database")


def bookkeeper_with_clerk(
    mail: Mail, business_id: uuid.UUID, email: str, *, opted_in: bool
) -> uuid.UUID:
    user_id = mail.user(email)
    sql(
        "INSERT INTO memberships (business_id, user_id, role, receive_alert_emails)"
        " VALUES (:b, :u, 'bookkeeper', :r)",
        b=business_id,
        u=user_id,
        r=opted_in,
    )
    return user_id


def test_toggle_alert_emails(mail: Mail) -> None:
    """C22."""
    owner = Caller()
    owner.post({"name": "Acme", "province": "ON", "time_zone": "America/Toronto"})
    business_id = owner.get("/v1/businesses").json()["items"][0]["id"]
    bookkeeper = add_bookkeeper(business_id)
    url = f"/v1/businesses/{business_id}/me/alert-emails"

    on = client.put(url, json={"enabled": True}, headers=bookkeeper.headers)
    assert on.status_code == 200
    assert on.json()["receive_alert_emails"] is True
    stored = sql(
        "SELECT receive_alert_emails FROM memberships WHERE user_id = :u",
        u=bookkeeper.id,
    )
    assert stored == [(True,)]
    off = client.put(url, json={"enabled": False}, headers=bookkeeper.headers)
    assert off.json()["receive_alert_emails"] is False

    assert (
        client.put(url, json={"enabled": True}, headers=owner.headers).status_code
        == 403
    )
    assert client.put(url, json={}, headers=bookkeeper.headers).status_code == 422
    assert (
        client.put(url, json={"enabled": "yes"}, headers=bookkeeper.headers).status_code
        == 422
    )


def test_opted_in_bookkeeper_gets_alert(mail: Mail, fake: Fake) -> None:  # noqa: F811
    """C23."""
    business_id = owned(mail, fake)
    opted = bookkeeper_with_clerk(mail, business_id, "pat@example.test", opted_in=True)
    quiet = bookkeeper_with_clerk(mail, business_id, "lee@example.test", opted_in=False)
    check(business_id)

    rows = deliveries(business_id)
    assert len(rows) == 2
    assert quiet not in {r.user_id for r in rows}
    (bookkeeper_row,) = [r for r in rows if r.user_id == opted]
    with get_sessionmaker()() as session:
        name = session.get(Business, business_id).name  # type: ignore[union-attr]
    assert bookkeeper_row.reason == (
        f"You're getting this email because you're a bookkeeper for {name} on Headroom."
    )
    assert len(mail.sender.sent) == 2
    assert "pat@example.test" in {e.to for e in mail.sender.sent}
    assert "lee@example.test" not in {e.to for e in mail.sender.sent}


def test_preferences_and_replay(mail: Mail, fake: Fake) -> None:  # noqa: F811
    """C24."""
    business_id = owned(mail, fake)
    opted = bookkeeper_with_clerk(mail, business_id, "pat@example.test", opted_in=True)
    mail.set_preferences(opted, alerts=False, weekly_digest=True)
    check(business_id)
    alert = the_alert(business_id)

    event = alert_event("alert.created", business_id, alert.id)
    notifications_service.email_alert(event)
    notifications_service.email_alert(event)

    rows = deliveries(business_id)
    assert len(rows) == 2
    (skipped,) = [r for r in rows if r.user_id == opted]
    assert skipped.state == "skipped"
    assert len(mail.sender.sent) == 1


def test_digest_owners_only(mail: Mail) -> None:
    """C25."""
    biz = business(mail)
    second = digest_second_owner(mail, biz, "sam@example.test")
    opted = bookkeeper_with_clerk(mail, biz.id, "pat@example.test", opted_in=True)
    weekly_digest(TORONTO_8AM)

    recipients = {r.user_id for r in digests(biz.id)}
    assert recipients == {biz.owner_id, second}
    assert opted not in recipients
