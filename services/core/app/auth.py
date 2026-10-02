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
