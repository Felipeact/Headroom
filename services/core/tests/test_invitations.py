"""Spec 31: inviting a bookkeeper, accepting, removing, and the schema (C1-C16)."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.log import configure_logging
from app.modules.notifications.senders import SendError
from tests.bookkeeper_support import (
    OWNER_EMAIL,
    PAT,
    accept,
    client,
    expire_invitations,
    invite,
    owner_business,
    sha256,
    signed_in,
    sql,
    team,
    token_from,
)
from tests.email_support import Mail

pytestmark = pytest.mark.usefixtures("migrated_database")


def audit_actions(business_id: str) -> list[str]:
    rows = sql(
        "SELECT action FROM audit_log WHERE business_id = :b AND action LIKE ANY"
        " (ARRAY['invitation.%', 'member.%']) ORDER BY id",
        b=uuid.UUID(business_id),
    )
    return [r[0] for r in rows]


def invitation_rows(business_id: str) -> list[tuple[object, ...]]:
    return [
        tuple(r)
        for r in sql(
            "SELECT token_hash, email_hash, created_at, expires_at, accepted_at,"
            " accepted_by_user_id FROM invitations WHERE business_id = :b",
            b=uuid.UUID(business_id),
        )
    ]


def test_invite_stores_emails_and_audits(mail: Mail) -> None:
    """C1."""
    owner, business_id = owner_business(mail)
    response = invite(owner, business_id, "  Pat@Example.test ")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "expires_at"}

    (email,) = mail.sender.sent
    assert email.to == PAT
    token = token_from(mail)
    assert f"https://app.example.test/invite/{token}" in email.text
    assert email.subject == "Dana invited you to Harbor Street Plumbing on Headroom"

    ((_, _, created_at, expires_at, *_),) = invitation_rows(business_id)
    assert expires_at - created_at == timedelta(days=7)
    assert audit_actions(business_id) == ["invitation.created"]


def test_stores_only_hashes(mail: Mail, capsys: pytest.CaptureFixture[str]) -> None:
    """C2."""
    configure_logging()
    owner, business_id = owner_business(mail)
    assert invite(owner, business_id, "Pat@Example.test").status_code == 201
    token = token_from(mail)

    ((token_hash, email_hash, *_),) = invitation_rows(business_id)
    assert token_hash == sha256(token)
    assert email_hash == sha256(PAT)
    stored = sql(
        "SELECT row_to_json(i)::text FROM invitations i WHERE business_id = :b"
        " UNION ALL SELECT row_to_json(a)::text FROM audit_log a WHERE business_id = :b",
        b=uuid.UUID(business_id),
    )
    for (row,) in stored:
        assert PAT not in row.lower()
        assert token not in row
    logged = capsys.readouterr().out
    assert PAT not in logged.lower()
    assert token not in logged


def test_duplicate_invite_conflicts(mail: Mail) -> None:
    """C3."""
    owner, business_id = owner_business(mail)
    assert invite(owner, business_id, PAT).status_code == 201
    sent = len(mail.sender.sent)

    pending = invite(owner, business_id, "pat@EXAMPLE.test")
    assert pending.status_code == 409
    own = invite(owner, business_id, OWNER_EMAIL.upper())
    assert own.status_code == 409

    assert len(invitation_rows(business_id)) == 1
    assert len(mail.sender.sent) == sent

    member = team(mail)
    sent = len(mail.sender.sent)
    assert invite(member.owner, member.business_id, PAT).status_code == 409
    assert len(mail.sender.sent) == sent


def test_send_failure_stores_nothing(mail: Mail) -> None:
    """C4."""
    owner, business_id = owner_business(mail)
    mail.sender.fail_next(SendError(error_type="429_rate_limit", retryable=True))
    response = invite(owner, business_id, PAT)
    assert response.status_code == 503
    assert invitation_rows(business_id) == []
    assert audit_actions(business_id) == []
    assert invite(owner, business_id, PAT).status_code == 201


@pytest.mark.parametrize("address", ["not-an-email", "", "a" * 255 + "@example.test"])
def test_invalid_address_is_422(mail: Mail, address: str) -> None:
    """C5."""
    owner, business_id = owner_business(mail)
    assert invite(owner, business_id, address).status_code == 422
    assert invitation_rows(business_id) == []


def test_accept_adds_bookkeeper(mail: Mail) -> None:
    """C6."""
    owner, business_id = owner_business(mail)
    pat = signed_in(mail, PAT)
    assert invite(owner, business_id, PAT).status_code == 201

    response = accept(pat, token_from(mail))
    assert response.status_code == 200
    assert response.json()["id"] == business_id
    assert response.json()["role"] == "bookkeeper"

    ((role, receives),) = sql(
        "SELECT role, receive_alert_emails FROM memberships"
        " WHERE business_id = :b AND user_id = :u",
        b=uuid.UUID(business_id),
        u=pat.id,
    )
    assert (role, receives) == ("bookkeeper", False)
    ((_, _, _, _, accepted_at, accepted_by),) = invitation_rows(business_id)
    assert accepted_at is not None
    assert accepted_by == pat.id
    assert audit_actions(business_id) == ["invitation.created", "invitation.accepted"]


def test_expired_invitation_cannot_be_accepted(mail: Mail) -> None:
    """C7."""
    owner, business_id = owner_business(mail)
    pat = signed_in(mail, PAT)
    assert invite(owner, business_id, PAT).status_code == 201
    token = token_from(mail)

    expire_invitations(business_id)
    assert client.get(f"/v1/invitations/{token}", headers=pat.headers).json() == {
        "business_name": "Harbor Street Plumbing",
        "status": "expired",
    }
    assert accept(pat, token).status_code == 410
    assert [
        m
        for m in owner.get(f"/v1/businesses/{business_id}/members").json()["items"]
        if m["role"] == "bookkeeper"
    ] == []

    sql(
        "UPDATE invitations SET expires_at = now() + interval '1 minute'"
        " WHERE business_id = :b",
        b=uuid.UUID(business_id),
    )
    assert accept(pat, token).status_code == 200


def test_wrong_address_is_403(mail: Mail) -> None:
    """C8."""
    owner, business_id = owner_business(mail)
    assert invite(owner, business_id, PAT).status_code == 201
    token = token_from(mail)
    lee = signed_in(mail, "lee@example.test")
    nobody = signed_in(mail, None)

    assert accept(lee, token).status_code == 403
    assert accept(nobody, token).status_code == 403
    assert not sql(
        "SELECT 1 FROM memberships WHERE business_id = :b AND role = 'bookkeeper'",
        b=uuid.UUID(business_id),
    )


def test_accept_twice_is_idempotent(mail: Mail) -> None:
    """C9."""
    owner, business_id = owner_business(mail)
    pat = signed_in(mail, PAT)
    assert invite(owner, business_id, PAT).status_code == 201
    token = token_from(mail)

    assert accept(pat, token).status_code == 200
    assert accept(pat, token).status_code == 200
    rows = sql(
        "SELECT 1 FROM memberships WHERE business_id = :b AND user_id = :u",
        b=uuid.UUID(business_id),
        u=pat.id,
    )
    assert len(rows) == 1
    assert audit_actions(business_id).count("invitation.accepted") == 1


def test_used_invitation_other_user_403(mail: Mail) -> None:
    """C10."""
    owner, business_id = owner_business(mail)
    pat = signed_in(mail, PAT)
    other = signed_in(mail, PAT)
    assert invite(owner, business_id, PAT).status_code == 201
    token = token_from(mail)
    assert accept(pat, token).status_code == 200

    assert accept(other, token).status_code == 403
    assert not sql(
        "SELECT 1 FROM memberships WHERE business_id = :b AND user_id = :u",
        b=uuid.UUID(business_id),
        u=other.id,
    )


def test_unknown_token_is_404(mail: Mail) -> None:
    """C11."""
    caller = signed_in(mail, PAT)
    unknown = "x" * 43
    assert (
        client.get(f"/v1/invitations/{unknown}", headers=caller.headers).status_code
        == 404
    )
    assert accept(caller, unknown).status_code == 404


def test_owner_cannot_accept_own_invitation(mail: Mail) -> None:
    """C12."""
    owner, business_id = owner_business(mail)
    assert invite(owner, business_id, PAT).status_code == 201
    # The owner later changes their primary address to the invited one.
    mail.clerk.set(owner.sub, PAT, "Dana")

    assert accept(owner, token_from(mail)).status_code == 409
    ((role,),) = sql(
        "SELECT role FROM memberships WHERE business_id = :b AND user_id = :u",
        b=uuid.UUID(business_id),
        u=owner.id,
    )
    assert role == "owner"


def test_remove_bookkeeper(mail: Mail) -> None:
    """C13."""
    t = team(mail)
    dashboard = t.path("/dashboard")
    assert client.get(dashboard, headers=t.bookkeeper.headers).status_code == 200

    removed = client.delete(
        t.path(f"/members/{t.bookkeeper.id}"), headers=t.owner.headers
    )
    assert removed.status_code == 204
    assert client.get(dashboard, headers=t.bookkeeper.headers).status_code == 404
    assert audit_actions(t.business_id)[-1] == "member.removed"


def test_remove_owner_conflicts_and_stranger_404(mail: Mail) -> None:
    """C14."""
    t = team(mail)
    owner_path = t.path(f"/members/{t.owner.id}")
    assert client.delete(owner_path, headers=t.owner.headers).status_code == 409
    assert sql(
        "SELECT 1 FROM memberships WHERE business_id = :b AND user_id = :u",
        b=uuid.UUID(t.business_id),
        u=t.owner.id,
    )
    missing = t.path(f"/members/{t.stranger.id}")
    assert client.delete(missing, headers=t.owner.headers).status_code == 404


def test_members_list_with_and_without_clerk(mail: Mail) -> None:
    """C15."""
    t = team(mail)
    assert invite(t.owner, t.business_id, "later@example.test").status_code == 201

    listed = client.get(t.path("/members"), headers=t.owner.headers)
    assert listed.status_code == 200
    body = listed.json()
    by_role = {m["role"]: m for m in body["items"]}
    assert set(by_role) == {"owner", "bookkeeper"}
    assert by_role["bookkeeper"]["email"] == PAT
    assert by_role["owner"]["name"] == "Dana"
    assert [set(i) for i in body["invitations"]] == [{"id", "created_at", "expires_at"}]

    mail.clerk.unavailable = 10
    degraded = client.get(t.path("/members"), headers=t.owner.headers)
    assert degraded.status_code == 200
    assert {m["role"] for m in degraded.json()["items"]} == {"owner", "bookkeeper"}
    assert all(
        m["name"] is None and m["email"] is None for m in degraded.json()["items"]
    )


def test_schema_constraints(mail: Mail) -> None:
    """C16."""
    t = team(mail)
    business = uuid.UUID(t.business_id)

    def violates(statement: str, **params: object) -> str:
        with pytest.raises(IntegrityError) as raised:
            sql(statement, **params)
        return str(raised.value)

    insert_member = (
        "INSERT INTO memberships (business_id, user_id, role) VALUES (:b, :u, :r)"
    )
    assert "ck_memberships_role" in violates(
        insert_member, b=business, u=t.stranger.id, r="viewer"
    )
    sql(insert_member, b=business, u=t.stranger.id, r="bookkeeper")
    ((default,),) = sql(
        "SELECT receive_alert_emails FROM memberships WHERE user_id = :u",
        u=t.stranger.id,
    )
    assert default is False

    insert_invitation = (
        "INSERT INTO invitations (id, business_id, invited_by_user_id, token_hash,"
        " email_hash, expires_at) VALUES (:id, :b, :u, :t, :e, now())"
    )
    sql(insert_invitation, id=uuid.uuid4(), b=business, u=t.owner.id, t="t1", e="e1")
    assert "uq_invitations_token_hash" in violates(
        insert_invitation, id=uuid.uuid4(), b=business, u=t.owner.id, t="t1", e="e2"
    )
    assert "uq_invitations_pending_business_id_email_hash" in violates(
        insert_invitation, id=uuid.uuid4(), b=business, u=t.owner.id, t="t3", e="e1"
    )
