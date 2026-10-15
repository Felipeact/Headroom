import json
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Annotated, Any

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.auth import Member, current_user, require_member
from app.db import get_session, get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.accounts import service
from app.modules.accounts.models import Business, Membership, User
from app.problems import install_problem_handlers
from tests.tokens import bearer, token

client = TestClient(app)

pytestmark = pytest.mark.usefixtures("migrated_database")

HARBOR = {
    "name": "Harbor Street Plumbing",
    "province": "ON",
    "time_zone": "America/Toronto",
}
BAYVIEW = {
    "name": "Bayview Bakery",
    "province": "BC",
    "time_zone": "America/Vancouver",
}
BUSINESS_KEYS = {
    "id",
    "name",
    "province",
    "time_zone",
    "country",
    "currency",
    "role",
    "created_at",
}
PROVINCES = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "SK", "YT"]
TIME_ZONES = [
    "America/St_Johns",
    "America/Halifax",
    "America/Toronto",
    "America/Winnipeg",
    "America/Regina",
    "America/Edmonton",
    "America/Vancouver",
    "America/Whitehorse",
]


class Caller:
    """A signed-in user, as the API sees them through a signed test token."""

    def __init__(self) -> None:
        self.sub = f"user_test_{uuid.uuid4().hex[:12]}"
        self.headers = bearer(token(self.sub))
        self.id = uuid.UUID(client.get("/v1/me", headers=self.headers).json()["id"])

    def post(self, body: dict[str, Any]) -> Any:
        return client.post("/v1/businesses", json=body, headers=self.headers)

    def get(self, path: str) -> Any:
        return client.get(path, headers=self.headers)

    def patch(self, path: str, body: dict[str, Any]) -> Any:
        return client.patch(path, json=body, headers=self.headers)


@pytest.fixture
def caller() -> Caller:
    return Caller()


def _owner(body: dict[str, str]) -> tuple[Caller, str]:
    owner = Caller()
    response = owner.post(body)
    assert response.status_code == 201
    return owner, response.json()["id"]


@pytest.fixture
def owner_a() -> tuple[Caller, str]:
    return _owner(HARBOR)


@pytest.fixture
def owner_b() -> tuple[Caller, str]:
    return _owner(BAYVIEW)


def counts(user_id: uuid.UUID) -> tuple[int, int]:
    """(businesses linked to the user, memberships of the user)."""
    with get_sessionmaker()() as session:
        memberships = session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.user_id == user_id)
        )
        businesses = session.scalar(
            select(func.count())
            .select_from(Business)
            .join(Membership, Membership.business_id == Business.id)
            .where(Membership.user_id == user_id)
        )
    return int(businesses or 0), int(memberships or 0)


def orphan_businesses() -> int:
    with get_sessionmaker()() as session:
        count = session.scalar(
            select(func.count())
            .select_from(Business)
            .outerjoin(Membership, Membership.business_id == Business.id)
            .where(Membership.business_id.is_(None))
        )
    return int(count or 0)


def stored(business_id: str) -> Business:
    with get_sessionmaker()() as session:
        return session.scalars(
            select(Business).where(Business.id == uuid.UUID(business_id))
        ).one()


def error_for(response: Any, field: str) -> dict[str, Any]:
    assert response.status_code == 422, response.text
    assert response.headers["content-type"] == "application/problem+json"
    matches = [e for e in response.json()["errors"] if e["loc"][-1] == field]
    assert matches, response.json()
    return matches[0]


# S1 - create


def test_create_returns_business(caller: Caller) -> None:
    response = caller.post(HARBOR)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == BUSINESS_KEYS
    assert body["name"] == "Harbor Street Plumbing"
    assert body["province"] == "ON"
    assert body["time_zone"] == "America/Toronto"
    assert body["country"] == "CA"
    assert body["currency"] == "CAD"
    assert body["role"] == "owner"
    uuid.UUID(body["id"])


def test_create_stores_business_and_owner(caller: Caller) -> None:
    business_id = caller.post(HARBOR).json()["id"]

    with get_sessionmaker()() as session:
        businesses = session.scalars(
            select(Business).where(Business.id == uuid.UUID(business_id))
        ).all()
        memberships = session.scalars(
            select(Membership).where(Membership.user_id == caller.id)
        ).all()
    assert len(businesses) == 1
    assert [(str(m.business_id), m.role) for m in memberships] == [
        (business_id, "owner")
    ]


def test_name_is_trimmed(caller: Caller) -> None:
    response = caller.post({**HARBOR, "name": "  Harbor Street Plumbing  "})

    assert response.json()["name"] == "Harbor Street Plumbing"
    assert stored(response.json()["id"]).name == "Harbor Street Plumbing"


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_name_bounds_rejected(caller: Caller, name: str) -> None:
    error_for(caller.post({**HARBOR, "name": name}), "name")
    assert counts(caller.id) == (0, 0)


def test_name_bounds_100_accepted(caller: Caller) -> None:
    assert caller.post({**HARBOR, "name": "x" * 100}).status_code == 201


@pytest.mark.parametrize("province", ["XX", "on", "Ontario", None])
def test_province_values_rejected(caller: Caller, province: str | None) -> None:
    body = {k: v for k, v in HARBOR.items() if k != "province"}
    if province is not None:
        body["province"] = province
    error_for(caller.post(body), "province")


@pytest.mark.parametrize("province", PROVINCES)
def test_province_values_accepted(caller: Caller, province: str) -> None:
    response = caller.post({**HARBOR, "province": province})
    assert response.status_code == 201
    assert response.json()["province"] == province


def test_quebec_refused(caller: Caller) -> None:
    error = error_for(caller.post({**HARBOR, "province": "QC"}), "province")

    assert error["type"] == "province_not_available"
    assert error["msg"] == "Headroom isn't available in Quebec yet."
    assert counts(caller.id) == (0, 0)


@pytest.mark.parametrize("time_zone", ["America/New_York", "UTC", "", None])
def test_time_zone_values_rejected(caller: Caller, time_zone: str | None) -> None:
    body = {k: v for k, v in HARBOR.items() if k != "time_zone"}
    if time_zone is not None:
        body["time_zone"] = time_zone
    error_for(caller.post(body), "time_zone")


@pytest.mark.parametrize("time_zone", TIME_ZONES)
def test_time_zone_values_accepted(caller: Caller, time_zone: str) -> None:
    response = caller.post({**HARBOR, "time_zone": time_zone})
    assert response.status_code == 201
    assert response.json()["time_zone"] == time_zone


def test_second_business_conflicts(caller: Caller) -> None:
    assert caller.post(HARBOR).status_code == 201

    response = caller.post({**HARBOR, "name": "Second Shop"})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "You already own a business."
    assert counts(caller.id) == (1, 1)


def test_concurrent_creates(caller: Caller) -> None:
    barrier = threading.Barrier(2)
    created: list[service.MemberBusiness] = []
    conflicts: list[service.AlreadyOwnsBusinessError] = []
    errors: list[BaseException] = []
    orphans_before = orphan_businesses()

    def create() -> None:
        try:
            with get_sessionmaker()() as session:
                barrier.wait()
                created.append(
                    service.create_business(
                        session,
                        user_id=caller.id,
                        name="Harbor Street Plumbing",
                        province="ON",
                        time_zone="America/Toronto",
                    )
                )
        except service.AlreadyOwnsBusinessError as exc:
            conflicts.append(exc)
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=create) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len(created) == 1
    assert len(conflicts) == 1
    assert counts(caller.id) == (1, 1)
    assert orphan_businesses() == orphans_before


INSERT_BUSINESS = (
    "INSERT INTO businesses (id, name, province, time_zone, country, currency)"
    " VALUES (:id, :name, :province, :time_zone, :country, :currency)"
)
INSERT_MEMBERSHIP = (
    "INSERT INTO memberships (business_id, user_id, role)"
    " VALUES (:business_id, :user_id, :role)"
)


def _good_business() -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "name": "Ok",
        "province": "ON",
        "time_zone": "America/Toronto",
        "country": "CA",
        "currency": "CAD",
    }


def _violates(statements: list[tuple[str, dict[str, Any]]]) -> str:
    """Run the statements in one rolled-back transaction; return the last one's error."""
    with get_sessionmaker()() as session:
        *setup, (last, params) = statements
        for statement, values in setup:
            session.execute(text(statement), values)
        with pytest.raises(IntegrityError) as raised:
            session.execute(text(last), params)
        session.rollback()
    return str(raised.value.orig)


@pytest.mark.parametrize(
    ("change", "constraint"),
    [
        ({"country": "US"}, "ck_businesses_country"),
        ({"currency": "USD"}, "ck_businesses_currency"),
        ({"province": "QC"}, "ck_businesses_province"),
        ({"time_zone": "UTC"}, "ck_businesses_time_zone"),
        ({"name": ""}, "ck_businesses_name_length"),
    ],
)
def test_database_constraints_businesses(
    change: dict[str, str], constraint: str
) -> None:
    assert constraint in _violates([(INSERT_BUSINESS, {**_good_business(), **change})])


def test_database_constraints_memberships(
    caller: Caller, owner_a: tuple[Caller, str]
) -> None:
    a, business_a = owner_a
    viewer = {
        "business_id": uuid.UUID(business_a),
        "user_id": caller.id,
        "role": "viewer",
    }
    assert "ck_memberships_role" in _violates([(INSERT_MEMBERSHIP, viewer)])

    other = _good_business()
    second_owner = {"business_id": other["id"], "user_id": a.id, "role": "owner"}
    assert "uq_memberships_owner_user_id" in _violates(
        [(INSERT_BUSINESS, other), (INSERT_MEMBERSHIP, second_owner)]
    )


# S2 - access


def test_list_only_own(
    caller: Caller, owner_a: tuple[Caller, str], owner_b: tuple[Caller, str]
) -> None:
    a, business_a = owner_a

    response = a.get("/v1/businesses")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [business_a]
    assert set(items[0]) == BUSINESS_KEYS
    assert caller.get("/v1/businesses").json() == {"items": []}


def test_list_oldest_membership_first() -> None:
    with get_sessionmaker()() as session:
        # Only owners exist until spec 31, so the one-owned-business index is dropped
        # inside this transaction (Postgres DDL is transactional) and comes back on
        # rollback.
        session.execute(text("DROP INDEX uq_memberships_owner_user_id"))
        user = User(clerk_user_id=f"user_test_{uuid.uuid4().hex[:12]}")
        newer = Business(name="Newer", province="ON", time_zone="America/Toronto")
        older = Business(name="Older", province="ON", time_zone="America/Toronto")
        session.add_all([user, newer, older])
        session.flush()
        session.add_all(
            [
                Membership(
                    business_id=newer.id,
                    user_id=user.id,
                    role="owner",
                    created_at=datetime(2026, 1, 2, tzinfo=UTC),
                ),
                Membership(
                    business_id=older.id,
                    user_id=user.id,
                    role="owner",
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ]
        )
        session.flush()

        names = [b.name for b in service.list_businesses(session, user.id)]

        session.rollback()
    assert names == ["Older", "Newer"]


def test_member_reads_business(owner_a: tuple[Caller, str]) -> None:
    a, business_a = owner_a

    response = a.get(f"/v1/businesses/{business_a}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == BUSINESS_KEYS
    assert body["id"] == business_a
    assert body["name"] == "Harbor Street Plumbing"
    assert body["province"] == "ON"
    assert body["time_zone"] == "America/Toronto"
    assert body["country"] == "CA"
    assert body["currency"] == "CAD"
    assert body["role"] == "owner"


def test_non_member_gets_404(
    owner_a: tuple[Caller, str], owner_b: tuple[Caller, str]
) -> None:
    _, business_a = owner_a
    b, _ = owner_b
    missing = str(uuid.uuid4())

    def read(business: str) -> Any:
        return b.get(f"/v1/businesses/{business}")

    def rename(business: str) -> Any:
        return b.patch(f"/v1/businesses/{business}", {"name": "Taken"})

    for call in (read, rename):
        foreign, absent = call(business_a), call(missing)
        assert foreign.status_code == 404
        assert foreign.headers["content-type"] == "application/problem+json"
        assert foreign.json()["detail"] == "Business not found."
        assert absent.status_code == 404
        assert {k: v for k, v in foreign.json().items() if k != "instance"} == {
            k: v for k, v in absent.json().items() if k != "instance"
        }


def test_malformed_business_id(caller: Caller) -> None:
    error_for(caller.get("/v1/businesses/not-a-uuid"), "business_id")
    error_for(
        caller.patch("/v1/businesses/not-a-uuid", {"name": "Taken"}), "business_id"
    )


def test_role_not_allowed_gets_403(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = FastAPI()
    install_problem_handlers(probe)

    @probe.get("/probe/{business_id}")
    def owner_only(
        member: Annotated[Member, Depends(require_member(service.Role.OWNER))],
    ) -> dict[str, str]:
        return {"role": member.role}

    def no_session() -> Iterator[None]:
        yield None

    probe.dependency_overrides[current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    probe.dependency_overrides[get_session] = no_session
    probe_client = TestClient(probe)
    role = {"value": "viewer"}
    monkeypatch.setattr(
        service, "get_membership", lambda *_, **__: SimpleNamespace(role=role["value"])
    )

    denied = probe_client.get(f"/probe/{uuid.uuid4()}")
    role["value"] = "owner"
    allowed = probe_client.get(f"/probe/{uuid.uuid4()}")

    assert denied.status_code == 403
    assert denied.headers["content-type"] == "application/problem+json"
    assert denied.json()["detail"] == "You don't have permission to do this."
    assert allowed.status_code == 200


def test_owner_patches_business(owner_a: tuple[Caller, str]) -> None:
    a, business_a = owner_a
    path = f"/v1/businesses/{business_a}"

    renamed = a.patch(path, {"name": "Harbor Street Plumbing Ltd"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Harbor Street Plumbing Ltd"
    assert renamed.json()["province"] == "ON"
    assert renamed.json()["time_zone"] == "America/Toronto"

    moved = a.patch(path, {"province": "BC", "time_zone": "America/Vancouver"})
    assert moved.status_code == 200
    assert moved.json()["name"] == "Harbor Street Plumbing Ltd"
    assert moved.json()["province"] == "BC"
    assert moved.json()["time_zone"] == "America/Vancouver"

    assert a.get(path).json() == moved.json()


def test_invalid_patch_changes_nothing(owner_a: tuple[Caller, str]) -> None:
    a, business_a = owner_a
    path = f"/v1/businesses/{business_a}"
    before = a.get(path).json()

    error_for(a.patch(path, {"name": "   "}), "name")
    quebec = error_for(a.patch(path, {"province": "QC"}), "province")
    assert quebec["type"] == "province_not_available"
    error_for(a.patch(path, {"time_zone": "UTC"}), "time_zone")

    row = stored(business_a)
    assert (row.name, row.province, row.time_zone) == (
        before["name"],
        before["province"],
        before["time_zone"],
    )


def test_non_member_patch_changes_nothing(
    owner_a: tuple[Caller, str], owner_b: tuple[Caller, str]
) -> None:
    _, business_a = owner_a
    b, _ = owner_b

    response = b.patch(f"/v1/businesses/{business_a}", {"name": "Taken"})

    assert response.status_code == 404
    assert stored(business_a).name == "Harbor Street Plumbing"


def _routes(routes: list[Any]) -> Iterator[APIRoute]:
    # Included routers wrap their routes; this FastAPI keeps them out of `app.routes`.
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from _routes(nested.routes)


def _requires_member(route: APIRoute) -> bool:
    pending = list(route.dependant.dependencies)
    while pending:
        dependant = pending.pop()
        call = dependant.call
        if getattr(call, "__qualname__", "") == "require_member.<locals>.member":
            return True
        pending.extend(dependant.dependencies)
    return False


def business_routes_missing_member(target: FastAPI) -> list[str]:
    return [
        f"{sorted(route.methods)} {route.path}"
        for route in _routes(target.routes)
        if "{business_id}" in route.path and not _requires_member(route)
    ]


def test_every_business_route_requires_member() -> None:
    walked = {
        (method, route.path)
        for route in _routes(app.routes)
        if "{business_id}" in route.path
        for method in route.methods
    }
    documented = {
        (method.upper(), path.removeprefix("/v1"))
        for path, methods in app.openapi()["paths"].items()
        if "{business_id}" in path
        for method in methods
    }
    assert ("GET", "/businesses/{business_id}") in walked
    assert walked == documented
    assert business_routes_missing_member(app) == []

    careless = FastAPI()
    router = APIRouter(prefix="/v1")

    @router.get("/businesses/{business_id}/careless")
    def careless_route(business_id: uuid.UUID) -> None:
        return None

    careless.include_router(router)
    assert business_routes_missing_member(careless) == [
        "['GET'] /v1/businesses/{business_id}/careless"
    ]


# S5 - nothing leaks


def test_business_logs(caller: Caller, capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    capsys.readouterr()
    business_id = caller.post({**HARBOR, "name": "Secret Name Plumbing"}).json()["id"]
    caller.patch(f"/v1/businesses/{business_id}", {"province": "BC"})

    output = capsys.readouterr()
    text_out = output.out + output.err
    lines = [json.loads(line) for line in text_out.splitlines() if line.startswith("{")]
    created = [line for line in lines if line.get("event") == "business.created"]
    updated = [line for line in lines if line.get("event") == "business.updated"]
    assert len(created) == 1
    assert len(updated) == 1
    for line in (created[0], updated[0]):
        assert line["business_id"] == business_id
        assert line["user_id"] == str(caller.id)
    assert "Secret Name Plumbing" not in text_out


def _keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def test_no_foreign_fields(
    owner_a: tuple[Caller, str], owner_b: tuple[Caller, str]
) -> None:
    a, business_a = owner_a
    _, business_b = owner_b
    path = f"/v1/businesses/{business_a}"
    responses = [
        a.get("/v1/businesses"),
        a.get(path),
        a.patch(path, {"name": "Harbor Street Plumbing"}),
        Caller().post(HARBOR),
    ]

    for response in responses:
        assert response.status_code in (200, 201)
        assert "clerk_user_id" not in set(_keys(response.json()))
    for response in responses[:3]:
        assert business_b not in response.text
