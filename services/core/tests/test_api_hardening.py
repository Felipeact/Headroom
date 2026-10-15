"""Spec 33 S1: the API refuses browsers and floods (C1-C11)."""

import json
import subprocess
import sys
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.log import configure_logging
from app.main import app
from tests.bookkeeper_support import sql
from tests.conftest import CORE
from tests.test_businesses import HARBOR
from tests.tokens import bearer, token

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app, raise_server_exceptions=False)
PROBLEM_JSON = "application/problem+json"
EVIL = {"Origin": "https://evil.example"}
UNSUBSCRIBE = "/v1/unsubscribe/not-a-real-token"
WEBHOOK = "/v1/webhooks/plaid"


class Clock:
    def __init__(self) -> None:
        self.value = 1_000_000.0

    def __call__(self) -> float:
        return self.value


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[Clock]:
    fixed = Clock()
    monkeypatch.setattr(ratelimit, "now", fixed)
    ratelimit.reset()
    yield fixed
    ratelimit.reset()


def new_headers(ip: str | None = None) -> dict[str, str]:
    headers = bearer(token(f"user_test_{uuid.uuid4().hex[:12]}"))
    if ip is not None:
        headers["X-Forwarded-For"] = ip
    return headers


def events_of(out: str) -> list[dict[str, object]]:
    return [json.loads(x) if x.startswith("{") else {} for x in out.splitlines()]


def business_count() -> int:
    return int(sql("SELECT count(*) FROM businesses")[0][0])


def test_origin_refused() -> None:
    """C1."""
    headers = new_headers()
    before = business_count()
    for method, path, extra in (
        ("GET", "/v1/me", {}),
        ("POST", "/v1/businesses", {"json": HARBOR}),
        ("POST", WEBHOOK, {"content": b"{}"}),
        ("POST", UNSUBSCRIBE, {}),
    ):
        response = client.request(method, path, headers={**headers, **EVIL}, **extra)
        assert response.status_code == 403, (method, path)
        assert response.headers["content-type"] == PROBLEM_JSON
        assert response.json()["detail"] == "Browser requests are not allowed."
    assert business_count() == before

    created = client.post("/v1/businesses", json=HARBOR, headers=headers)
    assert created.status_code == 201
    assert client.post(UNSUBSCRIBE).status_code != 403
    assert client.post(WEBHOOK, content=b"{}").status_code != 403
    assert business_count() == before + 1


def test_probes_ignore_origin() -> None:
    """C2."""
    assert client.get("/healthz/live", headers=EVIL).status_code == 200
    assert client.get("/healthz/ready", headers=EVIL).status_code == 200


def test_no_cors_headers(clock: Clock) -> None:
    """C3."""
    headers = new_headers()
    responses = [
        client.options("/v1/me", headers=EVIL),
        client.options("/v1/me"),
        client.get("/v1/me", headers=headers),
        client.get("/v1/me", headers={**headers, **EVIL}),
    ]
    flooded = new_headers()
    for _ in range(301):
        last = client.get("/v1/me", headers=flooded)
    assert last.status_code == 429
    responses.append(last)
    for response in responses:
        names = [name.lower() for name in response.headers]
        assert not [n for n in names if n.startswith("access-control-")], response


def test_user_limit() -> None:
    """C4."""
    headers = new_headers()
    for _ in range(300):
        assert client.get("/v1/me", headers=headers).status_code == 200
    blocked = client.get("/v1/me", headers=headers)

    assert blocked.status_code == 429
    assert blocked.headers["content-type"] == PROBLEM_JSON
    assert 1 <= int(blocked.headers["retry-after"]) <= 60
    assert client.get("/v1/me", headers=new_headers()).status_code == 200


def test_ip_limit_counts_only_rejected() -> None:
    """C5."""
    shared = "203.0.113.7"
    users = [new_headers(shared), new_headers(shared)]
    for i in range(100):
        response = client.get("/v1/me", headers=users[i % 2])
        assert response.status_code == 200, i

    attacker = {"X-Forwarded-For": "198.51.100.9"}
    for i in range(60):
        assert client.get("/v1/me", headers=attacker).status_code == 401, i
    blocked = client.get("/v1/me", headers=attacker)
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers


def test_public_routes_ip_limit() -> None:
    """C6."""
    ip = {"X-Forwarded-For": "192.0.2.10"}
    for i in range(30):
        assert client.post(UNSUBSCRIBE, headers=ip).status_code == 404, i
    blocked = client.post(UNSUBSCRIBE, headers=ip)
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers

    plaid = {"X-Forwarded-For": "192.0.2.20"}
    for i in range(30):
        assert client.post(WEBHOOK, content=b"{}", headers=plaid).status_code == 401, i
    assert client.post(WEBHOOK, content=b"{}", headers=plaid).status_code == 429

    # Only the right-most entry names the client; the left ones are the sender's to forge.
    spoof = {"X-Forwarded-For": "1.1.1.1, 192.0.2.10"}
    assert client.post(UNSUBSCRIBE, headers=spoof).status_code == 429
    other = {"X-Forwarded-For": "1.1.1.1, 192.0.2.11"}
    assert client.post(UNSUBSCRIBE, headers=other).status_code == 404


def test_window_resets(clock: Clock) -> None:
    """C7."""
    ip = {"X-Forwarded-For": "192.0.2.30"}
    for _ in range(30):
        client.post(UNSUBSCRIBE, headers=ip)
    clock.value += 41
    blocked = client.post(UNSUBSCRIBE, headers=ip)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) == 19

    clock.value += 20
    assert client.post(UNSUBSCRIBE, headers=ip).status_code == 404


def test_rejection_log_is_scrubbed(capsys: pytest.CaptureFixture[str]) -> None:
    """C8."""
    configure_logging()
    sub = f"user_test_{uuid.uuid4().hex[:12]}"
    value = token(sub)
    headers = {**bearer(value), "X-Forwarded-For": "203.0.113.55"}
    for _ in range(300):
        client.get("/v1/me", headers=headers)
    assert client.get("/v1/me", headers=headers).status_code == 429
    ip = {"X-Forwarded-For": "203.0.113.56"}
    for _ in range(30):
        client.post("/v1/unsubscribe/secret-token-value", headers=ip)
    assert (
        client.post("/v1/unsubscribe/secret-token-value", headers=ip).status_code == 429
    )

    out = capsys.readouterr().out
    events = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    rejected = [e for e in events if e.get("event") == "ratelimit.rejected"]
    assert {(e["route"], e["key_kind"]) for e in rejected} == {
        ("/v1/me", "user"),
        ("/v1/unsubscribe/{token}", "ip"),
    }
    assert all(
        set(e) == {"event", "route", "key_kind", "timestamp", "level", "logger"}
        for e in rejected
    )
    # The API's own lines: the test client's httpx logger prints the URLs it requests.
    api_log = " ".join(
        line
        for line, event in zip(out.splitlines(), events_of(out), strict=False)
        if event.get("logger") != "httpx"
    )
    for secret in (value, sub, "203.0.113.55", "203.0.113.56", "secret-token-value"):
        assert secret not in api_log


def test_headers_on_every_v1_answer() -> None:
    """C9."""
    hsts = "max-age=31536000; includeSubDomains"
    headers = new_headers()
    answers = {
        "200": client.get("/v1/me", headers=headers),
        "401": client.get("/v1/me"),
        "404": client.get(f"/v1/businesses/{uuid.uuid4()}", headers=headers),
        "403": client.get("/v1/me", headers={**headers, **EVIL}),
    }
    flooded = new_headers()
    for _ in range(301):
        limited = client.get("/v1/me", headers=flooded)
    answers["429"] = limited
    for code, response in answers.items():
        assert response.status_code == int(code), code
        assert response.headers["strict-transport-security"] == hsts, code
        assert response.headers["x-content-type-options"] == "nosniff", code
        assert response.headers["cache-control"] == "no-store", code


def test_probes_not_limited() -> None:
    """C10."""
    ip = {"X-Forwarded-For": "192.0.2.40"}
    for _ in range(500):
        assert client.get("/healthz/live", headers=ip).status_code == 200


def test_jobs_do_not_load_http_middleware() -> None:
    """C11."""
    code = (
        "import sys, app.jobs.run_due;"
        "bad = [m for m in ('app.ratelimit', 'app.security') if m in sys.modules];"
        "sys.exit(1 if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=CORE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
