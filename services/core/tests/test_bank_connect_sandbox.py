"""Spec 12 C21: the real PlaidClient against the Plaid sandbox.

Deselected by default; `.specs/features/12-bank-connect/proofs.sh c21` runs it with the
sandbox keys from `.env.local` exported. It fails, never skips, without them.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from plaid import ApiClient, Configuration, Environment
from plaid.api.plaid_api import PlaidApi
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import (
    SandboxPublicTokenCreateRequest,
)
from sqlalchemy import select

from app.db import get_sessionmaker
from app.main import app
from app.modules.bank_sync.models import BankConnection
from app.modules.bank_sync.plaid import get_plaid_client
from app.modules.bank_sync.tokens import decrypt_access_token
from app.settings import get_settings
from tests.test_businesses import HARBOR, _owner

pytestmark = [pytest.mark.plaid_sandbox, pytest.mark.usefixtures("migrated_database")]

ACCOUNT_TYPES = {"checking", "savings", "credit_card", "line_of_credit", "other"}


def sandbox_public_token(institution_id: str) -> str:
    settings = get_settings()
    configuration = Configuration(
        host=Environment.Sandbox,
        api_key={"clientId": settings.plaid_client_id, "secret": settings.plaid_secret},
    )
    response = PlaidApi(ApiClient(configuration)).sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id=institution_id,
            initial_products=[Products("transactions")],
        )
    )
    return str(response.public_token)


def test_sandbox_connects_td_canada_trust() -> None:
    settings = get_settings()
    assert settings.plaid_env == "sandbox"
    assert settings.plaid_client_id != "test-client-id", (
        "export services/core/.env.local first (proofs.sh c21)"
    )
    get_plaid_client.cache_clear()
    client = TestClient(app)
    owner, business_id = _owner({**HARBOR, "name": f"Sandbox {uuid.uuid4().hex[:6]}"})

    link = client.post(
        f"/v1/businesses/{business_id}/bank/link-token", headers=owner.headers
    )
    assert link.status_code == 200
    assert link.json()["link_token"].startswith("link-sandbox-")

    response = client.post(
        f"/v1/businesses/{business_id}/bank/connections",
        json={"public_token": sandbox_public_token("ins_42")},
        headers=owner.headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["institution_name"] == "TD Canada Trust"
    assert len(body["accounts"]) >= 1
    assert {a["type"] for a in body["accounts"]} <= ACCOUNT_TYPES
    assert {a["currency"] for a in body["accounts"]} == {"CAD"}

    with get_sessionmaker()() as session:
        ciphertext = session.scalars(
            select(BankConnection.access_token_ciphertext).where(
                BankConnection.business_id == uuid.UUID(business_id)
            )
        ).one()
    access_token = decrypt_access_token(ciphertext)
    assert access_token.startswith("access-sandbox-")
    get_plaid_client().remove_item(access_token)
