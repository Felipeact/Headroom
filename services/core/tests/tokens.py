import time

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from tests.conftest import TEST_PRIVATE_KEY


def claims(sub: str | None = "user_test", **overrides: object) -> dict[str, object]:
    now = int(time.time())
    payload: dict[str, object] = {"iat": now, "nbf": now, "exp": now + 60}
    if sub is not None:
        payload["sub"] = sub
    payload.update(overrides)
    return payload


def token(
    sub: str | None = "user_test",
    *,
    key: RSAPrivateKey = TEST_PRIVATE_KEY,
    algorithm: str = "RS256",
    **overrides: object,
) -> str:
    return jwt.encode(claims(sub, **overrides), key, algorithm=algorithm)


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}
