"""Security headers and the browser-origin rule for the API (spec 33, door 1).

The browser never calls the API (AGENTS.md, AD-017): the web server does, and a server's
request carries no `Origin`. So a request that has one is refused, and no CORS header is
ever sent.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.problems import problem_response

BROWSER_REFUSED = "Browser requests are not allowed."
HSTS = "max-age=31536000; includeSubDomains"
PROBE_PREFIX = "/healthz"


class SecurityMiddleware:
    """Outermost middleware: adds the headers to every answer, even a refusal."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Strict-Transport-Security"] = HSTS
                headers["X-Content-Type-Options"] = "nosniff"
                if path.startswith("/v1"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        has_origin = any(name == b"origin" for name, _ in scope["headers"])
        if has_origin and not path.startswith(PROBE_PREFIX):
            response = problem_response(path, 403, BROWSER_REFUSED)
            await response(scope, receive, send_with_headers)
            return
        await self.app(scope, receive, send_with_headers)
