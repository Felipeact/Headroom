import threading
import time
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import get_sessionmaker
from app.main import app
from app.modules.accounts import service
from app.modules.accounts.models import User
from tests.tokens import bearer, token

client = TestClient(app)

# Accepted requests create users rows, so the app needs a migrated database.
pytestmark = pytest.mark.usefixtures("migrated_database")


@pytest.fixture
def sub() -> Iterator[str]:
    value = f"user_test_{uuid.uuid4().hex[:12]}"
    yield value
    with get_sessionmaker()() as session:
        session.query(User).filter(User.clerk_user_id == value).delete()
        session.commit()


def rows_for(clerk_user_id: str) -> int:
    with get_sessionmaker()() as session:
        count = session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.clerk_user_id == clerk_user_id)
        )
    return int(count or 0)


def test_first_request_creates_user(sub: str) -> None:
    assert rows_for(sub) == 0

    response = client.get("/v1/me", headers=bearer(token(sub)))

    assert response.status_code == 200
    assert rows_for(sub) == 1
    with get_sessionmaker()() as session:
        user = session.scalars(select(User).where(User.clerk_user_id == sub)).one()
    assert str(user.id) == response.json()["id"]


def test_repeat_requests_reuse_user(sub: str) -> None:
    ids = {
        client.get("/v1/me", headers=bearer(token(sub))).json()["id"] for _ in range(3)
    }

    assert len(ids) == 1
    assert rows_for(sub) == 1


def test_concurrent_first_requests(sub: str) -> None:
    barrier = threading.Barrier(2)
    results: list[uuid.UUID] = []
    errors: list[BaseException] = []

    def first_request() -> None:
        try:
            with get_sessionmaker()() as session:
                barrier.wait()
                results.append(service.get_or_create_user(session, sub).id)
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=first_request) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len(results) == 2
    assert results[0] == results[1]
    assert rows_for(sub) == 1


def test_rejected_request_creates_nothing() -> None:
    sub = "user_test_rejected"
    now = int(time.time())
    expired = token(sub, iat=now - 70, nbf=now - 70, exp=now - 10)

    response = client.get("/v1/me", headers=bearer(expired))

    assert response.status_code == 401
    assert rows_for(sub) == 0
