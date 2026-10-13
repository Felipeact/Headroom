import uuid
from collections.abc import Collection, Mapping

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.accounts.models import Business, Membership, User


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


def time_zones(
    session: Session, business_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, str]:
    rows = session.execute(
        select(Business.id, Business.time_zone).where(Business.id.in_(business_ids))
    )
    return {business_id: time_zone for business_id, time_zone in rows}
