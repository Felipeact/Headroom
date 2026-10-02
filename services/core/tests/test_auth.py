import base64
import json
import time
import uuid
from collections.abc import Iterator

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.log import configure_logging
from app.main import app
from app.settings import get_settings
from tests.conftest import TEST_PUBLIC_PEM
from tests.tokens import bearer, token

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def parties(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CLERK_AUTHORIZED_PARTIES", "http://localhost:3000,https://app.test"
    )
    get_settings.cache_clear()


def new_sub() -> str:
    return f"user_test_{uuid.uuid4().hex[:12]}"


def assert_rejected(response: httpx.Response) -> None:
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"
    body = response.json()
    assert body["status"] == 401
    assert body["title"] == "Unauthorized"
    assert body["detail"] == "Authentication required."
    assert body["instance"] == "/v1/me"


def other_key_token() -> str:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return token(new_sub(), key=other)


def altered_payload_token() -> str:
    header, _, signature = token(new_sub()).split(".")
    now = int(time.time())
    forged = {"sub": "user_someone_else", "iat": now, "nbf": now, "exp": now + 60}
    payload = base64.urlsafe_b64encode(json.dumps(forged).encode()).rstrip(b"=")
    return f"{header}.{payload.decode()}.{signature}"


def none_alg_token() -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": new_sub(), "iat": now, "nbf": now, "exp": now + 60},
        None,
        algorithm="none",
    )


def hs256_with_public_pem_token() -> str:
    # The classic algorithm-confusion attack: the public key used as an HMAC secret.
    # PyJWT refuses to sign with a PEM as an HMAC key, so build the token by hand.
    import hashlib
    import hmac

    now = int(time.time())

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(
        json.dumps({"sub": new_sub(), "iat": now, "nbf": now, "exp": now + 60}).encode()
    )
    signing_input = f"{header}.{body}".encode()
    mac = hmac.new(TEST_PUBLIC_PEM.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{body}.{b64(mac)}"


def test_valid_token_returns_me() -> None:
    response = client.get("/v1/me", headers=bearer(token("user_test_c1")))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "clerk_user_id", "created_at"}
    assert body["clerk_user_id"] == "user_test_c1"
    uuid.UUID(body["id"])


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic dXNlcjpwdw=="},
        {"Authorization": "Bearer"},
        {"Authorization": "__TOKEN__"},
    ],
    ids=["no_header", "basic", "bearer_empty", "no_prefix"],
)
def test_missing_or_malformed_header(headers: dict[str, str]) -> None:
    if headers.get("Authorization") == "__TOKEN__":
        headers = {"Authorization": token(new_sub())}

    assert_rejected(client.get("/v1/me", headers=headers))


def test_expired_beyond_leeway_rejected() -> None:
    now = int(time.time())
    expired = token(new_sub(), iat=now - 70, nbf=now - 70, exp=now - 10)

    assert_rejected(client.get("/v1/me", headers=bearer(expired)))


def test_expired_within_leeway_accepted() -> None:
    now = int(time.time())
    recent = token(new_sub(), iat=now - 63, nbf=now - 63, exp=now - 3)

    assert client.get("/v1/me", headers=bearer(recent)).status_code == 200


@pytest.mark.parametrize("make", [other_key_token, altered_payload_token])
def test_bad_signature(make: object) -> None:
    assert callable(make)
    assert_rejected(client.get("/v1/me", headers=bearer(make())))


def rs512_token() -> str:
    return token(new_sub(), algorithm="RS512")


@pytest.mark.parametrize(
    "make", [none_alg_token, hs256_with_public_pem_token, rs512_token]
)
def test_wrong_algorithm(make: object) -> None:
    assert callable(make)
    assert_rejected(client.get("/v1/me", headers=bearer(make())))


def test_nbf_or_sub_future_nbf_rejected() -> None:
    now = int(time.time())
    future = token(new_sub(), nbf=now + 10)

    assert_rejected(client.get("/v1/me", headers=bearer(future)))


def test_nbf_or_sub_missing_sub_rejected() -> None:
    assert_rejected(client.get("/v1/me", headers=bearer(token(None))))


@pytest.mark.usefixtures("parties")
def test_authorized_parties_foreign_azp_rejected() -> None:
    foreign = token(new_sub(), azp="https://evil.test")

    assert_rejected(client.get("/v1/me", headers=bearer(foreign)))


@pytest.mark.usefixtures("parties")
def test_authorized_parties_listed_azp_accepted() -> None:
    listed = token(new_sub(), azp="https://app.test")

    assert client.get("/v1/me", headers=bearer(listed)).status_code == 200


@pytest.mark.usefixtures("parties")
def test_authorized_parties_absent_azp_accepted() -> None:
    assert client.get("/v1/me", headers=bearer(token(new_sub()))).status_code == 200


def test_authorized_parties_empty_list_skips_check() -> None:
    assert get_settings().clerk_authorized_parties == []
    foreign = token(new_sub(), azp="https://evil.test")

    assert client.get("/v1/me", headers=bearer(foreign)).status_code == 200


def test_every_v1_route_requires_token() -> None:
    # The OpenAPI paths list every exposed route, including those of included routers
    # (which FastAPI keeps out of `app.routes`).
    v1 = {
        path: methods
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/v1")
    }
    assert "/v1/me" in v1

    for path, methods in v1.items():
        for method in methods:
            response = client.request(method.upper(), path)
            assert response.status_code == 401, (method, path)

    assert client.get("/healthz/live").status_code == 200


def expired_token() -> str:
    now = int(time.time())
    return token(new_sub(), iat=now - 70, nbf=now - 70, exp=now - 10)


def foreign_azp_token() -> str:
    return token(new_sub(), azp="https://evil.test")


REJECTIONS = [
    ("no_header", None, "missing"),
    ("basic", lambda: "Basic dXNlcjpwdw==", "missing"),
    ("bearer_empty", lambda: "Bearer", "missing"),
    ("no_prefix", lambda: token(new_sub()), "missing"),
    ("expired", lambda: "Bearer " + expired_token(), "expired"),
    ("other_key", lambda: "Bearer " + other_key_token(), "invalid"),
    ("altered", lambda: "Bearer " + altered_payload_token(), "invalid"),
    ("none_alg", lambda: "Bearer " + none_alg_token(), "invalid"),
    ("hs256", lambda: "Bearer " + hs256_with_public_pem_token(), "invalid"),
    ("rs512", lambda: "Bearer " + rs512_token(), "invalid"),
    (
        "future_nbf",
        lambda: "Bearer " + token(new_sub(), nbf=int(time.time()) + 10),
        "invalid",
    ),
    ("no_sub", lambda: "Bearer " + token(None), "invalid"),
    ("foreign_azp", lambda: "Bearer " + foreign_azp_token(), "unauthorized_party"),
]


@pytest.mark.usefixtures("parties")
@pytest.mark.parametrize(
    ("case", "make_header", "reason"), REJECTIONS, ids=[r[0] for r in REJECTIONS]
)
def test_rejected_logs_reason(
    case: str,
    make_header: object,
    reason: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    header = make_header() if callable(make_header) else None
    headers = {"Authorization": header} if isinstance(header, str) else {}

    response = client.get("/v1/me", headers=headers)
    out = capsys.readouterr().out

    assert response.status_code == 401
    events = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    rejected = [e for e in events if e.get("event") == "auth.rejected"]
    assert len(rejected) == 1, out
    assert rejected[0]["reason"] == reason
    if isinstance(header, str):
        assert header not in out
        secret = header.removeprefix("Bearer ").removeprefix("Basic ")
        assert secret not in out


def test_accepted_logs_no_token(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    value = token(new_sub())

    response = client.get("/v1/me", headers=bearer(value))
    out = capsys.readouterr()

    assert response.status_code == 200
    assert value not in out.out
    assert value not in out.err
