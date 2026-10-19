"""Spec 17b: `provider` accepts `yodlee`, and the downgrade refuses while one exists."""

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError, InternalError, ProgrammingError

from tests.test_bank_provider_migration import (
    alembic,
    database_url,  # noqa: F401  (pytest fixture)
    engine,  # noqa: F401  (pytest fixture)
    insert_connection,
)

PREVIOUS = "8cbe90de5769"
REVISION = "c4ab8ce7a820"


def test_provider_check_accepts_yodlee(database_url: str, engine: Engine) -> None:  # noqa: F811
    alembic("upgrade", "head", database_url=database_url)

    insert_connection(engine, item="a", institution="i", provider="plaid")
    insert_connection(engine, item="b", institution="i", provider="yodlee")
    with pytest.raises(IntegrityError, match="ck_bank_connections_provider"):
        insert_connection(engine, item="c", institution="i", provider="other")


def test_downgrade_refuses_with_yodlee_rows(database_url: str, engine: Engine) -> None:  # noqa: F811
    alembic("upgrade", REVISION, database_url=database_url)
    insert_connection(engine, item="b", institution="i", provider="yodlee")

    with pytest.raises(AssertionError, match="ck_bank_connections_provider"):
        alembic("downgrade", PREVIOUS, database_url=database_url)

    # Nothing was deleted, and the constraint is still the widened one.
    with engine.connect() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT count(*) FROM bank_connections WHERE provider = 'yodlee'"
            ).scalar_one()
            == 1
        )


def test_downgrade_restores_plaid_only(database_url: str, engine: Engine) -> None:  # noqa: F811
    alembic("upgrade", REVISION, database_url=database_url)
    insert_connection(engine, item="a", institution="i", provider="plaid")

    alembic("downgrade", PREVIOUS, database_url=database_url)

    with pytest.raises((IntegrityError, InternalError, ProgrammingError)):
        insert_connection(engine, item="b", institution="i", provider="yodlee")
