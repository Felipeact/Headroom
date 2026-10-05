"""Spec 13 C31: two Plaid sandbox banks on one business, through the real PlaidClient.

Deselected by default; `.specs/features/13-bank-cash-accounts/proofs.sh c31` runs it with
the sandbox keys from `.env.local` exported. It fails, never skips, without them.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_sessionmaker
from app.main import app
from app.modules.bank_sync.models import BankConnection
from app.modules.bank_sync.plaid import get_plaid_client
from app.modules.bank_sync.tokens import decrypt_access_token
from app.settings import get_settings
from tests.test_bank_connect_sandbox import sandbox_public_token
from tests.test_businesses import HARBOR, _owner

pytestmark = [pytest.mark.plaid_sandbox, pytest.mark.usefixtures("migrated_database")]

# Found through /institutions/search (country CA, transactions) on 2026-10-04; neither
# uses OAuth.
BANKS = {"ins_42": "TD Canada Trust", "ins_39": "RBC Royal Bank"}


def test_two_sandbox_banks_on_one_business() -> None:
    settings = get_settings()
    assert settings.plaid_env == "sandbox"
    assert settings.plaid_client_id != "test-client-id", (
        "export services/core/.env.local first (proofs.sh c31)"
    )
    get_plaid_client.cache_clear()
    client = TestClient(app)
    owner, business_id = _owner({**HARBOR, "name": f"Sandbox {uuid.uuid4().hex[:6]}"})
    path = f"/v1/businesses/{business_id}/bank/connections"

    try:
        for institution_id in BANKS:
            response = client.post(
                path,
                json={"public_token": sandbox_public_token(institution_id)},
                headers=owner.headers,
            )
            assert response.status_code == 201, response.text

        listed = client.get(path, headers=owner.headers)

        assert listed.status_code == 200
        items = listed.json()["items"]
        assert [c["institution_name"] for c in items] == list(BANKS.values())
        accounts = [a for c in items for a in c["accounts"]]
        assert all(a["currency"] for a in accounts)
        assert sum(a["primary"] for a in accounts) == 1
    finally:
        with get_sessionmaker()() as session:
            ciphertexts = session.scalars(
                select(BankConnection.access_token_ciphertext).where(
                    BankConnection.business_id == uuid.UUID(business_id)
                )
            ).all()
        for ciphertext in ciphertexts:
            get_plaid_client().remove_item(decrypt_access_token(ciphertext))
