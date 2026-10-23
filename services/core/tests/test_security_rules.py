"""Spec 33 S3-S5: every endpoint denies another business, every rule has a proof (C16-C29)."""

import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from itertools import count
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import app
from app.modules.bank_sync.plaid import PlaidError, get_plaid_client
from tests.bookkeeper_support import sql
from tests.conftest import CORE
from tests.test_bank_connect import FakePlaid
from tests.test_bookkeeper_access import BASE, BOOKKEEPER_ONLY, OWNER_ONLY, SHARED
from tests.test_businesses import BAYVIEW, HARBOR, Caller
from tests.tokens import bearer, token

pytestmark = pytest.mark.usefixtures("migrated_database")

REPO = CORE.parents[1]
SECURITY = REPO / "context" / "security"
client = TestClient(app, raise_server_exceptions=False)

USER_SCOPED = {
    ("GET", "/v1/businesses"),
    ("POST", "/v1/businesses"),
    ("GET", "/v1/me"),
    ("GET", "/v1/me/email-preferences"),
    ("PUT", "/v1/me/email-preferences"),
    ("GET", "/v1/invitations/{token}"),
    ("POST", "/v1/invitations/{token}/accept"),
}
PUBLIC = {
    ("POST", "/v1/webhooks/plaid"),
    ("POST", "/v1/unsubscribe/{token}"),
    ("GET", "/healthz/live"),
    ("GET", "/healthz/ready"),
}

_ips = count(1)


def fresh_ip() -> dict[str, str]:
    """Each request from its own address, so the per-IP limits never get in the way."""
    n = next(_ips)
    return {"X-Forwarded-For": f"198.18.{n // 250}.{n % 250 + 1}"}


def v1_routes() -> set[tuple[str, str]]:
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def filled(path: str, **ids: object) -> str:
    values: dict[str, object] = {
        "business_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "alert_id": uuid.uuid4(),
        "payment_id": uuid.uuid4(),
        "token": "not-a-real-token",
        **ids,
    }
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]), path)


def business_rows(business_id: str) -> dict[str, int]:
    b = uuid.UUID(business_id)
    return {
        table: int(sql(f"SELECT count(*) FROM {table} WHERE {column} = :b", b=b)[0][0])
        for table, column in (
            ("businesses", "id"),
            ("memberships", "business_id"),
            ("audit_log", "business_id"),
            ("bank_connections", "business_id"),
        )
    }


def test_stranger_denied_on_every_business_route() -> None:
    """C16."""
    owner = Caller()
    created = owner.post(HARBOR)
    assert created.status_code == 201
    business_a = created.json()["id"]
    stranger = Caller()
    assert stranger.post(BAYVIEW).status_code == 201

    routes = {(method, path) for method, path in v1_routes() if path.startswith(BASE)}
    expected = {
        (method, "/v1/businesses/{business_id}" + ("" if tail == "/" else tail))
        for method, tail in OWNER_ONLY | SHARED | BOOKKEEPER_ONLY
    }
    assert routes == expected
    assert len(routes) == 28

    before = business_rows(business_a)
    for method, path in sorted(routes):
        response = client.request(
            method,
            filled(path, business_id=business_a),
            headers={**stranger.headers, **fresh_ip()},
            json={} if method in {"POST", "PUT", "PATCH"} else None,
        )
        assert response.status_code == 404, (method, path, response.status_code)
        assert response.json()["detail"] == "Business not found.", (method, path)
    assert business_rows(business_a) == before


def test_every_v1_route_is_classified() -> None:
    """C17."""
    other = {
        route
        for route in v1_routes()
        if route[1].startswith("/v1") and not route[1].startswith(BASE)
    }
    assert other == USER_SCOPED | {r for r in PUBLIC if r[1].startswith("/v1")}


def expired() -> str:
    now = int(time.time())
    return token("user_test_expired", iat=now - 70, nbf=now - 70, exp=now - 10)


def other_key() -> str:
    return token("user_test_other", key=rsa.generate_private_key(65537, 2048))


def test_unauthenticated_gets_401_with_challenge() -> None:
    """C19."""
    routes = {r for r in v1_routes() if r[1].startswith("/v1") and r not in PUBLIC}
    assert len(routes) == 35
    for method, path in sorted(routes):
        for label, headers in (
            ("missing", {}),
            ("expired", bearer(expired())),
            ("other_key", bearer(other_key())),
        ):
            response = client.request(
                method, filled(path), headers={**headers, **fresh_ip()}
            )
            assert response.status_code == 401, (method, path, label)
            assert response.headers["www-authenticate"] == "Bearer", (method, path)


def run_app(env: dict[str, str]) -> list[str]:
    code = (
        "import json; from app.main import app;"
        "print(json.dumps(sorted(getattr(r, 'path', '') for r in app.routes)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parent,  # no .env.local here: only `env` decides
        env={"PYTHONPATH": str(CORE), "PATH": "", "SYSTEMROOT": "C:\\Windows", **env},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    paths: list[str] = json.loads(result.stdout.splitlines()[-1])
    return paths


def test_docs_off_unless_enabled(tmp_path: Path) -> None:
    """C20."""
    docs = {"/docs", "/redoc", "/openapi.json"}
    assert docs.isdisjoint(run_app({}))
    assert docs.isdisjoint(run_app({"API_DOCS_ENABLED": "false"}))
    assert docs <= set(run_app({"API_DOCS_ENABLED": "true"}))
    # Truly unset: no variable, and a cwd with no .env.local for the docs switch to read.
    env = {k: v for k, v in os.environ.items() if k != "API_DOCS_ENABLED"}
    contract = REPO / "contracts" / "openapi.json"
    before = contract.stat().st_mtime_ns
    exported = subprocess.run(
        [sys.executable, "-m", "app.export_openapi"],
        cwd=tmp_path,
        env={**env, "PYTHONPATH": str(CORE)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert exported.returncode == 0, exported.stderr
    assert contract.stat().st_mtime_ns > before
    assert "/v1/me" in json.loads(contract.read_text(encoding="utf8"))["paths"]


def test_public_list_is_exactly_four() -> None:
    """C21."""
    public = set()
    for method, path in v1_routes():
        if not path.startswith("/v1"):
            continue
        response = client.request(method, filled(path), headers=fresh_ip())
        if response.status_code != 401 or "www-authenticate" not in response.headers:
            public.add((method, path))
    assert public == {r for r in PUBLIC if r[1].startswith("/v1")}
    outside = {
        getattr(route, "path", "")
        for route in app.routes
        if not getattr(route, "path", "/v1").startswith("/v1")
    }
    assert outside == {"/healthz/live", "/healthz/ready"}
    assert len(PUBLIC) == 4


# S4 - rules.md


def security_bullets() -> list[str]:
    text = (REPO / "AGENTS.md").read_text(encoding="utf8")
    section = text.split("## Security and data handling", 1)[1].split("\n## ", 1)[0]
    return [line for line in section.splitlines() if line.startswith("- ")]


def rules_rows() -> list[tuple[str, str]]:
    text = (SECURITY / "rules.md").read_text(encoding="utf8")
    return re.findall(r"^\| (R\d+) \|.*?\| (.*) \|$", text, flags=re.MULTILINE)


def test_rules_table_has_a_row_per_rule() -> None:
    """C22."""
    bullets = security_bullets()
    rows = rules_rows()
    assert len(bullets) == 8
    assert [number for number, _ in rows] == [f"R{n}" for n in range(1, 9)]
    for number, cell in rows:
        proof = cell.startswith("Proof:") and "`" in cell
        written = cell.startswith("Written check:") and re.search(
            r"Last run: \d{4}-\d{2}-\d{2}", cell
        )
        assert proof or written, number


def named_tests() -> list[str]:
    text = (SECURITY / "rules.md").read_text(encoding="utf8")
    return re.findall(r"`((?:services/core|frontend)/tests/[^`]+)`", text)


def test_rules_table_tests_exist() -> None:
    """C23."""
    names = named_tests()
    assert names
    for name in names:
        path, _, function = name.partition("::")
        source = REPO / path
        assert source.is_file(), name
        if function:
            assert f"def {function}(" in source.read_text(encoding="utf8"), name


@pytest.fixture
def fake_plaid() -> Iterator[FakePlaid]:
    plaid = FakePlaid()
    app.dependency_overrides[get_plaid_client] = lambda: plaid
    yield plaid
    app.dependency_overrides.pop(get_plaid_client, None)


def test_error_bodies_leak_nothing(fake_plaid: FakePlaid) -> None:
    """C24."""
    secrets = [
        "access-sandbox-00000000-0000-0000-0000-000000000000",
        "Bearer abc.def.ghi",
        "123456789012",
    ]
    mixed = " ".join(secrets)
    owner = Caller()
    created = owner.post(HARBOR)
    assert created.status_code == 201
    business_id = created.json()["id"]

    unprocessable = client.post(
        "/v1/businesses",
        json={"name": mixed, "province": mixed, "time_zone": mixed},
        headers={**Caller().headers, **fresh_ip()},
    )
    fake_plaid.fail["link_token"] = PlaidError(
        error_type=secrets[0], error_code=secrets[1], request_id=secrets[2]
    )
    bad_gateway = client.post(
        f"/v1/businesses/{business_id}/bank/link-token", headers=owner.headers
    )

    router = APIRouter()

    @router.get("/test/boom")
    def boom() -> None:
        raise RuntimeError(mixed)

    before = list(app.router.routes)
    app.include_router(router)
    try:
        server_error = client.get("/test/boom", headers=fresh_ip())
    finally:
        app.router.routes[:] = before

    for response, code in (
        (unprocessable, 422),
        (server_error, 500),
        (bad_gateway, 502),
    ):
        assert response.status_code == code
        for secret in secrets:
            assert secret not in response.text, (code, secret)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


SECRET_PATTERNS = [
    r"access-(sandbox|production|development)-[0-9a-f]{8}-[0-9a-f]{4}",
    r"sk_(live|test)_[A-Za-z0-9]{20,}",
    r"\bre_[A-Za-z0-9_]{20,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
]
SCANNED = (
    "services/core/app/",
    "frontend/app/",
    "frontend/components/",
    "frontend/lib/",
    ".railway/",
    ".github/",
)


def test_no_env_files_or_secrets_tracked() -> None:
    """C26."""
    files = tracked_files()
    env = [f for f in files if Path(f).name.startswith(".env")]
    assert all(Path(f).name == ".env.example" for f in env), env
    assert env, "the .env.example files should be tracked"

    scanned = [f for f in files if f.startswith(SCANNED) or f in env]
    hits = []
    for name in scanned:
        try:
            text = (REPO / name).read_text(encoding="utf8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        hits += [name for p in SECRET_PATTERNS if re.search(p, text)]
    assert hits == []


# S5 - people, access, incident plan


def test_incident_plan_has_its_parts() -> None:
    """C28."""
    text = (SECURITY / "incident-response.md").read_text(encoding="utf8")
    for section in ("Detect", "Decide", "First hour", "Notify", "Client notice"):
        assert re.search(rf"^## {section}\s*$", text, flags=re.MULTILINE), section
    first = text.split("## First hour", 1)[1].split("\n## ", 1)[0]
    steps = re.findall(r"^\d+\. .*$", first, flags=re.MULTILINE)
    assert steps
    for name in (
        "Plaid access tokens",
        "TOKEN_ENCRYPTION_KEYS",
        "CLERK_SECRET_KEY",
        "RESEND_API_KEY",
        "Railway database password",
    ):
        assert name in first, name
    notify = text.split("## Notify", 1)[1].split("\n## ", 1)[0]
    assert notify.index("clients") < notify.index("Office of the Privacy Commissioner")
    notice = text.split("## Client notice", 1)[1]
    for slot in (
        "<what happened>",
        "<what data>",
        "<what we did>",
        "<what you should do>",
    ):
        assert slot in notice, slot


ACCESS_SERVICES = (
    "Clerk",
    "Railway",
    "GitHub",
    "Resend",
    "PostHog",
    "Sentry",
    "Plaid",
    "Domain registrar",
)


def test_access_table_complete() -> None:
    """C27."""
    text = (SECURITY / "access.md").read_text(encoding="utf8")
    rows = [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in text.splitlines()
        if line.startswith("| ") and line.split("|")[1].strip() in ACCESS_SERVICES
    ]
    roles: dict[tuple[str, str], set[str]] = {}
    for service in ACCESS_SERVICES:
        assert any(row[0] == service for row in rows), service
    for row in rows:
        service, person, role, reason, two_factor, checked = row[:6]
        assert person and role and reason, row
        assert two_factor == "yes", row
        age = datetime.now(UTC).date() - date.fromisoformat(checked)
        assert age <= timedelta(days=90), row
        roles.setdefault((service, person), set()).add(role)
    for (service, person), held in roles.items():
        assert len(held) == 1, f"{person} holds {sorted(held)} on {service}"


def test_rehearsal_recorded() -> None:
    """C29."""
    records = sorted(SECURITY.glob("rehearsal-*.md"))
    assert records
    record = records[-1]
    text = record.read_text(encoding="utf8")
    stamp = record.stem.removeprefix("rehearsal-")
    date.fromisoformat(stamp)
    for label in ("Date:", "Scenario:", "Participants:"):
        assert re.search(rf"^{label} \S", text, flags=re.MULTILINE), label
    plan = (SECURITY / "incident-response.md").read_text(encoding="utf8")
    first_hour = plan.split("## First hour", 1)[1].split("\n## ", 1)[0]
    steps = re.findall(r"^\d+\. ", first_hour, flags=re.MULTILINE)
    timings = re.findall(r"^Step \d+: \d+ min", text, flags=re.MULTILINE)
    assert len(timings) == len(steps)
    assert "## What the plan got wrong" in text
    wrong = text.split("## What the plan got wrong", 1)[1].split("\n## ", 1)[0]
    assert wrong.strip(), "write what the plan got wrong, or the word nothing"
    assert f"Last rehearsed: {stamp}" in plan
