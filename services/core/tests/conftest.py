import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

# A key pair for this test session only. Its public half is CLERK_JWT_KEY for every test
# (process env beats .env.local), so tests sign their own tokens and never call Clerk.
TEST_PRIVATE_KEY: RSAPrivateKey = rsa.generate_private_key(
    public_exponent=65537, key_size=2048
)
TEST_PUBLIC_PEM = (
    TEST_PRIVATE_KEY.public_key()
    .public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    .decode()
)
os.environ["CLERK_JWT_KEY"] = TEST_PUBLIC_PEM
os.environ["CLERK_AUTHORIZED_PARTIES"] = ""
# Empty means no webhook URL (spec 14): link tokens in tests never carry the URL a
# developer keeps in .env.local, because process env beats the file.
os.environ["PLAID_WEBHOOK_URL"] = ""
# Unit tests use a fake Plaid client, so these only have to satisfy Settings. setdefault:
# the `plaid_sandbox` proofs export the real sandbox keys first (proofs.sh), and keep them.
os.environ.setdefault("PLAID_CLIENT_ID", "test-client-id")
os.environ.setdefault("PLAID_SECRET", "test-secret")
os.environ.setdefault("PLAID_ENV", "sandbox")
os.environ.setdefault("TOKEN_ENCRYPTION_KEYS", Fernet.generate_key().decode())


CORE = Path(__file__).resolve().parents[1]


def _database_at_head() -> Iterator[str]:
    """Create a database at Alembic head, point the app at it, and drop it afterwards.

    Tests that reach a module's tables go through the app's own settings, so this points
    DATABASE_URL at the new database (and drops the cached engine) instead of trusting
    whatever state the configured database is in. Yields the database URL.
    """
    from sqlalchemy import create_engine, make_url

    from app.db import get_engine, get_sessionmaker
    from app.settings import get_settings

    get_settings.cache_clear()
    base_url = get_settings().database_url
    name = f"headroom_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    url = make_url(base_url).set(database=name).render_as_string(hide_password=False)
    upgrade = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=CORE,
        env={**os.environ, "DATABASE_URL": url},
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert upgrade.returncode == 0, upgrade.stderr

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()
    yield url

    get_engine().dispose()
    if previous is None:
        del os.environ["DATABASE_URL"]
    else:
        os.environ["DATABASE_URL"] = previous
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()
    with admin.connect() as conn:
        conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    admin.dispose()


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[None]:
    """A fresh database at Alembic head, used by the app for the whole session."""
    for _ in _database_at_head():
        yield


@pytest.fixture(scope="module")
def isolated_database() -> Iterator[str]:
    """A database of the test module's own, for code that reads every business's rows.

    The nightly sync job (spec 15) syncs every connection in the database, so its tests
    cannot share the session database with other tests' connections. Yields its URL.
    """
    yield from _database_at_head()
