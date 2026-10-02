import socket
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url

from app.db import create_db_engine, get_engine
from app.main import app
from app.settings import get_settings

client = TestClient(app)


def closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


@pytest.fixture
def refusing_database() -> Iterator[None]:
    url = make_url(get_settings().database_url).set(port=closed_port())
    engine = create_db_engine(url.render_as_string(hide_password=False))
    app.dependency_overrides[get_engine] = lambda: engine
    yield
    app.dependency_overrides.clear()
    engine.dispose()


def test_live_returns_ok() -> None:
    response = client.get("/healthz/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_live_ok_without_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        response = client.get("/healthz/live")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200


def test_ready_returns_ok_when_database_answers() -> None:
    response = client.get("/healthz/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.usefixtures("refusing_database")
def test_ready_returns_unavailable_when_database_refuses() -> None:
    started = time.monotonic()
    response = client.get("/healthz/ready")
    elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert elapsed < 5


@pytest.mark.usefixtures("refusing_database")
def test_unavailable_body_leaks_nothing() -> None:
    url = make_url(get_settings().database_url)

    body = client.get("/healthz/ready").text

    for secret in (url.host, url.username, url.password):
        assert secret
        assert secret not in body
    for word in ("Error", "Exception", "Traceback"):
        assert word not in body


@pytest.mark.usefixtures("refusing_database")
def test_ready_503_stays_plain_json() -> None:
    response = client.get("/healthz/ready")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "unavailable"}
