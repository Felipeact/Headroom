import hashlib
import secrets
import uuid
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

import structlog
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.modules.accounts import clerk, repository
from app.modules.accounts.models import Business, Membership, User

OWNER_INDEX = "uq_memberships_owner_user_id"

log = structlog.get_logger(__name__)


class Role(StrEnum):
    OWNER = "owner"
    BOOKKEEPER = "bookkeeper"


INVITATION_DAYS = 7


class AlreadyOwnsBusinessError(Exception):
    """The user already owns a business; v1 allows one per owner."""


class AlreadyMemberError(Exception):
    """The address, or the accepting user, is already a member of the business."""


class AlreadyInvitedError(Exception):
    """The address already has a pending invitation to the business."""


class InvitationNotFoundError(Exception):
    """No invitation has this token."""


class InvitationExpiredError(Exception):
    """The invitation is older than 7 days."""


class WrongAddressError(Exception):
    """The signed-in user's primary address is not the invited one, or it is spent."""


class MemberNotFoundError(Exception):
    """The user is not a member of the business."""


class CannotRemoveOwnerError(Exception):
    """Owners are not removed from their business."""


@dataclass(frozen=True)
class MemberBusiness:
    """A business as one of its members sees it."""

    id: uuid.UUID
    name: str
    province: str
    time_zone: str
    country: str
    currency: str
    role: str
    created_at: datetime


def _view(business: Business, role: str) -> MemberBusiness:
    return MemberBusiness(
        id=business.id,
        name=business.name,
        province=business.province,
        time_zone=business.time_zone,
        country=business.country,
        currency=business.currency,
        role=role,
        created_at=business.created_at,
    )


ContactUnavailableError = clerk.ClerkUnavailableError


@dataclass(frozen=True)
class Contact:
    """Where to email a user, read from Clerk at the moment of sending (spec 28)."""

    email: str
    first_name: str | None


def contact(session: Session, user_id: uuid.UUID) -> Contact | None:
    """The user's primary email address and first name, from Clerk.

    None when the user, their Clerk user, or a primary address does not exist. Raises
    `ContactUnavailableError` when Clerk cannot answer now. Nothing read here is stored.
    """
    clerk_user_id = repository.clerk_user_id(session, user_id)
    if clerk_user_id is None:
        return None
    user = clerk.get_clerk_users().get(clerk_user_id)
    if user is None or user.primary_email_address_id is None:
        return None
    for address_id, address in user.email_addresses:
        if address_id == user.primary_email_address_id:
            return Contact(email=address, first_name=user.first_name or None)
    return None


def get_or_create_user(session: Session, clerk_user_id: str) -> User:
    """Return the user for a verified Clerk user ID, creating the row on first sight.

    Safe to call concurrently: the unique `clerk_user_id` decides which insert wins, and
    every caller gets the same row. Commits the session.
    """
    user = repository.get_or_insert_user(session, clerk_user_id)
    session.commit()
    return user


def create_business(
    session: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    province: str,
    time_zone: str,
) -> MemberBusiness:
    """Create a business with `user_id` as its owner, in one transaction.

    Raises `AlreadyOwnsBusinessError` when the user owns one already, including when two
    creates race: `uq_memberships_owner_user_id` decides, and the loser's business row is
    rolled back with its membership. Commits the session.
    """
    if repository.owns_a_business(session, user_id):
        session.rollback()
        raise AlreadyOwnsBusinessError
    try:
        business = repository.insert_business(
            session, name=name, province=province, time_zone=time_zone
        )
        repository.insert_membership(
            session, business_id=business.id, user_id=user_id, role=Role.OWNER
        )
    except IntegrityError as exc:
        session.rollback()
        orig = exc.orig
        if (
            isinstance(orig, UniqueViolation)
            and orig.diag.constraint_name == OWNER_INDEX
        ):
            raise AlreadyOwnsBusinessError from None
        raise
    view = _view(business, Role.OWNER)
    session.commit()
    log.info("business.created", business_id=str(view.id), user_id=str(user_id))
    return view


def list_businesses(session: Session, user_id: uuid.UUID) -> list[MemberBusiness]:
    """The businesses `user_id` is a member of, oldest membership first."""
    return [
        _view(business, role)
        for business, role in repository.businesses_for_user(session, user_id)
    ]


def get_membership(
    session: Session, *, business_id: uuid.UUID, user_id: uuid.UUID
) -> Membership | None:
    """The user's membership in the business, or None when they are not a member."""
    return repository.get_membership(session, business_id=business_id, user_id=user_id)


def get_business(
    session: Session, *, business_id: uuid.UUID, role: str
) -> MemberBusiness:
    """The business, for a caller whose membership `require_member` has already checked."""
    return _view(repository.get_business(session, business_id), role)


def owner_ids(session: Session, *, business_id: uuid.UUID) -> list[uuid.UUID]:
    """The user IDs of the business's owners, oldest membership first.

    Who gets the weekly digest (spec 30).
    """
    return repository.member_ids(session, business_id=business_id, roles=[Role.OWNER])


@dataclass(frozen=True)
class Recipient:
    """A member who gets the business's alert emails, and the role that earned it."""

    user_id: uuid.UUID
    role: str


def alert_recipients(session: Session, *, business_id: uuid.UUID) -> list[Recipient]:
    """The owners, and the bookkeepers who turned alert emails on, oldest first (spec 31)."""
    return [
        Recipient(user_id=user_id, role=role)
        for user_id, role in repository.alert_recipients(
            session, business_id=business_id
        )
    ]


def update_business(
    session: Session,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    changes: Mapping[str, str],
) -> MemberBusiness:
    """Apply `changes` (any of name, province, time_zone) and return the business.

    The caller has already checked the membership and role. Commits the session.
    """
    if changes:
        repository.update_business(session, business_id, changes)
        session.commit()
        log.info("business.updated", business_id=str(business_id), user_id=str(user_id))
    session.expire_all()
    return get_business(session, business_id=business_id, role=role)


def business_time_zones(
    session: Session, business_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """The IANA time zone of each business in `business_ids` that exists, by ID.

    For jobs that act at a business's local time, such as the nightly bank sync.
    """
    return repository.time_zones(session, business_ids)


def all_business_zones(session: Session) -> dict[uuid.UUID, str]:
    """The IANA time zone of every business, by ID.

    For a job that acts on all businesses at their local time, such as the weekly digest.
    """
    return repository.all_time_zones(session)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _address_hash(address: str) -> str:
    return _sha256(address.strip().lower())


@dataclass(frozen=True)
class Invited:
    """A stored invitation, as the owner who made it sees it."""

    id: uuid.UUID
    expires_at: datetime


def invite(
    session: Session,
    *,
    business_id: uuid.UUID,
    inviter_id: uuid.UUID,
    address: str,
    send: Callable[[str, str, str | None, str], None],
) -> Invited:
    """Store an invitation for `address` and email its link with `send`, in one step.

    `send(address, business_name, inviter_first_name, token)` runs before the commit, so
    when it raises nothing is stored. Only hashes of the address and token are kept.
    Raises `AlreadyMemberError` or `AlreadyInvitedError`. The caller has checked that the
    inviter is an owner. Commits the session.
    """
    normalized = address.strip().lower()
    email_hash = _address_hash(normalized)
    for membership in repository.memberships(session, business_id=business_id):
        try:
            found = contact(session, membership.user_id)
        except ContactUnavailableError:
            continue
        if found is not None and _address_hash(found.email) == email_hash:
            raise AlreadyMemberError
    now = datetime.now(UTC)
    existing = repository.lock_pending_invitation(
        session, business_id=business_id, email_hash=email_hash
    )
    if existing is not None:
        if existing.expires_at > now:
            session.rollback()
            raise AlreadyInvitedError
        repository.delete_invitation(session, existing)
    token = secrets.token_urlsafe(32)
    try:
        invitation = repository.insert_invitation(
            session,
            business_id=business_id,
            invited_by_user_id=inviter_id,
            token_hash=_sha256(token),
            email_hash=email_hash,
            created_at=now,
            expires_at=now + timedelta(days=INVITATION_DAYS),
        )
    except IntegrityError:
        session.rollback()
        raise AlreadyInvitedError from None
    audit.record(
        session,
        action="invitation.created",
        business_id=business_id,
        actor_user_id=str(inviter_id),
        target_type="invitation",
        target_id=str(invitation.id),
    )
    try:
        inviter = contact(session, inviter_id)
    except ContactUnavailableError:
        inviter = None
    business = repository.get_business(session, business_id)
    try:
        send(normalized, business.name, inviter.first_name if inviter else None, token)
    except BaseException:
        session.rollback()
        raise
    invited = Invited(id=invitation.id, expires_at=invitation.expires_at)
    session.commit()
    log.info("invitation.created", business_id=str(business_id))
    return invited


InvitationStatus = Literal["pending", "expired", "accepted"]


@dataclass(frozen=True)
class InvitationPreview:
    """What a link's holder sees before accepting."""

    business_name: str
    status: InvitationStatus


def invitation_preview(session: Session, *, token: str) -> InvitationPreview:
    """The business and state behind an invitation link. Raises `InvitationNotFoundError`."""
    invitation = repository.find_invitation_by_token(session, _sha256(token))
    if invitation is None:
        raise InvitationNotFoundError
    status: InvitationStatus = "pending"
    if invitation.accepted_at is not None:
        status = "accepted"
    elif invitation.expires_at <= datetime.now(UTC):
        status = "expired"
    name = repository.get_business(session, invitation.business_id).name
    return InvitationPreview(business_name=name, status=status)


def accept_invitation(
    session: Session, *, token: str, user_id: uuid.UUID
) -> MemberBusiness:
    """Add `user_id` as a bookkeeper of the invitation's business.

    The user's primary Clerk address must be the invited one. Accepting again as the same
    user changes nothing. Raises `InvitationNotFoundError`, `InvitationExpiredError`,
    `WrongAddressError`, `AlreadyMemberError` (the user owns the business) or
    `ContactUnavailableError`. Commits the session.
    """
    invitation = repository.lock_invitation_by_token(session, _sha256(token))
    if invitation is None:
        session.rollback()
        raise InvitationNotFoundError
    business_id = invitation.business_id
    membership = repository.get_membership(
        session, business_id=business_id, user_id=user_id
    )
    if invitation.accepted_at is not None:
        if (
            invitation.accepted_by_user_id == user_id
            and membership is not None
            and membership.role == Role.BOOKKEEPER
        ):
            view = _view(repository.get_business(session, business_id), membership.role)
            session.rollback()
            return view
        session.rollback()
        raise WrongAddressError
    now = datetime.now(UTC)
    if invitation.expires_at <= now:
        session.rollback()
        raise InvitationExpiredError
    try:
        found = contact(session, user_id)
    except ContactUnavailableError:
        session.rollback()
        raise
    if found is None or _address_hash(found.email) != invitation.email_hash:
        session.rollback()
        raise WrongAddressError
    if membership is not None:
        session.rollback()
        raise AlreadyMemberError
    repository.insert_membership(
        session, business_id=business_id, user_id=user_id, role=Role.BOOKKEEPER
    )
    repository.accept_invitation(session, invitation, user_id=user_id, at=now)
    audit.record(
        session,
        action="invitation.accepted",
        business_id=business_id,
        actor_user_id=str(user_id),
        target_type="invitation",
        target_id=str(invitation.id),
    )
    view = _view(repository.get_business(session, business_id), Role.BOOKKEEPER)
    session.commit()
    log.info("invitation.accepted", business_id=str(business_id))
    return view


@dataclass(frozen=True)
class MemberView:
    """A member of a business. `name` and `email` come from Clerk when it answers."""

    user_id: uuid.UUID
    role: str
    receive_alert_emails: bool
    name: str | None
    email: str | None


@dataclass(frozen=True)
class PendingInvitation:
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class Members:
    members: list[MemberView]
    invitations: list[PendingInvitation]


def list_members(session: Session, *, business_id: uuid.UUID) -> Members:
    """The business's members, with names and addresses read from Clerk (never stored),
    and its unexpired, unaccepted invitations."""
    views = []
    for membership in repository.memberships(session, business_id=business_id):
        try:
            found = contact(session, membership.user_id)
        except ContactUnavailableError:
            found = None
        views.append(
            MemberView(
                user_id=membership.user_id,
                role=membership.role,
                receive_alert_emails=membership.receive_alert_emails,
                name=found.first_name if found else None,
                email=found.email if found else None,
            )
        )
    pending = [
        PendingInvitation(id=i.id, created_at=i.created_at, expires_at=i.expires_at)
        for i in repository.pending_invitations(
            session, business_id=business_id, now=datetime.now(UTC)
        )
    ]
    return Members(members=views, invitations=pending)


def remove_member(
    session: Session,
    *,
    business_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Remove a bookkeeper from the business and audit it. Commits the session.

    Raises `MemberNotFoundError`, or `CannotRemoveOwnerError` for an owner.
    """
    membership = repository.get_membership(
        session, business_id=business_id, user_id=user_id
    )
    if membership is None:
        raise MemberNotFoundError
    if membership.role == Role.OWNER:
        raise CannotRemoveOwnerError
    repository.delete_membership(session, business_id=business_id, user_id=user_id)
    audit.record(
        session,
        action="member.removed",
        business_id=business_id,
        actor_user_id=str(actor_user_id),
        target_type="user",
        target_id=str(user_id),
    )
    session.commit()
    log.info("member.removed", business_id=str(business_id))


def set_alert_emails(
    session: Session, *, business_id: uuid.UUID, user_id: uuid.UUID, enabled: bool
) -> MemberView:
    """Turn the bookkeeper's alert emails for this business on or off. Commits."""
    repository.set_alert_emails(
        session, business_id=business_id, user_id=user_id, enabled=enabled
    )
    session.commit()
    return MemberView(
        user_id=user_id,
        role=Role.BOOKKEEPER,
        receive_alert_emails=enabled,
        name=None,
        email=None,
    )
