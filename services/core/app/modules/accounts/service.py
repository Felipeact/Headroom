from sqlalchemy.orm import Session

from app.modules.accounts import repository
from app.modules.accounts.models import User


def get_or_create_user(session: Session, clerk_user_id: str) -> User:
    """Return the user for a verified Clerk user ID, creating the row on first sight.

    Safe to call concurrently: the unique `clerk_user_id` decides which insert wins, and
    every caller gets the same row. Commits the session.
    """
    user = repository.get_or_insert_user(session, clerk_user_id)
    session.commit()
    return user
