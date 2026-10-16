"""Spec 30: the weekly digest against its mockup (C12-C26, C28, C31 rendering).

No database: the cases render the params of `sample_digest.SAMPLE`, the mockup's values,
with one value changed.
"""

import copy
import re
from html.parser import HTMLParser
from typing import Any

import pytest

from app.modules.notifications import rendering, sample_digest, senders
from tests.email_support import FakeEmailSender

WEB = "https://app.example.test"
ALERT_ID = sample_digest.SAMPLE["alerts"][0]["alert_id"]
FOOTER = rendering.Footer(
    reason="You're getting this email because you're an owner of Harbor Street"
    " Plumbing on Headroom.",
    preferences_url=f"{WEB}/settings/email",
    unsubscribe_url=f"{WEB}/unsubscribe/tok",
    mailing_address="1 Test St, Toronto ON M5V 1A1",
)
SUBJECT = "Your cash for the next 13 weeks"


def render(first_name: str | None = "Dana", **changes: Any) -> rendering.Rendered:
    params = copy.deepcopy(sample_digest.SAMPLE)
    params.update(changes)
    return rendering.render(
        "weekly_digest", params, first_name=first_name, footer=FOOTER
    )


def words(html: str) -> str:
    """The visible text of the HTML on one line."""
    body = re.sub(r"<style.*?</style>|<title.*?</title>", "", html, flags=re.DOTALL)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()


def hrefs(html: str) -> list[str]:
    return re.findall(r'href="([^"]+)"', html)


def changes(**values: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "cash_change_cents": 0,
        "low_change_cents": 0,
        "new_payments": [],
    }
    return {**base, **values}


class Rows(HTMLParser):
    """For each `<tr>`: its direct cell count and all the text inside it."""

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[dict[str, Any]] = []
        self.rows: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._stack.append({"cells": 0, "text": ""})
        elif tag == "td" and self._stack:
            self._stack[-1]["cells"] += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self._stack:
            self.rows.append(self._stack.pop())

    def handle_data(self, data: str) -> None:
        for row in self._stack:
            row["text"] += data


def test_sample_heading() -> None:
    """C12."""
    out = render()
    assert out.subject == SUBJECT
    assert re.search(rf"<h1[^>]*>\s*{SUBJECT}\s*</h1>", out.html)
    lines = out.text.splitlines()
    assert lines[lines.index("Weekly forecast · Monday, Sep 28") + 1] == SUBJECT


def test_label() -> None:
    """C13."""
    out = render()
    label = "Weekly forecast · Monday, Sep 28"
    assert label in words(out.html)
    assert label in out.text.splitlines()
    assert out.html.index(label) < out.html.index("<h1")


def test_greeting() -> None:
    """C14."""
    named = render()
    assert "Hi Dana, here's Harbor Street Plumbing stands" not in named.text
    assert "Hi Dana, here's where Harbor Street Plumbing stands this week." in words(
        named.html
    )
    assert (
        "Hi Dana, here's where Harbor Street Plumbing stands this week." in named.text
    )
    plain = render(first_name=None)
    assert "Here's where Harbor Street Plumbing stands this week." in words(plain.html)
    assert "Here's where Harbor Street Plumbing stands this week." in plain.text
    assert "Hi" not in words(plain.html).split("Here's")[0].split("Sep 28")[-1]


def test_cash_tile() -> None:
    """C15 (rendering)."""
    assert "Cash on hand $42,300" in words(render().html)
    assert "Cash on hand −$1,500" in words(render(cash_on_hand_cents=-150000).html)


def test_low_tile() -> None:
    """C16 (rendering): amber only below the minimum."""
    quiet: dict[str, Any] = {"alerts": [], "changes": None}
    below = render(**quiet)
    assert "Projected low $3,150 Week of Nov 9" in words(below.html)
    assert "background: #FFF4E2" in below.html
    negative = render(
        low={"balance_cents": -315000, "week_starts_on": "2026-11-09"}, **quiet
    )
    assert "Projected low −$3,150" in words(negative.html)
    for balance in (500000, 620000):
        level = render(
            low={"balance_cents": balance, "week_starts_on": "2026-11-09"}, **quiet
        )
        assert "background: #FFF4E2" not in level.html
        assert "#5C3300" not in level.html


def test_open_alerts() -> None:
    """C17 (rendering)."""
    out = render()
    text = words(out.html)
    assert "Open alerts (1)" in text
    assert (
        "Cash falls below your $5,000 minimum the week of Nov 9. See the fixes" in text
    )
    assert f"{WEB}/alerts/{ALERT_ID}" in hrefs(out.html)
    base = sample_digest.SAMPLE["alerts"][0]
    for fixes, label in ((0, "See details"), (1, "See the fix"), (2, "See the fixes")):
        found = render(alerts=[{**base, "fix_count": fixes}])
        assert f">{label}</a>" in found.html
        assert f"Nov 9. {label}: {WEB}/alerts/{ALERT_ID}" in found.text
    second = {
        **base,
        "alert_id": "00000000-0000-4000-8000-000000000031",
        "lowest_week_starts_on": "2026-12-14",
    }
    two = render(alerts=[base, second])
    assert "Open alerts (2)" in words(two.html)
    assert two.html.index("Nov 9.") < two.html.index("Dec 14.")


@pytest.mark.parametrize("balance", [620000, 500000])
def test_all_clear(balance: int) -> None:
    """C18 (rendering): above the minimum, and exactly equal to it."""
    out = render(
        alerts=[], low={"balance_cents": balance, "week_starts_on": "2026-11-09"}
    )
    line = "All clear. Your forecast stays above your $5,000 minimum for the next 13 weeks."
    assert line in words(out.html)
    assert line in out.text
    assert "Open alerts" not in out.html
    assert "Open alerts" not in out.text


def test_dismissed_gap() -> None:
    """C19 (rendering): a gap with every alert dismissed shows neither block."""
    out = render(alerts=[])
    for body in (words(out.html), out.text):
        assert "Open alerts" not in body
        assert "All clear" not in body
    assert "background: #FFF4E2" in out.html


def test_changes_bullets() -> None:
    """C20 (rendering): wording, direction, order and omission."""
    payment = {"name": "Acme Co", "amount_cents": 800000, "date": "2026-10-06"}
    out = render(
        changes=changes(
            cash_change_cents=412000, low_change_cents=-60000, new_payments=[payment]
        )
    )
    bullets = re.findall(r"<li>(.*?)</li>", out.html)
    assert bullets == [
        "Cash on hand is up $4,120.",
        "New expected payment: Acme Co, $8,000, on Tue, Oct 6.",
        "Your projected low is $600 lower than last week.",
    ]
    assert "- Cash on hand is up $4,120." in out.text
    down = render(changes=changes(cash_change_cents=-50000, low_change_cents=60000))
    assert re.findall(r"<li>(.*?)</li>", down.html) == [
        "Cash on hand is down $500.",
        "Your projected low is $600 higher than last week.",
    ]
    zero_cash = render(changes=changes(low_change_cents=-60000))
    assert re.findall(r"<li>(.*?)</li>", zero_cash.html) == [
        "Your projected low is $600 lower than last week."
    ]


def test_nothing_changed() -> None:
    """C21."""
    out = render(changes=changes())
    assert "What changed since last week" in out.html
    assert "Nothing has changed since last week." in words(out.html)
    assert "Nothing has changed since last week." in out.text
    assert "<li>" not in out.html


def test_no_changes_section() -> None:
    """C22 (rendering)."""
    out = render(changes=None)
    assert "What changed" not in out.html
    assert "What changed" not in out.text


def test_dashboard_button() -> None:
    """C23."""
    out = render()
    assert re.search(
        rf'<a href="{re.escape(WEB)}/"[^>]*>Open your dashboard</a>', out.html
    )
    assert f"Open your dashboard: {WEB}/" in out.text.splitlines()


def test_plain_text_order() -> None:
    """C24."""
    text = render().text
    order = [
        "Weekly forecast · Monday, Sep 28",
        SUBJECT,
        "Hi Dana, here's where Harbor Street Plumbing stands this week.",
        "Cash on hand: $42,300",
        "Projected low: $3,150 (week of Nov 9)",
        "Open alerts (1)",
        "Cash falls below your $5,000 minimum the week of Nov 9.",
        "What changed since last week",
        f"Open your dashboard: {WEB}/",
    ]
    positions = [text.index(part) for part in order]
    assert positions == sorted(positions)


def test_email_safe_html() -> None:
    """C25."""
    html = render().html
    for banned in ("display: flex", "display:flex", "grid", "position:"):
        assert banned not in html.lower()
    for tag in ("<link", "<script", "<img"):
        assert tag not in html.lower()
    parser = Rows()
    parser.feed(html)
    outer = [
        r
        for r in parser.rows
        if "Cash on hand" in r["text"] and "Projected low" in r["text"]
    ]
    # The page's own wrapper rows hold the tiles too, with one cell each.
    assert [r["cells"] for r in outer].count(2) == 1
    assert re.search(r'<td bgcolor="#1D4E89"[^>]*>\s*<a [^>]*color: #FFFFFF', html)


def test_mockup_colours() -> None:
    """C26."""
    html = render().html
    assert re.search(r"text-transform: uppercase; color: #5A6370", html)
    assert "border: 1px solid #E2DDD3" in html
    assert "background: #FFF4E2; border: 1px solid #F0D3A4" in html
    assert "color: #5C3300" in html
    assert "color: #7A4300" in html
    assert "color: #3D2E1C" in html
    assert "#1D4E89" in html


def test_sample_digest_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """C28."""
    sender = FakeEmailSender()
    monkeypatch.setattr(senders, "get_email_sender", lambda: sender)
    assert sample_digest.main(["--to", "someone@example.test"]) == 0
    (sent,) = sender.sent
    assert sent.to == "someone@example.test"
    assert sent.subject == SUBJECT
    assert "Cash falls below your $5,000 minimum the week of Nov 9." in sent.html
    with pytest.raises(SystemExit) as exit_info:
        sample_digest.main([])
    assert exit_info.value.code == 2


def test_links() -> None:
    """C31 (rendering): the set of links, and none with a query string."""
    out = render()
    assert set(hrefs(out.html)) == {
        f"{WEB}/",
        f"{WEB}/alerts/{ALERT_ID}",
        f"{WEB}/settings/email",
        f"{WEB}/unsubscribe/tok",
    }
    assert all("?" not in h for h in hrefs(out.html))
    for url in re.findall(r"https?://\S+", out.text):
        assert "?" not in url
