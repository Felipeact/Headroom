import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import CurrentUser

router = APIRouter(tags=["accounts"])


class Me(BaseModel):
    id: uuid.UUID
    clerk_user_id: str
    created_at: datetime


@router.get("/me", response_model=Me)
def read_me(user: CurrentUser) -> Me:
    return Me(id=user.id, clerk_user_id=user.clerk_user_id, created_at=user.created_at)
