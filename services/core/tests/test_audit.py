import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, create_engine, func, make_url, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.audit import AuditLog
from app.settings import get_settings
from tests.test_migrations import alembic

SANDBOX_TOKEN = "access-sandbox-1b4e28ba-2fa1-11d2-883f-0016e5f2c3a1"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    name = f"headroom_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(get_settings().database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    url = make_url(get_settings().database_url).set(database=name)
    url_text = url.render_as_string(hide_password=False)
    upgrade = alembic("upgrade", url_text)
    assert upgrade.returncode == 0, upgrade.stderr
    engine = create_engine(url_text)
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    admin.dispose()


def count(engine: Engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(AuditLog)) or 0


def insert_entry(engine: Engine) -> int:
    with Session(engine) as session:
        audit.record(
            session, action="thing.created", business_id=None, actor_user_id=None
        )
        session.commit()
        entry_id = session.scalar(select(func.max(AuditLog.id)))
    assert entry_id is not None
    return entry_id


def test_record_commits_with_caller(engine: Engine) -> None:
    business_id = uuid.uuid4()
    before = count(engine)
    with Session(engine) as session:
        audit.record(
            session,
            action="bank_connection.created",
            business_id=business_id,
            actor_user_id="user_test",
            target_type="bank_connection",
            target_id="42",
            details={"institution": "Sandbox Bank"},
        )
        session.commit()

    assert count(engine) == before + 1
    with Session(engine) as session:
        row = session.scalars(
            select(AuditLog).where(AuditLog.business_id == business_id)
        ).one()
    assert row.action == "bank_connection.created"
    assert row.business_id == business_id
    assert row.actor_user_id == "user_test"
    assert row.target_type == "bank_connection"
    assert row.target_id == "42"
    assert row.details == {"institution": "Sandbox Bank"}
    assert abs(row.occurred_at - datetime.now(UTC)) < timedelta(seconds=5)


def test_record_rolls_back_with_caller(engine: Engine) -> None:
    before = count(engine)
    with Session(engine) as session:
        audit.record(
            session, action="thing.created", business_id=None, actor_user_id=None
        )
        session.rollback()

    assert count(engine) == before


def test_update_is_rejected(engine: Engine) -> None:
    entry_id = insert_entry(engine)

    with engine.connect() as conn, pytest.raises(DBAPIError):
        conn.execute(
            text("UPDATE audit_log SET action = 'x.y' WHERE id = :id"), {"id": entry_id}
        )

    with engine.connect() as conn:
        action = conn.execute(
            text("SELECT action FROM audit_log WHERE id = :id"), {"id": entry_id}
        ).scalar_one()
    assert action == "thing.created"


def test_delete_is_rejected(engine: Engine) -> None:
    entry_id = insert_entry(engine)
    before = count(engine)

    with engine.connect() as conn, pytest.raises(DBAPIError):
        conn.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": entry_id})

    assert count(engine) == before


def test_truncate_is_rejected(engine: Engine) -> None:
    insert_entry(engine)
    before = count(engine)

    with engine.connect() as conn, pytest.raises(DBAPIError):
        conn.execute(text("TRUNCATE audit_log"))

    assert count(engine) == before


@pytest.mark.parametrize(
    "action",
    [
        "BankConnected",
        "bank_connection",
        "bank-connection.created",
        "bank_connection.created.extra",
        ".created",
    ],
)
def test_invalid_action_raises_value_error(engine: Engine, action: str) -> None:
    with Session(engine) as session:
        with pytest.raises(ValueError):
            audit.record(session, action=action, business_id=None, actor_user_id=None)
        assert not session.new


def test_check_constraint_rejects_invalid_action(engine: Engine) -> None:
    with engine.connect() as conn, pytest.raises(IntegrityError) as raised:
        conn.execute(text("INSERT INTO audit_log (action) VALUES ('BankConnected')"))

    assert "ck_audit_log_action_format" in str(raised.value)


def test_details_redacted(engine: Engine) -> None:
    business_id = uuid.uuid4()
    with Session(engine) as session:
        audit.record(
            session,
            action="bank_connection.created",
            business_id=business_id,
            actor_user_id=None,
            details={
                "plaid": {"access_token": SANDBOX_TOKEN},
                "items": [{"password": "pw"}],
                "institution": "Sandbox Bank",
            },
        )
        session.commit()
        stored = session.scalars(
            select(AuditLog.details).where(AuditLog.business_id == business_id)
        ).one()

    assert stored == {
        "plaid": {"access_token": "[REDACTED]"},
        "items": [{"password": "[REDACTED]"}],
        "institution": "Sandbox Bank",
    }
