import json
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import structlog

from app.log import configure_logging

CORE = Path(__file__).resolve().parents[1]
UUID = "1b4e28ba-2fa1-11d2-883f-0016e5f2c3a1"

SECRET_KEYS = [
    "Plaid_Access_TOKEN",
    "client_Secret",
    "Password",
    "db_PASSWD",
    "Authorization",
    "Set_Cookie",
    "Plaid_API_KEY",
    "resend_ApiKey",
    "Sentry_DSN",
    "Account_Number",
    "Private_Key_pem",
]

TOKENS = [
    f"access-sandbox-{UUID}",
    f"access-development-{UUID}",
    f"access-production-{UUID}",
    "Bearer abc.def-123",
]


def test_line_is_json_with_core_keys(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    structlog.get_logger("t").info("thing.happened", count=3)

    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert len(lines) == 1
    line = lines[0]
    assert line["event"] == "thing.happened"
    assert line["level"] == "info"
    assert line["logger"] == "t"
    assert line["count"] == 3
    assert isinstance(line["timestamp"], str)
    assert line["timestamp"].endswith("Z")


@pytest.mark.parametrize("key", SECRET_KEYS)
def test_secret_named_keys_redacted(
    key: str, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging()
    structlog.get_logger("t").info("thing.happened", **{key: "hunter2-value"})

    out = capsys.readouterr().out
    assert "hunter2-value" not in out
    assert json.loads(out)[key] == "[REDACTED]"


def test_nested_secret_keys_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    payload = {
        "items": [{"access_token": "s3cr3t"}],
        "meta": {"inner": {"password": "pw-9"}},
    }
    structlog.get_logger("t").info("thing.happened", payload=payload)

    out = capsys.readouterr().out
    assert "s3cr3t" not in out
    assert "pw-9" not in out


@pytest.mark.parametrize("token", TOKENS)
def test_token_patterns_redacted_in_strings(
    token: str, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging()
    structlog.get_logger("t").info(f"got {token} here", note=f"value {token} end")

    out = capsys.readouterr().out
    assert token not in out
    line = json.loads(out)
    assert "[REDACTED]" in line["event"]
    assert "[REDACTED]" in line["note"]


@pytest.mark.parametrize(
    "name", ["uvicorn.error", "uvicorn.access", "sqlalchemy.engine"]
)
def test_stdlib_loggers_render_json_with_redaction(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging()
    token = f"access-sandbox-{UUID}"
    logging.getLogger(name).warning("saw %s in a request", token)

    out = capsys.readouterr().out
    lines = out.splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line["logger"] == name
    assert token not in out


def test_exception_traceback_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    token = f"access-sandbox-{UUID}"
    try:
        raise ValueError(f"bad token {token}")
    except ValueError:
        structlog.get_logger("t").exception("thing.failed")

    out = capsys.readouterr().out
    assert token not in out
    exception = json.loads(out)["exception"]
    assert "Traceback" in exception
    assert "[REDACTED]" in exception


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def test_real_server_writes_json_access_log() -> None:
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "fastapi", "run", "app/main.py", "--port", str(port)],
        cwd=CORE,
        env={**os.environ, "SENTRY_DSN": ""},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/does-not-exist")
            except urllib.error.HTTPError as error:
                assert error.code == 404
                break
            except urllib.error.URLError:
                assert time.monotonic() < deadline, "server did not start"
                time.sleep(0.2)
        time.sleep(0.5)
    finally:
        server.terminate()
        output, _ = server.communicate(timeout=30)

    json_lines = [line for line in output.splitlines() if line.startswith("{")]
    assert json_lines, output
    records = [json.loads(line) for line in json_lines]
    assert any(
        r.get("logger") == "uvicorn.access" and "/does-not-exist" in str(r["event"])
        for r in records
    ), output
