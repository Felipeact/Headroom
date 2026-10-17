import logging
import re
import sys
from collections.abc import Mapping

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

REDACTED = "[REDACTED]"

SECRET_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "dsn",
    "account_number",
    "private_key",
    # Raw request bodies (Sentry frame locals such as `body_bytes`): spec 12 door 8.
    "body",
    # Flinks (spec 17a): the loginId is a permanent token, and a raw account carries the
    # full `AccountNumber` and the holder's identity, as frame locals or nested keys.
    "login_id",
    "loginid",
    "accountnumber",
    "holder",
    "username",
    # Flinks' header names (`x-api-key`, `flinks-auth-key`) in a request's frame locals.
    "api-key",
    "auth-key",
)

TOKEN_PATTERN = re.compile(
    r"(?:access|public)-(?:sandbox|development|production)-"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|Bearer\s+[^\s\"',;]+"
    # An invitation link's token is the path segment after `/v1/invitations/` (spec 31).
    r"|(?<=/v1/invitations/)[A-Za-z0-9_-]{20,}"
    # A Flinks loginId is a permanent token, and DeleteCard takes it in the path, which
    # httpx logs on every request (spec 17a).
    r"|(?<=/DeleteCard/)[A-Za-z0-9-]+",
    re.IGNORECASE,
)

# uvicorn installs its own handlers on these; they must propagate to the root instead.
STDLIB_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def _is_secret_key(key: object) -> bool:
    return isinstance(key, str) and any(
        fragment in key.lower() for fragment in SECRET_KEY_FRAGMENTS
    )


def _redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        return redact(value)
    if isinstance(value, list | tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return TOKEN_PATTERN.sub(REDACTED, value)
    return value


def redact(data: Mapping[str, object]) -> dict[str, object]:
    """Return a copy with secret-named keys and token values replaced, at any depth."""
    return {
        key: REDACTED if _is_secret_key(key) else _redact_value(value)
        for key, value in data.items()
    }


def _redact_processor(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    return redact(event_dict)


def configure_logging() -> None:
    """Send structlog and stdlib logging to stdout as redacted JSON lines."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in STDLIB_LOGGERS:
        stdlib_logger = logging.getLogger(name)
        stdlib_logger.handlers = []
        stdlib_logger.propagate = True
