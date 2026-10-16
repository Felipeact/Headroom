import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.main import app

CORE_DIR = Path(__file__).resolve().parents[1]
CONTRACT = CORE_DIR.parents[1] / "contracts" / "openapi.json"


@pytest.fixture(autouse=True)
def restore_contract() -> Iterator[None]:
    # The export writes the tracked contract; put the committed bytes back afterwards.
    original = CONTRACT.read_bytes()
    yield
    CONTRACT.write_bytes(original)


def run_export(cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env["PYTHONPATH"] = str(CORE_DIR)
    return subprocess.run(
        [sys.executable, "-m", "app.export_openapi"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_writes_contract_from_any_cwd(tmp_path: Path) -> None:
    CONTRACT.unlink()  # so only this export can make it exist again

    result = run_export(tmp_path)

    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == app.openapi()


def test_output_is_deterministic(tmp_path: Path) -> None:
    assert run_export(tmp_path).returncode == 0
    first = CONTRACT.read_bytes()
    assert run_export(tmp_path).returncode == 0
    second = CONTRACT.read_bytes()

    assert first == second
    assert first.endswith(b"\n")
    assert not first.endswith(b"\n\n")
    assert b"\r" not in first


def test_contract_has_healthz_paths() -> None:
    paths = json.loads(CONTRACT.read_text(encoding="utf-8"))["paths"]

    assert "/healthz/live" in paths
    assert "/healthz/ready" in paths


def test_email_routes() -> None:
    """Spec 28 C30: the preferences routes and the public unsubscribe route."""
    paths = json.loads(CONTRACT.read_text(encoding="utf-8"))["paths"]

    assert set(paths["/v1/me/email-preferences"]) == {"get", "put"}
    assert set(paths["/v1/unsubscribe/{token}"]) == {"post"}
