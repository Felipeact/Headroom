"""Spec 19: recurring patterns found in the Harbor Street Plumbing sample data."""

import contextlib
import io
import json
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.fixtures import load
from app.main import app
from tests.tokens import bearer, token

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)


@dataclass(frozen=True)
class Sample:
    business_id: str
    headers: dict[str, str]

    def get(self, path: str) -> Any:
        response = client.get(
            f"/v1/businesses/{self.business_id}/{path}", headers=self.headers
        )
        assert response.status_code == 200, response.text
        return response.json()

    def patterns(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = self.get("recurring-patterns")["items"]
        return items

    def account_id(self, name: str) -> str:
        for connection in self.get("bank/connections")["items"]:
            for account in connection["accounts"]:
                if account["name"] == name:
                    return str(account["id"])
        raise AssertionError(name)

    def transactions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor = None
        while True:
            query = "bank/transactions?limit=500" + (
                f"&cursor={cursor}" if cursor else ""
            )
            body = self.get(query)
            items += body["items"]
            cursor = body["next_cursor"]
            if cursor is None:
                return items


def load_sample(seed: int) -> Sample:
    clerk_user_id = f"user_sample_{uuid.uuid4().hex[:10]}"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = load.main(
            ["harbor_street", "--seed", str(seed), "--clerk-user-id", clerk_user_id]
        )
    assert code == 0
    plain = []
    for line in out.getvalue().splitlines():
        try:
            json.loads(line)
        except ValueError:
            plain.append(line)
    assert len(plain) == 1, out.getvalue()
    return Sample(str(uuid.UUID(plain[0].strip())), bearer(token(clerk_user_id)))


@pytest.fixture(scope="module")
def sample(migrated_database: None) -> Sample:
    return load_sample(0)


def by_counterparty(sample: Sample, counterparty: str) -> dict[str, Any]:
    found = [p for p in sample.patterns() if p["counterparty"] == counterparty]
    assert len(found) == 1, sample.patterns()
    return found[0]


def test_payroll(sample: Sample) -> None:
    """C14."""
    payroll = by_counterparty(sample, "Payroll")
    assert payroll["account_id"] == sample.account_id("Operating checking")
    assert payroll["schedule"] == "biweekly"
    assert payroll["amount_cents"] == -1_120_000
    assert payroll["currency"] == "CAD"
    assert payroll["next_date"] == "2026-10-02"


def test_rent(sample: Sample) -> None:
    """C15."""
    rent = by_counterparty(sample, "Wharfside Properties")
    assert rent["description"] == "Rent"
    assert rent["account_id"] == sample.account_id("Operating checking")
    assert rent["schedule"] == "monthly"
    assert rent["amount_cents"] == -380_000
    assert rent["next_date"] == "2026-10-15"


def test_software(sample: Sample) -> None:
    """C16."""
    software = by_counterparty(sample, "Fieldworks Software")
    assert software["description"] == "Software subscriptions"
    assert software["account_id"] == sample.account_id("Operating checking")
    assert software["schedule"] == "monthly"
    assert software["amount_cents"] == -64_000
    assert software["next_date"] == "2026-10-07"


@pytest.mark.parametrize("seed", range(10))
def test_exactly_three(seed: int) -> None:
    """C17."""
    patterns = load_sample(seed).patterns()
    assert sorted(p["counterparty"] for p in patterns) == [
        "Fieldworks Software",
        "Payroll",
        "Wharfside Properties",
    ]


def test_no_transfers(sample: Sample) -> None:
    """C18."""
    transactions = {t["id"]: t for t in sample.transactions()}
    reserve = sample.account_id("Reserve savings")
    operating = sample.account_id("Operating checking")
    transfer_accounts = {
        t["account_id"]
        for t in transactions.values()
        if t["label"] == "internal_transfer"
    }
    assert {reserve, operating} <= transfer_accounts
    for pattern in sample.patterns():
        for transaction_id in pattern["transaction_ids"]:
            t = transactions[transaction_id]
            assert t["account_id"] != reserve
            assert t["label"] != "internal_transfer"
