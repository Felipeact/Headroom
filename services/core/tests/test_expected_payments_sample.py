"""Spec 20: the Harbor Street Plumbing sample's expected payments (AC 27)."""

import contextlib
import io
import json
import uuid
from typing import Any

import pytest

from app.db import get_sessionmaker
from app.fixtures import load
from app.modules.forecasting import repository
from tests.test_recurring_sample import Sample
from tests.tokens import bearer, token

pytestmark = pytest.mark.usefixtures("migrated_database")

SAMPLE_PAYMENTS = {
    ("Acme Co, invoice 1042", 800_000, "2026-10-06", None),
    ("Coastal Supply Co, quarterly order", -1_450_000, "2026-11-12", "quarterly"),
    ("Birch & Co, invoice 1057", 960_000, "2026-11-17", None),
    ("Equipment lease deposit", -300_000, "2026-12-07", None),
}


def run_load(clerk_user_id: str) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = load.main(
            ["harbor_street", "--seed", "0", "--clerk-user-id", clerk_user_id]
        )
    assert code == 0
    plain = []
    for line in out.getvalue().splitlines():
        try:
            json.loads(line)
        except ValueError:
            plain.append(line)
    assert len(plain) == 1, out.getvalue()
    return str(uuid.UUID(plain[0].removeprefix("already loaded:").strip()))


def payments(sample: Sample) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = sample.get("expected-payments")["items"]
    return items


def test_sample_payments() -> None:
    """C33."""
    clerk_user_id = f"user_sample_{uuid.uuid4().hex[:10]}"
    sample = Sample(run_load(clerk_user_id), bearer(token(clerk_user_id)))

    items = payments(sample)
    operating = sample.account_id("Operating checking")
    assert {
        (i["description"], i["amount_cents"], i["date"], i["repeats"]) for i in items
    } == SAMPLE_PAYMENTS
    assert len(items) == 4
    assert {i["account_id"] for i in items} == {operating}
    with get_sessionmaker()() as session:
        assert (
            repository.matches(session, business_id=uuid.UUID(sample.business_id)) == []
        )


def test_load_twice() -> None:
    """C34."""
    clerk_user_id = f"user_sample_{uuid.uuid4().hex[:10]}"
    first = run_load(clerk_user_id)
    second = run_load(clerk_user_id)
    assert first == second
    sample = Sample(first, bearer(token(clerk_user_id)))
    assert len(payments(sample)) == 4
