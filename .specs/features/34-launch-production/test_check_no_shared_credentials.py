"""Spec 34 C12-C15: the shared-credential check, on fixtures with known values."""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_PATH = Path(__file__).with_name("check_no_shared_credentials.py")
_spec = importlib.util.spec_from_file_location("check_no_shared_credentials", _PATH)
assert _spec is not None and _spec.loader is not None
check: Any = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = check
_spec.loader.exec_module(check)

ALLOWLISTED = [
    "NEXT_PUBLIC_CLERK_SIGN_IN_URL",
    "NEXT_PUBLIC_CLERK_SIGN_UP_URL",
    "POSTHOG_HOST",
    "POSTHOG_APP_HOST",
    "EMAIL_MAILING_ADDRESS",
    "FORECAST_STRATEGY",
    "PLAID_CLIENT_ID",
    "RAILWAY_PROJECT_ID",
]


def env(name: str) -> dict[str, dict[str, str]]:
    """Distinct per-environment values for every service, so nothing is shared."""
    return {
        "api": {
            "RESEND_API_KEY": f"re_{name}_k3y-value",
            "PLAID_SECRET": f"plaid-{name}-s3cret",
            "DATABASE_URL": f"postgresql+psycopg://u:{name}-pw@host/db",
        },
        "web": {"CLERK_SECRET_KEY": f"sk_test_{name}_web"},
        "jobs": {"TOKEN_ENCRYPTION_KEYS": f"fernet-{name}-key="},
    }


def reader(data: dict[str, dict[str, dict[str, str]]]) -> Any:
    return lambda service, environment: data[environment][service]


def values(data: dict[str, dict[str, dict[str, str]]]) -> list[str]:
    return [v for e in data.values() for s in e.values() for v in s.values()]


def fixtures() -> dict[str, dict[str, dict[str, str]]]:
    return {"staging": env("staging"), "production": env("production")}


def run(data: Any, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = check.main(read=reader(data))
    out = capsys.readouterr()
    return code, out.out + out.err


def test_clean_passes(capsys: pytest.CaptureFixture[str]) -> None:
    code, _ = run(fixtures(), capsys)
    assert code == 0


def test_shared_secret_fails(capsys: pytest.CaptureFixture[str]) -> None:
    data = fixtures()
    data["production"]["api"]["RESEND_API_KEY"] = data["staging"]["api"][
        "RESEND_API_KEY"
    ]

    code, output = run(data, capsys)

    assert code == 1
    assert [line for line in output.splitlines() if not line.startswith("FAIL")] == [
        "api RESEND_API_KEY"
    ]


def test_allowlist_equal_passes(capsys: pytest.CaptureFixture[str]) -> None:
    data = fixtures()
    for service in ("api", "web", "jobs"):
        for name in ALLOWLISTED:
            data["staging"][service][name] = f"same-{name}"
            data["production"][service][name] = f"same-{name}"

    code, _ = run(data, capsys)

    assert code == 0


def test_allowlist_does_not_cover_new_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = fixtures()
    data["staging"]["web"]["NEW_SECRET"] = "brand-new-value"
    data["production"]["web"]["NEW_SECRET"] = "brand-new-value"

    code, output = run(data, capsys)

    assert code == 1
    assert "web NEW_SECRET" in output.splitlines()


def test_no_value_printed(capsys: pytest.CaptureFixture[str]) -> None:
    clean = fixtures()
    failing = fixtures()
    for service in ("api", "web", "jobs"):
        failing["production"][service] = dict(failing["staging"][service])

    for data in (clean, failing):
        _, output = run(data, capsys)
        assert [v for v in values(data) if v in output] == []


def test_cli_failure(capsys: pytest.CaptureFixture[str]) -> None:
    data = fixtures()
    compared: list[tuple[str, str]] = []

    def read(service: str, environment: str) -> dict[str, str]:
        if (service, environment) == ("web", "production"):
            raise check.ReadError(service, environment, "railway exited 2")
        compared.append((service, environment))
        return data[environment][service]

    original = check.shared
    calls: list[object] = []
    check.shared = lambda v: calls.append(v) or original(v)
    try:
        code = check.main(read=read)
    finally:
        check.shared = original
    output = capsys.readouterr()

    assert code == 1
    assert "web" in output.err and "production" in output.err
    assert calls == []
