"""In-process rate limits (spec 33, door 2).

Fixed one-minute windows held in memory: they reset on every deploy and do not span
replicas, so running `api` on more than one instance means reopening this door. The three
limits are constants because nobody tunes them before the pilot.
"""

import math
import time
from collections.abc import Mapping
from typing import Literal

import structlog
from fastapi import HTTPException, status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.problems import problem_response

WINDOW_SECONDS = 60
USER_LIMIT = 300  # signed-in requests per user per window
REJECTED_AUTH_LIMIT = 60  # requests failing authentication per client IP per window
PUBLIC_LIMIT = 30  # requests to a public route per client IP per window
PUBLIC_PREFIXES = ("/v1/webhooks/", "/v1/unsubscribe/")
RATE_LIMITED = "Too many requests."
PRUNE_ABOVE = 10_000

KeyKind = Literal["user", "ip"]

log = structlog.get_logger(__name__)
now = time.monotonic
_windows: dict[tuple[str, str], tuple[float, int]] = {}


def reset() -> None:
    _windows.clear()


def _prune(at: float) -> None:
    for key, (started, _) in list(_windows.items()):
        if at - started >= WINDOW_SECONDS:
            del _windows[key]


def _retry_after(started: float, at: float) -> int:
    return max(1, min(WINDOW_SECONDS, math.ceil(started + WINDOW_SECONDS - at)))


def _blocked(scope: str, key: str, limit: int) -> int | None:
    """Seconds to wait when `key` has used up `limit` in its window, else None."""
    at = now()
    started, count = _windows.get((scope, key), (at, 0))
    if at - started >= WINDOW_SECONDS:
        started, count = at, 0
    return _retry_after(started, at) if count >= limit else None


def _count(scope: str, key: str) -> None:
    at = now()
    if len(_windows) > PRUNE_ABOVE:
        _prune(at)
    started, count = _windows.get((scope, key), (at, 0))
    if at - started >= WINDOW_SECONDS:
        started, count = at, 0
    _windows[(scope, key)] = (started, count + 1)


def client_ip(headers: Mapping[str, str], fallback: str) -> str:
    """The right-most `X-Forwarded-For` entry, which Railway's proxy appends."""
    forwarded = headers.get("x-forwarded-for", "")
    last = forwarded.rsplit(",", 1)[-1].strip()
    return last or fallback


def rejected(route: str, key_kind: KeyKind, retry_after: int) -> HTTPException:
    # The route template and the kind of key only: never the token, user or address.
    log.warning("ratelimit.rejected", route=route, key_kind=key_kind)
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail=RATE_LIMITED,
        headers={"Retry-After": str(retry_after)},
    )


def check_ip_not_blocked(ip: str, route: str) -> None:
    """Refuse a client IP that has failed authentication too often (door 5)."""
    wait = _blocked("rejected", ip, REJECTED_AUTH_LIMIT)
    if wait is not None:
        raise rejected(route, "ip", wait)


def count_rejected_authentication(ip: str) -> None:
    _count("rejected", ip)


def hit_user(user: str, route: str) -> None:
    """Count one signed-in request; refuse the 301st in a window."""
    wait = _blocked("user", user, USER_LIMIT)
    if wait is not None:
        raise rejected(route, "user", wait)
    _count("user", user)


def _public_template(path: str) -> str:
    if path.startswith("/v1/unsubscribe/"):
        return "/v1/unsubscribe/{token}"
    return path


class PublicRouteLimit:
    """ASGI middleware: the per-IP limit on routes that need no login."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return
        headers = {
            name.decode("latin-1").lower(): value.decode("latin-1")
            for name, value in scope["headers"]
        }
        client = scope.get("client")
        ip = client_ip(headers, client[0] if client else "unknown")
        wait = _blocked("public", ip, PUBLIC_LIMIT)
        if wait is not None:
            error = rejected(_public_template(scope["path"]), "ip", wait)
            response = problem_response(
                scope["path"], error.status_code, RATE_LIMITED, error.headers
            )
            await response(scope, receive, send)
            return
        _count("public", ip)
        await self.app(scope, receive, send)
