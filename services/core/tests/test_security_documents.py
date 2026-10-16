"""Spec 33 S5: the access table and the rehearsal record (C27, C29)."""

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SECURITY = REPO / "context" / "security"


def test_access_table_complete() -> None:
    """C27."""
    text = (SECURITY / "access.md").read_text(encoding="utf8")
    services = ["Clerk", "Railway", "GitHub", "Resend", "PostHog", "Sentry", "Plaid"]
    services.append("Domain registrar")
    rows = [line for line in text.splitlines() if line.startswith("| ")]
    for service in services:
        mine = [r for r in rows if r.split("|")[1].strip() == service]
        assert mine, service
        for row in mine:
            cells = [c.strip() for c in row.strip("|").split("|")]
            person, role, reason, two_factor, checked = cells[1:6]
            assert person and role and reason, row
            assert two_factor == "yes", row
            when = date.fromisoformat(checked)
            assert datetime.now(UTC).date() - when <= timedelta(days=90), row
    pairs: dict[str, set[str]] = {}
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if cells[0] in services:
            pairs.setdefault(cells[1], set()).add(f"{cells[0]}:{cells[2]}")
    for person, held in pairs.items():
        roles = {h.split(":", 1)[0] + h.split(":", 1)[1] for h in held}
        assert len(roles) == len(held), person


def test_rehearsal_recorded() -> None:
    """C29."""
    records = sorted(SECURITY.glob("rehearsal-*.md"))
    assert records
    record = records[-1]
    text = record.read_text(encoding="utf8")
    stamp = record.stem.removeprefix("rehearsal-")
    date.fromisoformat(stamp)
    for label in ("Date:", "Scenario:", "Participants:"):
        assert re.search(rf"^{label} \S", text, flags=re.MULTILINE), label
    plan = (SECURITY / "incident-response.md").read_text(encoding="utf8")
    first = plan.split("## First hour", 1)[1].split("\n## ", 1)[0]
    steps = re.findall(r"^\d+\. ", first, flags=re.MULTILINE)
    timings = re.findall(r"^Step \d+: \d+ min", text, flags=re.MULTILINE)
    assert len(timings) == len(steps)
    wrong = text.split("What the plan got wrong", 1)[1]
    assert wrong.strip(), "write what the plan got wrong, or the word nothing"
    assert f"Last rehearsed: {stamp}" in plan
