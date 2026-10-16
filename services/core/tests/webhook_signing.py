"""Plaid-style webhook signatures for tests (spec 14).

Plaid signs each webhook with an ES256 JWT in `Plaid-Verification` and serves the public
key at /webhook_verification_key/get. Tests sign with a key made for this session, and the
fake Plaid client serves `jwk()` as that key, so nothing calls Plaid.
"""

import hashlib
import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())
KID = "test-kid-1"


def jwk(*, kid: str = KID, expired_at: int | None = None) -> dict[str, Any]:
    """`KEY`'s public half in the shape /webhook_verification_key/get returns."""
    public = ECAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
    return {
        **public,
        "alg": "ES256",
        "kid": kid,
        "use": "sig",
        "created_at": int(time.time()) - 3600,
        "expired_at": expired_at,
    }


def body(item_id: str, *, code: str = "SYNC_UPDATES_AVAILABLE", **extra: Any) -> bytes:
    """A webhook body as Plaid formats it: JSON with a tab spacing of 2."""
    return json.dumps(
        {
            "webhook_type": "TRANSACTIONS",
            "webhook_code": code,
            "item_id": item_id,
            "initial_update_complete": True,
            "historical_update_complete": True,
            "environment": "sandbox",
            **extra,
        },
        indent=2,
    ).encode()


def sign(
    content: bytes,
    *,
    key: Any = KEY,
    kid: str = KID,
    iat: int | None = None,
    body_sha256: str | None = None,
    algorithm: str | None = "ES256",
) -> str:
    claims = {
        "iat": int(time.time()) if iat is None else iat,
        "request_body_sha256": body_sha256 or hashlib.sha256(content).hexdigest(),
    }
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid})


def headers(content: bytes, **kwargs: Any) -> dict[str, str]:
    return {
        "Plaid-Verification": sign(content, **kwargs),
        "Content-Type": "application/json",
    }
