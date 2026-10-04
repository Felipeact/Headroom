import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_session
from app.modules.accounts import service as accounts
from app.modules.accounts.models import User
from app.settings import get_settings

AUTHENTICATION_REQUIRED = "Authentication required."
BUSINESS_NOT_FOUND = "Business not found."
PERMISSION_DENIED = "You don't have permission to do this."
LEEWAY_SECONDS = 5
REQUIRED_CLAIMS = ["exp", "nbf", "iat", "sub"]

Reason = Literal["missing", "expired", "invalid", "unauthorized_party"]

log = structlog.get_logger(__name__)
bearer = HTTPBearer(auto_error=False)


def _rejected(reason: Reason) -> HTTPException:
    # One response for every cause; only the log says which. Never log the token.
    log.info("auth.rejected", reason=reason)
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail=AUTHENTICATION_REQUIRED,
        headers={"WWW-Authenticate": "Bearer"},
    )


def verified_clerk_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    """Verify the Clerk session token in `Authorization: Bearer` and return its `sub`."""
    if credentials is None:
        raise _rejected("missing")
    settings = get_settings()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.clerk_jwt_key,
            algorithms=["RS256"],
            options={"require": REQUIRED_CLAIMS},
            leeway=LEEWAY_SECONDS,
        )
    except jwt.ExpiredSignatureError:
        raise _rejected("expired") from None
    except jwt.InvalidTokenError:
        raise _rejected("invalid") from None
    azp = claims.get("azp")
    parties = settings.clerk_authorized_parties
    if parties and azp is not None and azp not in parties:
        raise _rejected("unauthorized_party")
    sub = claims["sub"]
    if not isinstance(sub, str) or not sub:
        raise _rejected("invalid")
    return sub


def current_user(
    clerk_user_id: Annotated[str, Depends(verified_clerk_user_id)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """The signed-in user, created on their first verified request."""
    return accounts.get_or_create_user(session, clerk_user_id)


CurrentUser = Annotated[User, Depends(current_user)]


@dataclass(frozen=True)
class Member:
    """The signed-in user's membership in the business named by the route's path."""

    business_id: uuid.UUID
    user_id: uuid.UUID
    role: str


def require_member(*roles: accounts.Role) -> Callable[..., Member]:
    """Dependency for every route under `/v1/businesses/{business_id}` (spec 11, AD-031).

    A user who is not a member gets `404`, the same as for a business that does not exist,
    so a stranger learns nothing; a member whose role is not in `roles` gets `403`.
    """
    allowed = frozenset(roles)

    def member(
        business_id: uuid.UUID,
        user: CurrentUser,
        session: Annotated[Session, Depends(get_session)],
    ) -> Member:
        membership = accounts.get_membership(
            session, business_id=business_id, user_id=user.id
        )
        if membership is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=BUSINESS_NOT_FOUND)
        if membership.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=PERMISSION_DENIED)
        return Member(business_id=business_id, user_id=user.id, role=membership.role)

    return member
