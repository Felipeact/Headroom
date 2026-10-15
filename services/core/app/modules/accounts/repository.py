import uuid
from collections.abc import Collection, Mapping
from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.accounts.models import Business, Invitation, Membership, User


def get_or_insert_user(session: Session, clerk_user_id: str) -> User:
    # ON CONFLICT DO NOTHING: two first requests at once both end on the same row.
    session.execute(
        insert(User)
        .values(clerk_user_id=clerk_user_id)
        .on_conflict_do_nothing(index_elements=[User.clerk_user_id])
    )
    return session.scalars(
        select(User).where(User.clerk_user_id == clerk_user_id)
    ).one()


def clerk_user_id(session: Session, user_id: uuid.UUID) -> str | None:
    return session.scalar(select(User.clerk_user_id).where(User.id == user_id))


def owns_a_business(session: Session, user_id: uuid.UUID) -> bool:
    return (
        session.scalar(
            select(Membership.business_id).where(
                Membership.user_id == user_id, Membership.role == "owner"
            )
        )
        is not None
    )


def insert_business(
    session: Session, *, name: str, province: str, time_zone: str
) -> Business:
    business = Business(name=name, province=province, time_zone=time_zone)
    session.add(business)
    session.flush()
    session.refresh(business)
    return business


def insert_membership(
    session: Session, *, business_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> None:
    session.add(Membership(business_id=business_id, user_id=user_id, role=role))
    session.flush()


def get_membership(
    session: Session, *, business_id: uuid.UUID, user_id: uuid.UUID
) -> Membership | None:
    return session.get(Membership, (business_id, user_id))


def member_ids(
    session: Session, *, business_id: uuid.UUID, roles: Collection[str]
) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(Membership.user_id)
            .where(Membership.business_id == business_id, Membership.role.in_(roles))
            .order_by(Membership.created_at, Membership.user_id)
        )
    )


def businesses_for_user(
    session: Session, user_id: uuid.UUID
) -> list[tuple[Business, str]]:
    rows = session.execute(
        select(Business, Membership.role)
        .join(Membership, Membership.business_id == Business.id)
        .where(Membership.user_id == user_id)
        .order_by(Membership.created_at, Business.id)
    ).all()
    return [(business, role) for business, role in rows]


def get_business(session: Session, business_id: uuid.UUID) -> Business:
    return session.scalars(select(Business).where(Business.id == business_id)).one()


def update_business(
    session: Session, business_id: uuid.UUID, changes: Mapping[str, str]
) -> None:
    session.execute(
        update(Business)
        .where(Business.id == business_id)
        .values(**changes, updated_at=func.now())
    )


def all_time_zones(session: Session) -> dict[uuid.UUID, str]:
    rows = session.execute(select(Business.id, Business.time_zone))
    return {business_id: time_zone for business_id, time_zone in rows}


def time_zones(
    session: Session, business_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, str]:
    rows = session.execute(
        select(Business.id, Business.time_zone).where(Business.id.in_(business_ids))
    )
    return {business_id: time_zone for business_id, time_zone in rows}


def alert_recipients(
    session: Session, *, business_id: uuid.UUID
) -> list[tuple[uuid.UUID, str]]:
    """(user, role) of every owner and of each bookkeeper who opted in, oldest first."""
    rows = session.execute(
        select(Membership.user_id, Membership.role)
        .where(
            Membership.business_id == business_id,
            or_(
                Membership.role == "owner",
                and_(Membership.role == "bookkeeper", Membership.receive_alert_emails),
            ),
        )
        .order_by(Membership.created_at, Membership.user_id)
    ).all()
    return [(user_id, role) for user_id, role in rows]


def memberships(session: Session, *, business_id: uuid.UUID) -> list[Membership]:
    return list(
        session.scalars(
            select(Membership)
            .where(Membership.business_id == business_id)
            .order_by(Membership.created_at, Membership.user_id)
        )
    )


def delete_membership(
    session: Session, *, business_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    session.execute(
        delete(Membership).where(
            Membership.business_id == business_id, Membership.user_id == user_id
        )
    )


def set_alert_emails(
    session: Session, *, business_id: uuid.UUID, user_id: uuid.UUID, enabled: bool
) -> None:
    session.execute(
        update(Membership)
        .where(Membership.business_id == business_id, Membership.user_id == user_id)
        .values(receive_alert_emails=enabled)
    )


def insert_invitation(
    session: Session,
    *,
    business_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
    token_hash: str,
    email_hash: str,
    created_at: datetime,
    expires_at: datetime,
) -> Invitation:
    invitation = Invitation(
        business_id=business_id,
        invited_by_user_id=invited_by_user_id,
        token_hash=token_hash,
        email_hash=email_hash,
        created_at=created_at,
        expires_at=expires_at,
    )
    session.add(invitation)
    session.flush()
    return invitation


def lock_pending_invitation(
    session: Session, *, business_id: uuid.UUID, email_hash: str
) -> Invitation | None:
    """The business's unaccepted invitation for this address, locked, expired or not."""
    return session.scalars(
        select(Invitation)
        .where(
            Invitation.business_id == business_id,
            Invitation.email_hash == email_hash,
            Invitation.accepted_at.is_(None),
        )
        .with_for_update()
    ).one_or_none()


def delete_invitation(session: Session, invitation: Invitation) -> None:
    session.delete(invitation)
    session.flush()


def lock_invitation_by_token(session: Session, token_hash: str) -> Invitation | None:
    return session.scalars(
        select(Invitation).where(Invitation.token_hash == token_hash).with_for_update()
    ).one_or_none()


def pending_invitations(
    session: Session, *, business_id: uuid.UUID, now: datetime
) -> list[Invitation]:
    return list(
        session.scalars(
            select(Invitation)
            .where(
                Invitation.business_id == business_id,
                Invitation.accepted_at.is_(None),
                Invitation.expires_at > now,
            )
            .order_by(Invitation.created_at, Invitation.id)
        )
    )


def accept_invitation(
    session: Session, invitation: Invitation, *, user_id: uuid.UUID, at: datetime
) -> None:
    invitation.accepted_at = at
    invitation.accepted_by_user_id = user_id
    session.flush()


def find_invitation_by_token(session: Session, token_hash: str) -> Invitation | None:
    return session.scalars(
        select(Invitation).where(Invitation.token_hash == token_hash)
    ).one_or_none()
