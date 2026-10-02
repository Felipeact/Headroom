from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.accounts.models import User


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
