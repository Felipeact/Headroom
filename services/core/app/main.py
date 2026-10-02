from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_engine

app = FastAPI(title="Headroom API")


class LiveStatus(BaseModel):
    status: Literal["ok"]


class ReadyStatus(BaseModel):
    status: Literal["ok", "unavailable"]


@app.get("/healthz/live", response_model=LiveStatus)
def live() -> LiveStatus:
    return LiveStatus(status="ok")


@app.get(
    "/healthz/ready",
    response_model=ReadyStatus,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadyStatus}},
)
def ready(
    response: Response, engine: Annotated[Engine, Depends(get_engine)]
) -> ReadyStatus:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyStatus(status="unavailable")
    return ReadyStatus(status="ok")
