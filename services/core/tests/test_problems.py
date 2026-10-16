import json
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from app.log import configure_logging
from app.main import app

PROBLEM_JSON = "application/problem+json"
SANDBOX_TOKEN = "access-sandbox-00000000-0000-0000-0000-000000000000"

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def test_routes() -> Iterator[None]:
    router = APIRouter()

    @router.get("/test/conflict")
    def conflict() -> None:
        raise HTTPException(
            status_code=409, detail="Already connected", headers={"X-Test": "1"}
        )

    @router.get("/test/boom")
    def boom() -> None:
        raise RuntimeError("boom-secret-detail")

    @router.get("/test/items/{item_id}")
    def item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    before = list(app.router.routes)
    app.include_router(router)
    yield
    app.router.routes[:] = before


def test_unknown_route_returns_404_problem() -> None:
    response = client.get("/does-not-exist?x=1")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Not Found",
        "instance": "/does-not-exist",
    }


def test_wrong_method_returns_405_problem_with_allow() -> None:
    response = client.post("/healthz/live")

    assert response.status_code == 405
    assert response.headers["content-type"] == PROBLEM_JSON
    body = response.json()
    assert body["status"] == 405
    assert body["title"] == "Method Not Allowed"
    assert "GET" in response.headers["allow"]


@pytest.mark.usefixtures("test_routes")
def test_http_exception_becomes_problem_with_headers() -> None:
    response = client.get("/test/conflict")

    assert response.status_code == 409
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.headers["x-test"] == "1"
    assert response.json() == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "detail": "Already connected",
        "instance": "/test/conflict",
    }


@pytest.mark.usefixtures("test_routes")
def test_validation_error_returns_422_problem() -> None:
    response = client.get("/test/items/not-a-number")

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON
    body = response.json()
    assert body["status"] == 422
    assert body["title"] == HTTPStatus(422).phrase
    assert body["errors"]
    for error in body["errors"]:
        assert set(error) == {"loc", "msg", "type"}


@pytest.mark.usefixtures("test_routes")
def test_validation_error_does_not_echo_input() -> None:
    response = client.get(f"/test/items/{SANDBOX_TOKEN}")

    assert response.status_code == 422
    assert SANDBOX_TOKEN not in response.text


@pytest.mark.usefixtures("test_routes")
def test_unhandled_exception_returns_generic_500() -> None:
    response = client.get("/test/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.json()["detail"] == "An unexpected error occurred."
    assert "boom-secret-detail" not in response.text
    assert "RuntimeError" not in response.text


@pytest.mark.usefixtures("test_routes")
def test_unhandled_exception_logged_once(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    client.get("/test/boom")

    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    records = [r for r in lines if r.get("event") == "request.unhandled_exception"]
    assert len(records) == 1
    record = records[0]
    assert record["level"] == "error"
    assert record["method"] == "GET"
    assert record["path"] == "/test/boom"
    assert "RuntimeError" in str(record["exception"])
