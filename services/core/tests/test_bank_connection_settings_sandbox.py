"""Spec 17 C26 and C48: login required and disconnect against the real Plaid sandbox.

Deselected by default; `.specs/features/17-bank-connection-settings/proofs.sh c26 c48`
runs them with the sandbox keys from `.env.local` exported. They fail, never skip,
without them.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_sessionmaker
from app.main import app
from app.modules.bank_sync.models import BankConnection
from app.modules.bank_sync.plaid import PlaidError, get_plaid_client
from app.modules.bank_sync.tokens import decrypt_access_token
from app.settings import get_settings
from tests.sandbox_reset_login import reset_login
from tests.test_bank_connect_sandbox import sandbox_public_token
from tests.test_businesses import HARBOR, Caller, _owner

pytestmark = [pytest.mark.plaid_sandbox, pytest.mark.usefixtures("migrated_database")]

client = TestClient(app)


def connect_td() -> tuple[Caller, str, dict[str, Any], str]:
    """An owner with TD Canada Trust connected through the sandbox, and its token."""
    settings = get_settings()
    assert settings.plaid_env == "sandbox"
    assert settings.plaid_client_id != "test-client-id", (
        "export services/core/.env.local first (proofs.sh)"
    )
    get_plaid_client.cache_clear()
    owner, business_id = _owner({**HARBOR, "name": f"Sandbox {uuid.uuid4().hex[:6]}"})
    response = client.post(
        f"/v1/businesses/{business_id}/bank/connections",
        json={"public_token": sandbox_public_token("ins_42")},
        headers=owner.headers,
    )
    assert response.status_code == 201, response.text
    with get_sessionmaker()() as session:
        ciphertext = session.scalars(
            select(BankConnection.access_token_ciphertext).where(
                BankConnection.business_id == uuid.UUID(business_id)
            )
        ).one()
    return owner, business_id, response.json(), decrypt_access_token(ciphertext)


def test_sandbox_login_required() -> None:
    """C26."""
    owner, business_id, connection, token = connect_td()
    base = f"/v1/businesses/{business_id}/bank/connections"
    try:
        assert reset_login(uuid.UUID(business_id)) == 1

        listed = client.get(base, headers=owner.headers)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["status"] == "login_required"

        link = client.post(
            f"{base}/{connection['id']}/link-token", headers=owner.headers
        )
        assert link.status_code == 200, link.text
        assert link.json()["link_token"].startswith("link-sandbox-")
    finally:
        get_plaid_client().remove_item(token)


def test_sandbox_disconnect() -> None:
    """C48."""
    owner, business_id, connection, token = connect_td()

    response = client.delete(
        f"/v1/businesses/{business_id}/bank/connections/{connection['id']}",
        headers=owner.headers,
    )

    assert response.status_code == 204, response.text
    with pytest.raises(PlaidError) as excinfo:
        get_plaid_client().get_accounts(token)
    assert excinfo.value.error_code == "ITEM_NOT_FOUND"
