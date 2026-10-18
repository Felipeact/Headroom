"""Spec 14 C39, C40: a real Plaid sandbox item synced through the real PlaidClient.

Deselected by default; `.specs/features/14-bank-transaction-sync/proofs.sh c39` runs it
with the sandbox keys from `.env.local` exported. It fails, never skips, without them.
"""

import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import events
from app.db import get_sessionmaker
from app.main import app
from app.modules.bank_sync import service
from app.modules.bank_sync.models import BankConnection, BankTransaction
from app.modules.bank_sync.plaid import get_plaid_client
from app.modules.bank_sync.providers import to_cents
from app.modules.bank_sync.tokens import decrypt_access_token
from app.settings import get_settings
from tests.test_bank_connect_sandbox import sandbox_public_token
from tests.test_businesses import HARBOR, _owner
from tests.test_transaction_sync import snapshot

pytestmark = [pytest.mark.plaid_sandbox, pytest.mark.usefixtures("migrated_database")]

INSTITUTION_ID = "ins_42"  # TD Canada Trust, user_good; no OAuth
READY_SECONDS = 180


def stored_amounts(business_id: uuid.UUID) -> dict[str, int]:
    with get_sessionmaker()() as session:
        return {
            t.provider_transaction_id: t.amount_cents
            for t in session.scalars(
                select(BankTransaction).where(
                    BankTransaction.business_id == business_id
                )
            )
        }


def test_sandbox_sync_signs_amounts_and_repeats_cleanly() -> None:
    settings = get_settings()
    assert settings.plaid_env == "sandbox"
    assert settings.plaid_client_id != "test-client-id", (
        "export services/core/.env.local first (proofs.sh c39)"
    )
    get_plaid_client.cache_clear()
    plaid = get_plaid_client()
    client = TestClient(app)
    owner, business = _owner({**HARBOR, "name": f"Sandbox {uuid.uuid4().hex[:6]}"})
    business_id = uuid.UUID(business)

    response = client.post(
        f"/v1/businesses/{business}/bank/connections",
        json={"public_token": sandbox_public_token(INSTITUTION_ID)},
        headers=owner.headers,
    )
    assert response.status_code == 201, response.text
    connection_id = uuid.UUID(response.json()["id"])
    with get_sessionmaker()() as session:
        ciphertext = session.scalar(
            select(BankConnection.access_token_ciphertext).where(
                BankConnection.id == connection_id
            )
        )
    assert ciphertext is not None
    access_token = decrypt_access_token(ciphertext)

    def sync() -> service.SyncResult:
        with get_sessionmaker()() as session:
            return service.sync_connection(
                session, plaid, business_id=business_id, connection_id=connection_id
            )

    try:
        # The sandbox prepares the item's history a few seconds after it is created;
        # wait until it has landed and a sync finds nothing more.
        deadline = time.monotonic() + READY_SECONDS
        while True:
            result = sync()
            if stored_amounts(business_id) and not result.changed:
                break
            assert time.monotonic() < deadline, "sandbox history never arrived"
            time.sleep(3)

        # C39: every stored amount is the negated amount Plaid returned for that ID.
        plaid_amounts: dict[str, float] = {}
        cursor: str | None = None
        while True:
            page = plaid.sync_transactions(access_token, cursor)
            for transaction in [*page.added, *page.modified]:
                plaid_amounts[transaction.transaction_id] = transaction.amount
            for removed in page.removed:
                plaid_amounts.pop(removed, None)
            cursor = page.next_cursor
            if not page.has_more:
                break
        stored = stored_amounts(business_id)
        assert set(stored) == set(plaid_amounts)
        for transaction_id, cents in stored.items():
            assert cents == -(to_cents(plaid_amounts[transaction_id]) or 0), (
                transaction_id
            )
        assert any(cents > 0 for cents in stored.values())
        assert any(cents < 0 for cents in stored.values())

        # C40: syncing again with no new sandbox activity changes nothing.
        before = snapshot(business_id)
        seen: list[events.Event] = []
        events.subscribe("transactions.synced", seen.append)
        try:
            again = sync()
        finally:
            events.unsubscribe("transactions.synced", seen.append)
        assert not again.changed
        assert seen == []
        assert snapshot(business_id) == before
    finally:
        plaid.remove_item(access_token)
