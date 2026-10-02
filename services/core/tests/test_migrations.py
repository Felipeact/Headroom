import configparser
import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, make_url

from app.settings import get_settings

CORE = Path(__file__).resolve().parents[1]


def alembic(command: str, database_url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        ["uv", "run", "alembic", command, *(["head"] if command == "upgrade" else [])],
        cwd=CORE,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture
def empty_database_url() -> Iterator[str]:
    name = f"headroom_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(get_settings().database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    url = make_url(get_settings().database_url).set(database=name)
    yield url.render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    admin.dispose()


def test_upgrade_head_on_empty_database(empty_database_url: str) -> None:
    upgrade = alembic("upgrade", empty_database_url)
    assert upgrade.returncode == 0, upgrade.stderr

    current = alembic("current", empty_database_url)
    assert current.returncode == 0, current.stderr

    again = alembic("upgrade", empty_database_url)
    assert again.returncode == 0, again.stderr


def test_upgrade_targets_database_url(empty_database_url: str) -> None:
    upgrade = alembic("upgrade", empty_database_url)
    assert upgrade.returncode == 0, upgrade.stderr

    engine = create_engine(empty_database_url)
    try:
        tables = inspect(engine).get_table_names()
    finally:
        engine.dispose()
    assert "alembic_version" in tables


def test_alembic_ini_has_no_url() -> None:
    ini = configparser.RawConfigParser()
    ini.read(CORE / "alembic.ini")

    assert ini.get("alembic", "sqlalchemy.url", fallback="").strip() == ""


def alembic_run(*args: str, database_url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=CORE,
        env={**os.environ, "DATABASE_URL": database_url},
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_audit_log_upgrade_downgrade_and_check(empty_database_url: str) -> None:
    # audit_log is the first revision, so downgrading to base undoes it.
    for args in (("upgrade", "head"), ("downgrade", "base")):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stderr

    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            function = conn.exec_driver_sql(
                "SELECT to_regproc('audit_log_append_only')"
            ).scalar()
        tables = inspect(engine).get_table_names()
    finally:
        engine.dispose()
    assert "audit_log" not in tables
    assert function is None

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


def test_users_table_upgrade_downgrade_and_check(empty_database_url: str) -> None:
    result = alembic_run("upgrade", "head", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr

    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            columns = conn.exec_driver_sql(
                "SELECT column_name, data_type, is_nullable"
                " FROM information_schema.columns WHERE table_name = 'users'"
            ).all()
            constraints = conn.exec_driver_sql(
                "SELECT tc.constraint_name, tc.constraint_type, kcu.column_name"
                " FROM information_schema.table_constraints tc"
                " JOIN information_schema.key_column_usage kcu"
                " USING (constraint_schema, constraint_name)"
                " WHERE tc.table_name = 'users'"
            ).all()
    finally:
        engine.dispose()

    assert {(name, kind, nullable) for name, kind, nullable in columns} == {
        ("id", "uuid", "NO"),
        ("clerk_user_id", "text", "NO"),
        ("created_at", "timestamp with time zone", "NO"),
    }
    assert set(constraints) == {
        ("pk_users", "PRIMARY KEY", "id"),
        ("uq_users_clerk_user_id", "UNIQUE", "clerk_user_id"),
    }

    result = alembic_run("downgrade", "-1", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        tables = inspect(engine).get_table_names()
    finally:
        engine.dispose()
    assert "users" not in tables
    assert "audit_log" in tables

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr
