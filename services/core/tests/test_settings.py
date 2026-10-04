from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.settings import Settings, get_settings

ENV_URL = "postgresql+psycopg://env-host:5432/env_db"
FILE_URL = "postgresql+psycopg://file-host:5432/file_db"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_process_env_overrides_env_file(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated / ".env.local").write_text(f"DATABASE_URL={FILE_URL}\n")
    monkeypatch.setenv("DATABASE_URL", ENV_URL)

    assert get_settings().database_url == ENV_URL


def test_env_file_used_when_process_env_absent(isolated: Path) -> None:
    (isolated / ".env.local").write_text(f"DATABASE_URL={FILE_URL}\n")

    assert get_settings().database_url == FILE_URL


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://h/d",
        "postgres://h/d",
        "postgresql+psycopg2://h/d",
        "sqlite:///headroom.db",
    ],
)
def test_rejects_non_psycopg_scheme(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", url)

    with pytest.raises(ValidationError):
        Settings()


def test_missing_database_url_raises() -> None:
    with pytest.raises(ValidationError):
        Settings()


def test_clerk_jwt_key_required(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", ENV_URL)
    monkeypatch.delenv("CLERK_JWT_KEY", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert "clerk_jwt_key" in str(excinfo.value)


@pytest.mark.parametrize(
    ("raw", "parsed"),
    [
        ("http://a.test, https://b.test", ["http://a.test", "https://b.test"]),
        (None, []),
    ],
    ids=["comma_list", "unset"],
)
def test_clerk_authorized_parties_parse(
    raw: str | None, parsed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", ENV_URL)
    if raw is None:
        monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)
    else:
        monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", raw)

    assert Settings().clerk_authorized_parties == parsed


# Spec 12: Plaid and token encryption settings


@pytest.fixture
def plaid_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setenv("DATABASE_URL", ENV_URL)
    monkeypatch.setenv("PLAID_CLIENT_ID", "client")
    monkeypatch.setenv("PLAID_SECRET", "secret")
    monkeypatch.setenv("PLAID_ENV", "sandbox")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEYS", Fernet.generate_key().decode())
    return monkeypatch


@pytest.mark.parametrize(
    "raw",
    [None, "", "not-a-key", "VALID,not-a-key"],
    ids=["unset", "empty", "not_a_key", "one_bad_key"],
)
def test_token_encryption_keys_rejected(
    raw: str | None, plaid_env: pytest.MonkeyPatch
) -> None:
    if raw is None:
        plaid_env.delenv("TOKEN_ENCRYPTION_KEYS")
    else:
        valid = Fernet.generate_key().decode()
        plaid_env.setenv("TOKEN_ENCRYPTION_KEYS", raw.replace("VALID", valid))

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert "token_encryption_keys" in str(excinfo.value)


def test_token_encryption_keys_two_keys_in_order(plaid_env: pytest.MonkeyPatch) -> None:
    new, old = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    plaid_env.setenv("TOKEN_ENCRYPTION_KEYS", f"{new}, {old}")

    assert Settings().token_encryption_keys == [new, old]


@pytest.mark.parametrize("name", ["PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ENV"])
def test_plaid_settings_required(name: str, plaid_env: pytest.MonkeyPatch) -> None:
    plaid_env.delenv(name)

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert name.lower() in str(excinfo.value)


def test_plaid_settings_env_rejects_development(plaid_env: pytest.MonkeyPatch) -> None:
    plaid_env.setenv("PLAID_ENV", "development")

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("env", ["sandbox", "production"])
def test_plaid_settings_env_accepted(env: str, plaid_env: pytest.MonkeyPatch) -> None:
    plaid_env.setenv("PLAID_ENV", env)

    assert Settings().plaid_env == env
