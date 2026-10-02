from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

import structlog
from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_engine
from app.log import configure_logging
from app.monitoring import init_sentry
from app.problems import install_problem_handlers
from app.settings import get_settings

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Here, not at import: uvicorn applies its own log config after importing the app.
    configure_logging()
    try:
        settings = get_settings()
    except ValidationError as exc:
        # Field names only: the error text can carry the rejected values.
        fields = [".".join(map(str, error["loc"])) for error in exc.errors()]
        log.warning("monitoring.disabled", reason="invalid settings", fields=fields)
    else:
        if init_sentry(settings):
            # Rebuild the stack so Sentry also patches the ExceptionMiddleware that
            # handles a raised HTTPException with a 5xx status.
            app.middleware_stack = None
    yield


app = FastAPI(title="Headroom API", lifespan=lifespan)
install_problem_handlers(app)


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
