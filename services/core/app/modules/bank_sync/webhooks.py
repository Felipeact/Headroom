"""Plaid webhook verification (spec 14 door 7, AD-049).

Follows https://plaid.com/docs/api/webhooks/webhook-verification/: the `Plaid-Verification`
header is an ES256 JWT signed with the key named by its `kid`; its `iat` is at most five
minutes old, and its `request_body_sha256` is the SHA-256 of the raw body.
"""

import hashlib
import hmac
import threading
import time
from typing import Any

import jwt

from app.modules.bank_sync.plaid import PlaidClient

ALGORITHM = "ES256"
MAX_AGE_SECONDS = 300

_keys: dict[str, dict[str, Any]] = {}
_keys_lock = threading.Lock()


class InvalidSignatureError(Exception):
    """The webhook is not signed by Plaid, is too old, or its body was changed."""


def clear_key_cache() -> None:
    with _keys_lock:
        _keys.clear()


def _key(plaid: PlaidClient, key_id: str) -> dict[str, Any]:
    with _keys_lock:
        key = _keys.get(key_id)
    if key is None:
        # Raises PlaidError when Plaid fails; the caller answers 502 so Plaid retries.
        key = plaid.get_webhook_verification_key(key_id)
        with _keys_lock:
            _keys[key_id] = key
    return key


def verify(plaid: PlaidClient, header: str | None, body: bytes) -> None:
    """Return when `header` proves Plaid sent `body`; raise `InvalidSignatureError` if not.

    Raises `PlaidError` when the verification key cannot be fetched.
    """
    if not header:
        raise InvalidSignatureError
    try:
        unverified = jwt.get_unverified_header(header)
    except jwt.PyJWTError:
        raise InvalidSignatureError from None
    key_id = unverified.get("kid")
    if unverified.get("alg") != ALGORITHM or not isinstance(key_id, str):
        raise InvalidSignatureError

    key = _key(plaid, key_id)
    expired_at = key.get("expired_at")
    if expired_at is not None and expired_at <= time.time():
        raise InvalidSignatureError
    try:
        public_key = jwt.PyJWK(
            {k: v for k, v in key.items() if k in ("kty", "crv", "x", "y", "kid")},
            algorithm=ALGORITHM,
        ).key
        claims = jwt.decode(
            header,
            public_key,
            algorithms=[ALGORITHM],
            options={"require": ["iat"]},
        )
    except (jwt.PyJWTError, ValueError, TypeError):
        raise InvalidSignatureError from None

    issued_at = claims["iat"]
    if not isinstance(issued_at, int) or time.time() - issued_at > MAX_AGE_SECONDS:
        raise InvalidSignatureError
    expected = claims.get("request_body_sha256")
    actual = hashlib.sha256(body).hexdigest()
    if not isinstance(expected, str) or not hmac.compare_digest(expected, actual):
        raise InvalidSignatureError
