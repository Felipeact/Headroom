"""Spec 17a S1: the provider column and the renamed provider ID columns (C1-C4)."""

import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect, make_url, text
from sqlalchemy.exc import IntegrityError

from app.settings import get_settings

CORE = Path(__file__).resolve().parents[1]
BEFORE = "e31b0c7a5d42"
REVISION = "86276e8fa7aa"


def alembic(*args: str, database_url: str) -> None:
    result = subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=CORE,
        env={**os.environ, "DATABASE_URL": database_url},
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def database_url() -> Iterator[str]:
    name = f"headroom_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(get_settings().database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    url = make_url(get_settings().database_url).set(database=name)
    yield url.render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    admin.dispose()


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


def insert_connection(
    engine: Engine,
    *,
    item: str,
    institution: str,
    provider: str | None = None,
    business_id: uuid.UUID | None = None,
) -> uuid.UUID:
    connection_id = uuid.uuid4()
    names = "provider_item_id, provider_institution_id"
    if provider is None:
        names = "plaid_item_id, plaid_institution_id"
    columns = f"id, business_id, {names}, institution_name, access_token_ciphertext"
    values = ":id, :business_id, :item, :institution, 'Bank', 'ciphertext'"
    if provider is not None:
        columns += ", provider"
        values += ", :provider"
    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO bank_connections ({columns}) VALUES ({values})"),
            {
                "id": connection_id,
                "business_id": business_id or uuid.uuid4(),
                "item": item,
                "institution": institution,
                "provider": provider,
            },
        )
    return connection_id


def seed_plaid_rows(engine: Engine) -> uuid.UUID:
    """A pre-migration Plaid connection with one account and one transaction."""
    connection_id = insert_connection(engine, item="item-1", institution="ins_1")
    account_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO bank_accounts (id, business_id, connection_id,"
                " plaid_account_id, name, type, currency, included)"
                " VALUES (:id, :business_id, :connection_id, 'acc-1', 'Chequing',"
                " 'checking', 'CAD', true)"
            ),
            {
                "id": account_id,
                "business_id": uuid.uuid4(),
                "connection_id": connection_id,
            },
        )
        conn.execute(
            text(
                "INSERT INTO bank_transactions (id, business_id, account_id,"
                " plaid_transaction_id, amount_cents, currency, date, pending, description)"
                " VALUES (:id, :business_id, :account_id, 'tx-1', -100, 'CAD',"
                " '2026-10-01', false, 'Rent')"
            ),
            {"id": uuid.uuid4(), "business_id": uuid.uuid4(), "account_id": account_id},
        )
    return connection_id


def columns(engine: Engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_existing_rows_become_plaid(database_url: str, engine: Engine) -> None:
    alembic("upgrade", BEFORE, database_url=database_url)
    connection_id = seed_plaid_rows(engine)

    alembic("upgrade", REVISION, database_url=database_url)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT provider, provider_item_id, provider_institution_id"
                " FROM bank_connections WHERE id = :id"
            ),
            {"id": connection_id},
        ).one()
        assert tuple(row) == ("plaid", "item-1", "ins_1")
        assert (
            conn.execute(
                text("SELECT provider_account_id FROM bank_accounts")
            ).scalar_one()
            == "acc-1"
        )
        assert (
            conn.execute(
                text("SELECT provider_transaction_id FROM bank_transactions")
            ).scalar_one()
            == "tx-1"
        )
    assert {"provider", "provider_item_id", "provider_institution_id"} <= columns(
        engine, "bank_connections"
    )
    assert not {
        c for c in columns(engine, "bank_connections") if c.startswith("plaid_")
    }
    assert "provider_account_id" in columns(engine, "bank_accounts")
    assert "provider_transaction_id" in columns(engine, "bank_transactions")


def test_downgrade_restores_plaid_names(database_url: str, engine: Engine) -> None:
    alembic("upgrade", BEFORE, database_url=database_url)
    seed_plaid_rows(engine)
    alembic("upgrade", REVISION, database_url=database_url)

    alembic("downgrade", BEFORE, database_url=database_url)

    assert {"plaid_item_id", "plaid_institution_id"} <= columns(
        engine, "bank_connections"
    )
    assert "provider" not in columns(engine, "bank_connections")
    assert "plaid_account_id" in columns(engine, "bank_accounts")
    assert "plaid_transaction_id" in columns(engine, "bank_transactions")
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT plaid_item_id FROM bank_connections")
            ).scalar_one()
            == "item-1"
        )
        assert (
            conn.execute(text("SELECT count(*) FROM bank_transactions")).scalar_one()
            == 1
        )


def test_provider_check_constraint(database_url: str, engine: Engine) -> None:
    alembic("upgrade", "head", database_url=database_url)

    insert_connection(engine, item="a", institution="i", provider="plaid")
    insert_connection(engine, item="b", institution="i", provider="flinks")
    with pytest.raises(IntegrityError, match="ck_bank_connections_provider"):
        insert_connection(engine, item="c", institution="i", provider="other")


def test_provider_uniques(database_url: str, engine: Engine) -> None:
    alembic("upgrade", "head", database_url=database_url)
    business_id = uuid.uuid4()

    insert_connection(
        engine,
        item="same",
        institution="ins_9",
        provider="plaid",
        business_id=business_id,
    )
    # The same institution and item IDs under the other provider are a different login.
    insert_connection(
        engine,
        item="same",
        institution="ins_9",
        provider="flinks",
        business_id=business_id,
    )
    with pytest.raises(
        IntegrityError, match="uq_bank_connections_provider_provider_item_id"
    ):
        insert_connection(
            engine, item="same", institution="ins_other", provider="plaid"
        )
    with pytest.raises(
        IntegrityError, match="uq_bank_connections_business_provider_institution"
    ):
        insert_connection(
            engine,
            item="new",
            institution="ins_9",
            provider="plaid",
            business_id=business_id,
        )
