"""Reading PostHog's numbers (spec 32, door 4): a HogQL query over its Query API.

Only the weekly metrics report reads PostHog; the web app is what writes to it. `PostHogQuery`
is the port: tests replace it with a fake, and every failure is one `PostHogError` carrying
the error type only, never the key, the query's rows or the response body (AD-036 pattern).
"""

from typing import Protocol

import httpx

from app.settings import get_settings

TIMEOUT_SECONDS = 15


class PostHogError(Exception):
    def __init__(self, *, error_type: str) -> None:
        super().__init__(f"posthog query failed: {error_type}")
        self.error_type = error_type


class PostHogQuery(Protocol):
    def count(self, hogql: str) -> int:
        """The first cell of the first row of the query's result. Raises `PostHogError`."""
        ...


class PostHogHttpQuery:
    def __init__(
        self,
        *,
        app_host: str,
        project_id: str,
        personal_api_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = f"{app_host.rstrip('/')}/api/projects/{project_id}/query/"
        self._key = personal_api_key
        self._transport = transport

    def count(self, hogql: str) -> int:
        try:
            with httpx.Client(
                timeout=TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                response = client.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._key}"},
                    json={"query": {"kind": "HogQLQuery", "query": hogql}},
                )
        except httpx.TimeoutException:
            raise PostHogError(error_type="timeout") from None
        except httpx.HTTPError as exc:
            raise PostHogError(error_type=type(exc).__name__) from None
        if response.status_code != 200:
            raise PostHogError(error_type=f"http_{response.status_code}")
        try:
            value = response.json()["results"][0][0]
        except (ValueError, KeyError, IndexError, TypeError):
            raise PostHogError(error_type="malformed_response") from None
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise PostHogError(error_type="malformed_response")
        return int(value)


def get_posthog_query() -> PostHogQuery | None:
    """The client for the configured project, or None when PostHog is not configured."""
    settings = get_settings()
    if not (
        settings.posthog_app_host
        and settings.posthog_project_id
        and settings.posthog_personal_api_key
    ):
        return None
    return PostHogHttpQuery(
        app_host=settings.posthog_app_host,
        project_id=settings.posthog_project_id,
        personal_api_key=settings.posthog_personal_api_key,
    )
