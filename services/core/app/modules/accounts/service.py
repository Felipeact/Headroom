import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import structlog
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.accounts import repository
from app.modules.accounts.models import Business, Membership, User

OWNER_INDEX = "uq_memberships_owner_user_id"

log = structlog.get_logger(__name__)


class Role(StrEnum):
    OWNER = "owner"


class AlreadyOwnsBusinessError(Exception):
    """The user already owns a business; v1 allows one per owner."""


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
