"""Spec 17a C32: the real Flinks client against the Flinks sandbox (toolbox).

Deselected by default; run with `uv run pytest -m flinks_sandbox` and the four `FLINKS_*`
sandbox settings in `.env.local`. It fails, never skips, without them. The loginId comes
from Flinks' direct `Authorize` with the documented test user, which stands in for the
Flinks Connect iframe.
"""

import time

import httpx
import pytest

from app.modules.bank_sync.flinks import HttpxFlinksClient, get_flinks_client
from app.settings import get_settings

pytestmark = pytest.mark.flinks_sandbox

# Flinks docs, "Test users": FlinksCapital with no MFA.
INSTITUTION = "FlinksCapital"
USERNAME = "greatday_nomfa"
PASSWORD = "Everyday"


def sandbox_login_id() -> str:
    settings = get_settings()
    base = (
        f"https://{settings.flinks_instance}-api.private.fin.ag"
        f"/v3/{settings.flinks_customer_id}/BankingServices"
    )
    with httpx.Client(timeout=60) as http:
        token = http.post(
            f"{base}/GenerateAuthorizeToken",
            headers={"flinks-auth-key": str(settings.flinks_auth_key)},
        ).json()["Token"]
        authorized = http.post(
            f"{base}/Authorize",
            headers={"flinks-auth-key": token},
            json={
                "Institution": INSTITUTION,
                "Username": USERNAME,
                "Password": PASSWORD,
                "MostRecentCached": False,
                "Save": True,
            },
        )
        assert authorized.status_code == 200, authorized.status_code
        request_id = authorized.json()["RequestId"]
        headers = {"x-api-key": str(settings.flinks_api_key)}
        detail = http.post(
            f"{base}/GetAccountsDetail", headers=headers, json={"RequestId": request_id}
        )
        for _ in range(30):
            if detail.status_code != 202:
                break
            time.sleep(10)
            detail = http.get(
                f"{base}/GetAccountsDetailAsync/{request_id}", headers=headers
            )
        assert detail.status_code == 200, detail.status_code
        # Flinks docs: GetAccountsDetail's `Login.Id` is the loginId.
        return str(detail.json()["Login"]["Id"])


def test_transaction_ids_are_stable() -> None:
    get_flinks_client.cache_clear()
    client = get_flinks_client()
    if client is None:
        pytest.fail("Set the four FLINKS_* sandbox settings in .env.local")
    assert isinstance(client, HttpxFlinksClient)
    login_id = sandbox_login_id()
    try:
        first = client.accounts(
            login_id, with_transactions=True, days="Days90", polls=30
        )
        second = client.accounts(
            login_id, with_transactions=True, days="Days90", polls=30
        )

        assert first.accounts, "the sandbox login has accounts"
        first_ids = {t.transaction_id for t in first.transactions}
        assert first_ids
        assert first_ids <= {t.transaction_id for t in second.transactions}
    finally:
        client.delete(login_id)
