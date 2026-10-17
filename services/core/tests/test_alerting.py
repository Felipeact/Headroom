"""Spec 34: failures the team must hear about are logged at `error` (door 4)."""

import json
import uuid
from typing import Any

import pytest

from app.log import configure_logging
from app.modules.bank_sync import service
from app.modules.bank_sync.plaid import PlaidError
from tests import webhook_signing as signing
from tests.test_plaid_webhook import _fresh_key_cache, connected, fake, owner, post
from tests.test_transaction_sync import ACCESS_TOKEN, Connected, SyncFake

__all__ = ["_fresh_key_cache", "connected", "fake", "owner"]


def logged(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    lines = []
    for line in capsys.readouterr().out.splitlines():
        try:
            lines.append(json.loads(line))
        except ValueError:
            continue
    return lines


@pytest.mark.usefixtures("migrated_database")
def test_sync_failed_plaid_is_error(
    fake: SyncFake, connected: Connected, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.script = [
        PlaidError(error_type="ITEM_ERROR", error_code="ITEM_LOCKED", request_id="r-34")
    ]
    configure_logging()
    capsys.readouterr()

    service.sync_in_background(
        fake, business_id=connected.business_id, connection_id=connected.connection_id
    )

    out = capsys.readouterr().out
    assert ACCESS_TOKEN not in out
    failed = [
        json.loads(line)
        for line in out.splitlines()
        if '"bank_sync.sync_failed"' in line
    ]
    assert len(failed) == 1
    assert failed[0]["level"] == "error"
    assert failed[0]["business_id"] == str(connected.business_id)
    assert failed[0]["connection_id"] == str(connected.connection_id)
    assert failed[0]["error_type"] == "ITEM_ERROR"
    assert failed[0]["error_code"] == "ITEM_LOCKED"
    assert failed[0]["request_id"] == "r-34"


def test_sync_failed_other_is_error(capsys: pytest.CaptureFixture[str]) -> None:
    business_id, connection_id = uuid.uuid4(), uuid.uuid4()
    configure_logging()
    capsys.readouterr()

    service._log_failure(business_id, connection_id, RuntimeError("boom-secret"))

    out = capsys.readouterr().out
    assert "boom-secret" not in out
    failed = [json.loads(line) for line in out.splitlines()]
    assert len(failed) == 1
    assert failed[0]["event"] == "bank_sync.sync_failed"
    assert failed[0]["level"] == "error"
    assert failed[0]["business_id"] == str(business_id)
    assert failed[0]["connection_id"] == str(connection_id)
    assert failed[0]["error_type"] == "RuntimeError"


@pytest.mark.usefixtures("migrated_database")
def test_webhook_levels_key_fetch_fails(
    fake: SyncFake, connected: Connected, capsys: pytest.CaptureFixture[str]
) -> None:
    content = signing.body(connected.provider_item_id)
    fake.fail = {
        "key": PlaidError(error_type="API_ERROR", error_code="X", request_id="r-k")
    }
    configure_logging()
    capsys.readouterr()

    assert post(content, signing.headers(content)).status_code == 502

    failed = [
        line for line in logged(capsys) if line.get("event") == "plaid.request_failed"
    ]
    assert len(failed) == 1
    assert failed[0]["level"] == "error"
    assert failed[0]["request_id"] == "r-k"


@pytest.mark.usefixtures("migrated_database")
def test_webhook_levels_invalid_signature(
    fake: SyncFake, connected: Connected, capsys: pytest.CaptureFixture[str]
) -> None:
    content = signing.body(connected.provider_item_id)
    configure_logging()
    capsys.readouterr()

    response = post(content, signing.headers(content, key=signing.OTHER_KEY))

    assert response.status_code == 401
    assert [line for line in logged(capsys) if line.get("level") == "error"] == []
