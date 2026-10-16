from collections.abc import Mapping
from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from app.log import REDACTED, TOKEN_PATTERN

PROBLEM_JSON = "application/problem+json"
UNEXPECTED_ERROR = "An unexpected error occurred."
VALIDATION_FAILED = "The request did not pass validation."

log = structlog.get_logger(__name__)


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str


class FieldError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationProblemDetails(ProblemDetails):
    errors: list[FieldError]


def _phrase(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def _instance(request: Request) -> str:
    return TOKEN_PATTERN.sub(REDACTED, request.url.path)


def _problem(
    problem: ProblemDetails,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        problem.model_dump(),
        status_code=problem.status,
        headers=headers,
        media_type=PROBLEM_JSON,
    )


def problem_response(
    path: str,
    status: int,
    detail: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """A problem details response for code that runs before routing (spec 33)."""
    problem = ProblemDetails(
        title=_phrase(status),
        status=status,
        detail=detail,
        instance=TOKEN_PATTERN.sub(REDACTED, path),
    )
    return _problem(problem, headers)


def _http_exception(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, HTTPException)
    if exc.status_code in {HTTPStatus.NO_CONTENT, HTTPStatus.NOT_MODIFIED}:
        return Response(status_code=exc.status_code, headers=exc.headers)
    detail = exc.detail if isinstance(exc.detail, str) else _phrase(exc.status_code)
    problem = ProblemDetails(
        title=_phrase(exc.status_code),
        status=exc.status_code,
        detail=detail,
        instance=_instance(request),
    )
    return _problem(problem, exc.headers)


def _validation_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    status = HTTPStatus.UNPROCESSABLE_ENTITY
    # Only loc, msg and type: Pydantic's input and ctx can echo submitted secrets.
    errors = [
        FieldError(loc=list(error["loc"]), msg=error["msg"], type=error["type"])
        for error in exc.errors()
    ]
    problem = ValidationProblemDetails(
        title=status.phrase,
        status=status,
        detail=VALIDATION_FAILED,
        instance=_instance(request),
        errors=errors,
    )
    return _problem(problem)


def _unhandled_exception(request: Request, exc: Exception) -> Response:
    log.error(
        "request.unhandled_exception",
        method=request.method,
        path=request.url.path,
        exc_info=exc,
    )
    status = HTTPStatus.INTERNAL_SERVER_ERROR
    problem = ProblemDetails(
        title=status.phrase,
        status=status,
        detail=UNEXPECTED_ERROR,
        instance=_instance(request),
    )
    return _problem(problem)


def install_problem_handlers(app: FastAPI) -> None:
    """Make every error the app raises an RFC 9457 problem details response."""
    app.add_exception_handler(HTTPException, _http_exception)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_exception)
