import configparser
import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, make_url
from sqlalchemy.exc import IntegrityError

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


BANK_TABLES = "5db30d28e759"
CASH_COLUMNS = "d546cee847e0"
TRANSACTIONS = "de44856f468e"


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

    # Down to the audit_log revision, the one before users.
    result = alembic_run("downgrade", "99b26f739028", database_url=empty_database_url)
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


def test_businesses_and_memberships_upgrade_downgrade_and_check(
    empty_database_url: str,
) -> None:
    result = alembic_run("upgrade", "head", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr

    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            columns = conn.exec_driver_sql(
                "SELECT table_name, column_name, data_type, is_nullable"
                " FROM information_schema.columns"
                " WHERE table_name IN ('businesses', 'memberships')"
            ).all()
            keys = conn.exec_driver_sql(
                "SELECT tc.table_name, tc.constraint_name, tc.constraint_type,"
                " kcu.column_name, ccu.table_name AS referred"
                " FROM information_schema.table_constraints tc"
                " JOIN information_schema.key_column_usage kcu"
                " USING (constraint_schema, constraint_name)"
                " LEFT JOIN information_schema.constraint_column_usage ccu"
                " ON tc.constraint_type = 'FOREIGN KEY'"
                " AND ccu.constraint_name = tc.constraint_name"
                " WHERE tc.table_name IN ('businesses', 'memberships')"
                " AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')"
            ).all()
            index = conn.exec_driver_sql(
                "SELECT indexdef FROM pg_indexes"
                " WHERE indexname = 'uq_memberships_owner_user_id'"
            ).scalar_one()
    finally:
        engine.dispose()

    assert {tuple(row) for row in columns} == {
        ("businesses", "id", "uuid", "NO"),
        ("businesses", "name", "text", "NO"),
        ("businesses", "province", "text", "NO"),
        ("businesses", "time_zone", "text", "NO"),
        ("businesses", "country", "text", "NO"),
        ("businesses", "currency", "text", "NO"),
        ("businesses", "created_at", "timestamp with time zone", "NO"),
        ("businesses", "updated_at", "timestamp with time zone", "NO"),
        ("memberships", "business_id", "uuid", "NO"),
        ("memberships", "user_id", "uuid", "NO"),
        ("memberships", "role", "text", "NO"),
        ("memberships", "created_at", "timestamp with time zone", "NO"),
    }
    assert {tuple(row) for row in keys} == {
        ("businesses", "pk_businesses", "PRIMARY KEY", "id", None),
        ("memberships", "pk_memberships", "PRIMARY KEY", "business_id", None),
        ("memberships", "pk_memberships", "PRIMARY KEY", "user_id", None),
        (
            "memberships",
            "fk_memberships_business_id_businesses",
            "FOREIGN KEY",
            "business_id",
            "businesses",
        ),
        (
            "memberships",
            "fk_memberships_user_id_users",
            "FOREIGN KEY",
            "user_id",
            "users",
        ),
    }
    assert index.startswith("CREATE UNIQUE INDEX uq_memberships_owner_user_id")
    assert "(user_id)" in index
    assert index.endswith("WHERE (role = 'owner'::text)")

    # To the users revision, not -1: later migrations sit on top of this one.
    result = alembic_run("downgrade", "07f1bcba78b6", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        tables = inspect(engine).get_table_names()
    finally:
        engine.dispose()
    assert "businesses" not in tables
    assert "memberships" not in tables
    assert "users" in tables

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


def test_bank_connections_and_accounts_upgrade_downgrade_and_check(
    empty_database_url: str,
) -> None:
    # To spec 12's revision, not head: spec 13 adds columns to bank_accounts on top.
    result = alembic_run("upgrade", BANK_TABLES, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr

    tables = ("bank_connections", "bank_accounts")
    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            columns = conn.exec_driver_sql(
                "SELECT table_name, column_name, data_type, is_nullable"
                " FROM information_schema.columns WHERE table_name = ANY(%s)",
                (list(tables),),
            ).all()
            keys = conn.exec_driver_sql(
                "SELECT tc.table_name, tc.constraint_name, tc.constraint_type,"
                " kcu.column_name, ccu.table_name AS referred"
                " FROM information_schema.table_constraints tc"
                " JOIN information_schema.key_column_usage kcu"
                " USING (constraint_schema, constraint_name)"
                " LEFT JOIN information_schema.constraint_column_usage ccu"
                " ON tc.constraint_type = 'FOREIGN KEY'"
                " AND ccu.constraint_name = tc.constraint_name"
                " WHERE tc.table_name = ANY(%s)"
                " AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')",
                (list(tables),),
            ).all()
            checks = (
                conn.exec_driver_sql(
                    "SELECT conname FROM pg_constraint"
                    " WHERE conrelid = 'bank_accounts'::regclass AND contype = 'c'"
                )
                .scalars()
                .all()
            )
    finally:
        engine.dispose()

    text_not_null = [
        ("bank_connections", c)
        for c in (
            "plaid_item_id",
            "plaid_institution_id",
            "institution_name",
            "access_token_ciphertext",
        )
    ] + [("bank_accounts", c) for c in ("plaid_account_id", "name", "type", "currency")]
    expected_columns = {
        *((t, c, "text", "NO") for t, c in text_not_null),
        ("bank_connections", "id", "uuid", "NO"),
        ("bank_connections", "business_id", "uuid", "NO"),
        ("bank_accounts", "id", "uuid", "NO"),
        ("bank_accounts", "business_id", "uuid", "NO"),
        ("bank_accounts", "connection_id", "uuid", "NO"),
        ("bank_accounts", "mask", "text", "YES"),
        ("bank_accounts", "balance_cents", "bigint", "YES"),
        *(
            (t, c, "timestamp with time zone", "NO")
            for t in tables
            for c in ("created_at", "updated_at")
        ),
    }
    assert {tuple(row) for row in columns} == expected_columns
    assert {tuple(row) for row in keys} == {
        ("bank_connections", "pk_bank_connections", "PRIMARY KEY", "id", None),
        (
            "bank_connections",
            "uq_bank_connections_plaid_item_id",
            "UNIQUE",
            "plaid_item_id",
            None,
        ),
        (
            "bank_connections",
            "uq_bank_connections_business_id_plaid_institution_id",
            "UNIQUE",
            "business_id",
            None,
        ),
        (
            "bank_connections",
            "uq_bank_connections_business_id_plaid_institution_id",
            "UNIQUE",
            "plaid_institution_id",
            None,
        ),
        ("bank_accounts", "pk_bank_accounts", "PRIMARY KEY", "id", None),
        (
            "bank_accounts",
            "uq_bank_accounts_plaid_account_id",
            "UNIQUE",
            "plaid_account_id",
            None,
        ),
        (
            "bank_accounts",
            "fk_bank_accounts_connection_id_bank_connections",
            "FOREIGN KEY",
            "connection_id",
            "bank_connections",
        ),
    }
    assert "ck_bank_accounts_type" in checks

    result = alembic_run("downgrade", "-1", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        remaining = inspect(engine).get_table_names()
    finally:
        engine.dispose()
    assert "bank_connections" not in remaining
    assert "bank_accounts" not in remaining
    assert "businesses" in remaining

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


def test_bank_accounts_cash_columns_upgrade_backfill_downgrade_and_check(
    empty_database_url: str,
) -> None:
    result = alembic_run("upgrade", BANK_TABLES, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr

    business_a, business_b = uuid.uuid4(), uuid.uuid4()
    seeded = [
        # (business, name, type, currency, balance_cents)
        (business_a, "Low checking", "checking", "CAD", 5000),
        (business_a, "High checking", "checking", "CAD", 9000),
        (business_a, "Reserve", "savings", "CAD", 20000),
        (business_a, "Visa", "credit_card", "CAD", 800),
        (business_b, "US checking", "checking", "USD", 7000),
    ]
    engine = create_engine(empty_database_url)
    try:
        with engine.begin() as conn:
            for business in (business_a, business_b):
                conn.exec_driver_sql(
                    "INSERT INTO bank_connections (id, business_id, plaid_item_id,"
                    " plaid_institution_id, institution_name, access_token_ciphertext)"
                    " VALUES (%s, %s, %s, 'ins_42', 'Bank', 'x')",
                    (business, business, f"item-{business}"),
                )
            for business, name, kind, currency, cents in seeded:
                conn.exec_driver_sql(
                    "INSERT INTO bank_accounts (id, business_id, connection_id,"
                    " plaid_account_id, name, type, currency, balance_cents)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        uuid.uuid4(),
                        business,
                        business,
                        f"acc-{name}",
                        name,
                        kind,
                        currency,
                        cents,
                    ),
                )
    finally:
        engine.dispose()

    # To spec 13's revision, not head: spec 14 adds bank_transactions on top.
    result = alembic_run("upgrade", CASH_COLUMNS, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr

    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            columns = conn.exec_driver_sql(
                "SELECT column_name, data_type, is_nullable, column_default"
                " FROM information_schema.columns WHERE table_name = 'bank_accounts'"
                " AND column_name IN ('included', 'is_primary', 'available_cents')"
            ).all()
            checks = set(
                conn.exec_driver_sql(
                    "SELECT conname FROM pg_constraint"
                    " WHERE conrelid = 'bank_accounts'::regclass AND contype = 'c'"
                ).scalars()
            )
            index = conn.exec_driver_sql(
                "SELECT indexdef FROM pg_indexes"
                " WHERE indexname = 'uq_bank_accounts_primary_business_id'"
            ).scalar_one()
            backfilled = {
                name: (included, primary, available)
                for name, included, primary, available in conn.exec_driver_sql(
                    "SELECT name, included, is_primary, available_cents FROM bank_accounts"
                )
            }
    finally:
        engine.dispose()

    assert {(c, t, n) for c, t, n, _ in columns} == {
        ("included", "boolean", "NO"),
        ("is_primary", "boolean", "NO"),
        ("available_cents", "bigint", "YES"),
    }
    defaults = {c: d for c, _, _, d in columns}
    assert defaults["is_primary"] == "false"
    assert {
        "ck_bank_accounts_included_cash",
        "ck_bank_accounts_primary_included",
    } <= checks
    assert index.startswith("CREATE UNIQUE INDEX uq_bank_accounts_primary_business_id")
    assert "(business_id)" in index
    assert index.endswith("WHERE is_primary")
    assert backfilled == {
        "Low checking": (True, False, None),
        "High checking": (True, True, None),
        "Reserve": (False, False, None),
        "Visa": (False, False, None),
        "US checking": (False, False, None),
    }

    result = alembic_run("downgrade", "-1", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        remaining = {c["name"] for c in inspect(engine).get_columns("bank_accounts")}
    finally:
        engine.dispose()
    assert not {"included", "is_primary", "available_cents"} & remaining

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


def test_bank_transactions_upgrade_downgrade_and_check(empty_database_url: str) -> None:
    result = alembic_run("upgrade", TRANSACTIONS, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr

    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            columns = conn.exec_driver_sql(
                "SELECT column_name, data_type, is_nullable"
                " FROM information_schema.columns WHERE table_name = 'bank_transactions'"
            ).all()
            cursor = conn.exec_driver_sql(
                "SELECT data_type, is_nullable FROM information_schema.columns"
                " WHERE table_name = 'bank_connections'"
                " AND column_name = 'transactions_cursor'"
            ).one()
            constraints = {
                (name, kind, definition)
                for name, kind, definition in conn.exec_driver_sql(
                    "SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint"
                    " WHERE conrelid = 'bank_transactions'::regclass"
                )
            }
    finally:
        engine.dispose()

    assert {(c, t, n) for c, t, n in columns} == {
        ("id", "uuid", "NO"),
        ("business_id", "uuid", "NO"),
        ("account_id", "uuid", "NO"),
        ("plaid_transaction_id", "text", "NO"),
        ("amount_cents", "bigint", "NO"),
        ("currency", "text", "NO"),
        ("date", "date", "NO"),
        ("pending", "boolean", "NO"),
        ("description", "text", "NO"),
        ("counterparty", "text", "YES"),
        ("category", "text", "YES"),
        ("category_detailed", "text", "YES"),
        ("created_at", "timestamp with time zone", "NO"),
        ("updated_at", "timestamp with time zone", "NO"),
    }
    assert tuple(cursor) == ("text", "YES")
    assert ("pk_bank_transactions", "p", "PRIMARY KEY (id)") in constraints
    assert (
        "uq_bank_transactions_plaid_transaction_id",
        "u",
        "UNIQUE (plaid_transaction_id)",
    ) in constraints
    assert (
        "fk_bank_transactions_account_id_bank_accounts",
        "f",
        "FOREIGN KEY (account_id) REFERENCES bank_accounts(id)",
    ) in constraints

    result = alembic_run("downgrade", "-1", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        remaining = {c["name"] for c in inspect(engine).get_columns("bank_connections")}
    finally:
        engine.dispose()
    assert "bank_transactions" not in tables
    assert "transactions_cursor" not in remaining

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


def test_nightly_state_upgrade_downgrade_and_check(empty_database_url: str) -> None:
    """Spec 15 C32: the nightly sync state on bank_connections (door 1)."""
    result = alembic_run("upgrade", TRANSACTIONS, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO bank_connections (id, business_id, plaid_item_id,"
                " plaid_institution_id, institution_name, access_token_ciphertext)"
                " VALUES (gen_random_uuid(), gen_random_uuid(), 'item-existing',"
                " 'ins_1', 'TD Canada Trust', 'ciphertext')"
            )
    finally:
        engine.dispose()

    result = alembic_run("upgrade", "head", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            columns = {
                name: (kind, nullable)
                for name, kind, nullable in conn.exec_driver_sql(
                    "SELECT column_name, data_type, is_nullable"
                    " FROM information_schema.columns"
                    " WHERE table_name = 'bank_connections'"
                )
            }
            existing = conn.exec_driver_sql(
                "SELECT nightly_synced_on, nightly_attempts, next_nightly_attempt_at,"
                " failed_nights FROM bank_connections"
            ).one()
        with pytest.raises(IntegrityError) as excinfo, engine.begin() as conn:
            conn.exec_driver_sql("UPDATE bank_connections SET failed_nights = -1")
    finally:
        engine.dispose()

    assert columns["nightly_synced_on"] == ("date", "YES")
    assert columns["nightly_attempts"] == ("integer", "NO")
    assert columns["next_nightly_attempt_at"] == ("timestamp with time zone", "YES")
    assert columns["failed_nights"] == ("integer", "NO")
    assert tuple(existing) == (None, 0, None, 0)
    assert "ck_bank_connections_failed_nights" in str(excinfo.value)

    result = alembic_run("downgrade", TRANSACTIONS, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        remaining = {c["name"] for c in inspect(engine).get_columns("bank_connections")}
        checks = {
            c["name"] for c in inspect(engine).get_check_constraints("bank_connections")
        }
    finally:
        engine.dispose()
    assert remaining.isdisjoint(
        {
            "nightly_synced_on",
            "nightly_attempts",
            "next_nightly_attempt_at",
            "failed_nights",
        }
    )
    assert "ck_bank_connections_failed_nights" not in checks

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


NIGHTLY_STATE = "c183e89c1a74"


def test_transaction_labels_upgrade_downgrade_and_check(
    empty_database_url: str,
) -> None:
    """Spec 16 C28: existing transactions become `normal` with no link (doors 1, 2)."""
    result = alembic_run("upgrade", NIGHTLY_STATE, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO bank_connections (id, business_id, plaid_item_id,"
                " plaid_institution_id, institution_name, access_token_ciphertext)"
                " VALUES ('00000000-0000-0000-0000-00000000c001',"
                " '00000000-0000-0000-0000-00000000b001', 'item-existing', 'ins_1',"
                " 'TD Canada Trust', 'ciphertext')"
            )
            conn.exec_driver_sql(
                "INSERT INTO bank_accounts (id, business_id, connection_id,"
                " plaid_account_id, name, type, currency, included)"
                " VALUES ('00000000-0000-0000-0000-00000000a001',"
                " '00000000-0000-0000-0000-00000000b001',"
                " '00000000-0000-0000-0000-00000000c001', 'acc-existing', 'Savings',"
                " 'savings', 'CAD', false)"
            )
            conn.exec_driver_sql(
                "INSERT INTO bank_transactions (id, business_id, account_id,"
                " plaid_transaction_id, amount_cents, currency, date, pending,"
                " description) VALUES (gen_random_uuid(),"
                " '00000000-0000-0000-0000-00000000b001',"
                " '00000000-0000-0000-0000-00000000a001', 'tx-existing', -1000000,"
                " 'CAD', '2026-09-14', false, 'Transfer')"
            )
    finally:
        engine.dispose()

    result = alembic_run("upgrade", "head", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            existing = conn.exec_driver_sql(
                "SELECT label, linked_transaction_id FROM bank_transactions"
            ).one()
    finally:
        engine.dispose()
    assert tuple(existing) == ("normal", None)

    result = alembic_run("downgrade", NIGHTLY_STATE, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        remaining = {
            c["name"] for c in inspect(engine).get_columns("bank_transactions")
        }
    finally:
        engine.dispose()
    assert remaining.isdisjoint({"label", "linked_transaction_id"})

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


TRANSACTION_LABELS = "b8f2b4520a41"


def test_connection_settings_upgrade_downgrade_and_check(
    empty_database_url: str,
) -> None:
    """Spec 17 C3: `login_required` and `last_synced_at` on bank_connections."""
    result = alembic_run("upgrade", TRANSACTION_LABELS, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO bank_connections (id, business_id, plaid_item_id,"
                " plaid_institution_id, institution_name, access_token_ciphertext)"
                " VALUES (gen_random_uuid(), gen_random_uuid(), 'item-existing',"
                " 'ins_1', 'TD Canada Trust', 'ciphertext')"
            )
    finally:
        engine.dispose()

    result = alembic_run("upgrade", "head", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            columns = {
                name: (kind, nullable)
                for name, kind, nullable in conn.exec_driver_sql(
                    "SELECT column_name, data_type, is_nullable"
                    " FROM information_schema.columns"
                    " WHERE table_name = 'bank_connections'"
                )
            }
            existing = conn.exec_driver_sql(
                "SELECT login_required, last_synced_at FROM bank_connections"
            ).one()
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.exec_driver_sql("UPDATE bank_connections SET login_required = NULL")
    finally:
        engine.dispose()

    assert columns["login_required"] == ("boolean", "NO")
    assert columns["last_synced_at"] == ("timestamp with time zone", "YES")
    assert tuple(existing) == (False, None)

    result = alembic_run(
        "downgrade", TRANSACTION_LABELS, database_url=empty_database_url
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        remaining = {c["name"] for c in inspect(engine).get_columns("bank_connections")}
    finally:
        engine.dispose()
    assert remaining.isdisjoint({"login_required", "last_synced_at"})

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


CONNECTION_SETTINGS = "bf5cd9dfe9df"


def test_recurring_patterns_upgrade_downgrade_and_check(
    empty_database_url: str,
) -> None:
    """Spec 19 C27: the `recurring_patterns` table, and back."""
    result = alembic_run(
        "upgrade", CONNECTION_SETTINGS, database_url=empty_database_url
    )
    assert result.returncode == 0, result.stderr

    result = alembic_run("upgrade", "head", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as conn:
            columns = {
                name: (kind, udt)
                for name, kind, udt in conn.exec_driver_sql(
                    "SELECT column_name, data_type, udt_name"
                    " FROM information_schema.columns"
                    " WHERE table_name = 'recurring_patterns'"
                )
            }
    finally:
        engine.dispose()
    assert columns["transaction_ids"] == ("ARRAY", "_uuid")
    assert columns["confidence"][0] == "smallint"

    result = alembic_run(
        "downgrade", CONNECTION_SETTINGS, database_url=empty_database_url
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        assert "recurring_patterns" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


RECURRING_PATTERNS = "94a2c06f7ede"


def test_expected_payments_upgrade_downgrade_and_check(
    empty_database_url: str,
) -> None:
    """Spec 20 C15: `expected_payments` and `expected_payment_matches`, and back."""
    tables = {"expected_payments", "expected_payment_matches"}
    result = alembic_run("upgrade", RECURRING_PATTERNS, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr

    result = alembic_run("upgrade", "head", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        assert tables <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    result = alembic_run(
        "downgrade", RECURRING_PATTERNS, database_url=empty_database_url
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        assert not tables & set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr


EXPECTED_PAYMENTS = "0877a711bdf1"


def test_forecast_snapshots_upgrade_downgrade_and_check(
    empty_database_url: str,
) -> None:
    """Spec 21 C32: the 3 snapshot tables, their constraints and cascade, and back."""
    tables = {"forecast_snapshots", "forecast_weeks", "forecast_items"}
    result = alembic_run("upgrade", EXPECTED_PAYMENTS, database_url=empty_database_url)
    assert result.returncode == 0, result.stderr

    result = alembic_run("upgrade", "head", database_url=empty_database_url)
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    snapshot = (
        "INSERT INTO forecast_snapshots (id, business_id, inputs_sha256, strategy,"
        " as_of, currency, opening_balance_cents, last_computed_at)"
        " VALUES (%s, %s, %s, 'recurring_pattern', '2026-09-26', 'CAD', 0, now())"
    )
    week = (
        "INSERT INTO forecast_weeks (snapshot_id, number, starts_on, end_balance_cents,"
        " low_cents, high_cents, money_in_cents, money_out_cents)"
        " VALUES (%s, %s, '2026-09-28', 0, 0, 0, 0, 0)"
    )
    item = (
        "INSERT INTO forecast_items (id, snapshot_id, week, date, account_id,"
        " amount_cents, currency, source) VALUES (%s, %s, 1, '2026-09-28', %s, %s,"
        " 'CAD', %s)"
    )
    business, snapshot_id = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        assert tables <= set(inspect(engine).get_table_names())
        with engine.begin() as conn:
            conn.exec_driver_sql(snapshot, (snapshot_id, business, "a" * 64))
            conn.exec_driver_sql(week, (snapshot_id, 1))
            conn.exec_driver_sql(
                item,
                (str(uuid.uuid4()), snapshot_id, str(uuid.uuid4()), -5, "estimate"),
            )
        rejected = [
            (snapshot, (str(uuid.uuid4()), business, "a" * 64)),
            (week, (snapshot_id, 0)),
            (week, (snapshot_id, 14)),
            (item, (str(uuid.uuid4()), snapshot_id, str(uuid.uuid4()), -5, "other")),
            (item, (str(uuid.uuid4()), snapshot_id, str(uuid.uuid4()), 0, "estimate")),
        ]
        for statement, values in rejected:
            with pytest.raises(IntegrityError), engine.begin() as conn:
                conn.exec_driver_sql(statement, values)
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "DELETE FROM forecast_snapshots WHERE id = %s", (snapshot_id,)
            )
            for table in ("forecast_weeks", "forecast_items"):
                count = conn.exec_driver_sql(f"SELECT count(*) FROM {table}").scalar()
                assert count == 0, table
    finally:
        engine.dispose()

    result = alembic_run(
        "downgrade", EXPECTED_PAYMENTS, database_url=empty_database_url
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(empty_database_url)
    try:
        assert not tables & set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    for args in (("upgrade", "head"), ("check",)):
        result = alembic_run(*args, database_url=empty_database_url)
        assert result.returncode == 0, result.stdout + result.stderr
