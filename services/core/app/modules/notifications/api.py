from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_session
from app.modules.notifications import service
from app.problems import ProblemDetails, ValidationProblemDetails

UNSUBSCRIBE_NOT_FOUND = "Unsubscribe link not found."
# token_urlsafe(32) is 43 characters; anything far longer is no token of ours.
TOKEN_MAX_LENGTH = 128

router = APIRouter(tags=["notifications"])
# Public (door 4): mounted outside the `/v1` auth router; the token is the credential.
unsubscribe_router = APIRouter(tags=["notifications"])

SessionDep = Annotated[Session, Depends(get_session)]


class EmailPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alerts: StrictBool
    weekly_digest: StrictBool


class Unsubscribed(BaseModel):
    status: Literal["unsubscribed"]


def _out(prefs: service.Preferences) -> EmailPreferences:
    return EmailPreferences(alerts=prefs.alerts, weekly_digest=prefs.weekly_digest)


@router.get("/me/email-preferences", response_model=EmailPreferences)
def read_email_preferences(user: CurrentUser, session: SessionDep) -> EmailPreferences:
    return _out(service.get_preferences(session, user.id))


@router.put(
    "/me/email-preferences",
    response_model=EmailPreferences,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ValidationProblemDetails}
    },
)
def update_email_preferences(
    body: EmailPreferences, user: CurrentUser, session: SessionDep
) -> EmailPreferences:
    return _out(
        service.set_preferences(
            session, user.id, alerts=body.alerts, weekly_digest=body.weekly_digest
        )
    )


@unsubscribe_router.post(
    "/{token}",
    response_model=Unsubscribed,
    responses={status.HTTP_404_NOT_FOUND: {"model": ProblemDetails}},
)
def unsubscribe(token: str, session: SessionDep) -> Unsubscribed:
    """One click from an email, or a mail client's RFC 8058 POST; any body is ignored."""
    if len(token) > TOKEN_MAX_LENGTH or not service.unsubscribe(session, token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=UNSUBSCRIBE_NOT_FOUND)
    return Unsubscribed(status="unsubscribed")
