"""Spec 29: the alert email against its mockup (C11-C21, C23, C25).

The sample is the email sent for Harbor Street's alert (`tests/alert_email_support.py`);
the other cases render the same params with one value changed.
"""

import copy
import re
from datetime import date
from html.parser import HTMLParser
from typing import Any

import pytest

from app.modules.alerts import service as alerts_service
from app.modules.notifications import rendering, sample_alert, senders
from app.modules.notifications import service as notifications_service
from app.modules.notifications.senders import OutgoingEmail
from tests.alert_email_support import WEB, SampleEmail, send_sample
from tests.email_support import FakeEmailSender
from tests.test_alert_emails import view

FOOTER = rendering.Footer(
    reason="You're getting this email because you're an owner of Harbor Street"
    " Plumbing on Headroom.",
    preferences_url=f"{WEB}/settings/email",
    unsubscribe_url=f"{WEB}/unsubscribe/tok",
    mailing_address="1 Test St, Toronto ON M5V 1A1",
)


@pytest.fixture(scope="module")
def sample(migrated_database: None) -> SampleEmail:
    return send_sample()


@pytest.fixture(scope="module")
def email(sample: SampleEmail) -> OutgoingEmail:
    (sent,) = sample.sent
    return sent


def render(
    sample: SampleEmail, first_name: str | None = "Dana", **changes: Any
) -> rendering.Rendered:
    params = copy.deepcopy(sample.params)
    params.update(changes)
    return rendering.render("alert", params, first_name=first_name, footer=FOOTER)


class Page(HTMLParser):
    """The visible text of each element of interest, and every link."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.texts: dict[str, list[str]] = {}
        self.order: list[str] = []
        self.hrefs: list[str] = []
        self._open: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href") or "")
        if tag in ("h1", "li", "p", "a", "td", "div", "strong"):
            self._open.append((tag, []))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == tag:
                name, parts = self._open.pop(i)
                text = re.sub(r"\s+", " ", "".join(parts)).strip()
                self.texts.setdefault(name, []).append(text)
                self.order.append(text)
                break

    def handle_data(self, data: str) -> None:
        for _, parts in self._open:
            parts.append(data)


def page(html: str) -> Page:
    found = Page()
    found.feed(html)
    return found


def content(html: str) -> str:
    """The email's own block: between the wordmark and the footer."""
    return html.split("Headroom</div>", 1)[1].split("You&#39;re getting", 1)[0]


def test_sample_heading(email: OutgoingEmail) -> None:
    """C11."""
    heading = "Cash falls below your $5,000 minimum the week of Nov 9"
    assert email.subject == heading
    assert page(email.html).texts["h1"] == [heading]
    lines = email.text.splitlines()
    assert lines[lines.index("Cash gap") + 1] == heading


def test_label_by_change(sample: SampleEmail) -> None:
    """C12."""
    for change, label in (("created", "Cash gap"), ("updated", "Cash gap got bigger")):
        rendered = render(sample, change=change)
        found = page(content(rendered.html))
        assert found.texts["div"][0] == label
        assert found.order.index(label) < found.order.index(rendered.subject)
        assert label in rendered.text.splitlines()


def test_greeting(email: OutgoingEmail, sample: SampleEmail) -> None:
    """C13."""
    assert (
        '<p style="margin: 0 0 20px; font-size: 16px; line-height: 1.55;">Hi Dana, the'
        " forecast for Harbor Street Plumbing shows cash dropping to"
        " <strong>$3,150</strong> in the week of Nov 9.</p>"
    ) in email.html
    nameless = render(sample, first_name=None)
    assert (
        "The forecast for Harbor Street Plumbing shows cash dropping to $3,150 in the"
        " week of Nov 9."
    ) in nameless.text
    assert "Hi" not in content(nameless.html)


def test_sample_causes(email: OutgoingEmail) -> None:
    """C14."""
    found = page(content(email.html))
    assert "What's causing it" in found.texts["div"]
    assert found.texts["li"] == [
        "Coastal Supply Co, $14,500, on Thu, Nov 12",
        "Payroll, $11,200, on Fri, Nov 13",
    ]


FIXES = [
    (
        "pay_early",
        "Birch & Co",
        960000,
        "ask Birch & Co to pay their $9,600 invoice a week early.",
    ),
    (
        "move_payment",
        "Coastal Supply Co",
        1450000,
        "move the $14,500 payment to Coastal Supply Co a week later.",
    ),
    ("draw_credit", "Line of credit", 200000, "draw $2,000 from your Line of credit."),
    (
        "financing",
        "",
        200000,
        "arrange $2,000 of short-term financing for the length of the gap.",
    ),
]
KEEPS = "That keeps you above your minimum."


def fix_line(rendered: rendering.Rendered) -> tuple[str, str]:
    (html_line,) = [
        t for t in page(content(rendered.html)).texts["td"] if "Top fix:" in t
    ]
    (text_line,) = [t for t in rendered.text.splitlines() if t.startswith("Top fix:")]
    return html_line, text_line


@pytest.mark.parametrize(("kind", "name", "amount", "expected"), FIXES)
def test_top_fix(
    sample: SampleEmail, kind: str, name: str, amount: int, expected: str
) -> None:
    """C15: every kind; keeps-above from the builder at equal, above and one below."""
    fix = {"kind": kind, "name": name, "amount_cents": amount, "keeps_above": False}
    for line in fix_line(render(sample, top_fix=fix)):
        assert line == f"Top fix: {expected}"
    fix["keeps_above"] = True
    for line in fix_line(render(sample, top_fix=fix)):
        assert line == f"Top fix: {expected} {KEEPS}"


def test_top_fix_keeps_above_edges() -> None:
    """C15: `new_lowest_balance_cents` against `minimum_cents` (500000)."""

    def keeps(new_lowest: int) -> bool:
        fix = alerts_service.AlertFixView(
            kind="pay_early",
            amount_cents=960000,
            currency="CAD",
            original_date=None,
            repay_on=None,
            date=date(2026, 11, 10),
            description="Birch & Co, invoice 1057",
            counterparty=None,
            available_cents=None,
            new_lowest_balance_cents=new_lowest,
        )
        params = notifications_service.alert_params(
            view([], [fix]), business_name="Acme", change="created"
        )
        return bool(params["top_fix"]["keeps_above"])

    assert keeps(500000) is True
    assert keeps(500001) is True
    assert keeps(499999) is False


def test_sample_top_fix(email: OutgoingEmail) -> None:
    """C15: the sample shows the pay_early fix with the keeps-above sentence."""
    html_line = [t for t in page(content(email.html)).texts["td"] if "Top fix:" in t]
    assert html_line == [
        f"Top fix: ask Birch & Co to pay their $9,600 invoice a week early. {KEEPS}"
    ]


def test_no_fix(sample: SampleEmail) -> None:
    """C16."""
    rendered = render(sample, top_fix=None, fix_count=0)
    assert "Top fix:" not in rendered.html
    assert "Top fix:" not in rendered.text
    assert "#FFF4E2" not in rendered.html


@pytest.mark.parametrize(
    ("count", "label"),
    [
        (0, "See details"),
        (1, "See the fix"),
        (2, "See all 2 fixes"),
        (3, "See all 3 fixes"),
    ],
)
def test_button(sample: SampleEmail, count: int, label: str) -> None:
    """C17."""
    rendered = render(sample, fix_count=count)
    found = page(content(rendered.html))
    assert found.hrefs == [f"{WEB}/alerts/{sample.alert_id}"]
    assert found.texts["a"] == [label]


def test_filters() -> None:
    """C18: money and day, as frontend/lib/format.ts writes them."""
    money = rendering.money
    assert money(1450000, "CAD") == "$14,500"
    assert money(315049, "CAD") == "$3,150"
    assert money(315050, "CAD") == "$3,151"
    assert money(-315000, "CAD") == "−$3,150"
    assert money(0, "CAD") == "$0"
    assert money(-49, "CAD") == "$0"
    assert money(-50, "CAD") == "−$1"
    with pytest.raises(ValueError):
        money(100, "USD")
    assert rendering.day("2026-11-09") == "Nov 9"
    assert rendering.day("2026-11-12", weekday=True) == "Thu, Nov 12"


def test_filters_unsigned_params(sample: SampleEmail) -> None:
    """C18: the builder stores cause and fix amounts unsigned."""
    assert [c["amount_cents"] for c in sample.params["causes"]] == [1450000, 1120000]
    assert sample.params["top_fix"]["amount_cents"] == 960000


def test_negative_low(sample: SampleEmail) -> None:
    """C18: a low below zero keeps its sign."""
    rendered = render(sample, lowest_balance_cents=-315000)
    assert "cash dropping to <strong>−$3,150</strong>" in rendered.html


def test_plain_text_order(email: OutgoingEmail, sample: SampleEmail) -> None:
    """C19."""
    lines = email.text.splitlines()
    expected = [
        "Cash gap",
        "Cash falls below your $5,000 minimum the week of Nov 9",
        (
            "Hi Dana, the forecast for Harbor Street Plumbing shows cash dropping to"
            " $3,150 in the week of Nov 9."
        ),
        "What's causing it",
        "- Coastal Supply Co, $14,500, on Thu, Nov 12",
        "- Payroll, $11,200, on Fri, Nov 13",
        f"Top fix: ask Birch & Co to pay their $9,600 invoice a week early. {KEEPS}",
    ]
    positions = [lines.index(line) for line in expected]
    assert positions == sorted(positions)
    url = [
        i for i, line in enumerate(lines) if f"{WEB}/alerts/{sample.alert_id}" in line
    ]
    assert url and url[0] > positions[-1]


def test_email_safe_html(email: OutgoingEmail) -> None:
    """C20."""
    lowered = email.html.lower()
    for banned in ("display: flex", "display:flex", "grid", "position:"):
        assert banned not in lowered
    for tag in ("<link", "<script", "<img"):
        assert tag not in lowered
    button = re.search(
        r'<td bgcolor="#1D4E89"[^>]*>\s*<a [^>]*style="([^"]*)"', email.html
    )
    assert button is not None
    assert "color: #FFFFFF" in button.group(1)


def test_mockup_colours(email: OutgoingEmail) -> None:
    """C21."""
    block = content(email.html)
    assert re.search(r'<div style="[^"]*color: #7A4300;[^"]*">Cash gap</div>', block)
    box = re.search(r'<td style="([^"]*)"><strong>Top fix:', block)
    assert box is not None
    assert "background: #FFF4E2" in box.group(1)
    assert "#F0D3A4" in box.group(1)
    assert "color: #3D2E1C" in box.group(1)
    assert 'bgcolor="#1D4E89"' in block


def test_links(email: OutgoingEmail, sample: SampleEmail) -> None:
    """C25: the email's links, from the delivered email (real token)."""
    hrefs = page(email.html).hrefs
    alert = f"{WEB}/alerts/{sample.alert_id}"
    prefs = f"{WEB}/settings/email"
    unsubscribe = [h for h in hrefs if h.startswith(f"{WEB}/unsubscribe/")]
    assert len(unsubscribe) >= 1
    assert set(hrefs) == {alert, prefs, unsubscribe[0]}
    assert re.fullmatch(rf"{re.escape(WEB)}/unsubscribe/[A-Za-z0-9_-]+", unsubscribe[0])
    assert all("?" not in h for h in hrefs)
    for url in re.findall(r"https?://\S+", email.text):
        assert "?" not in url


def test_sample_alert_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """C23."""
    sender = FakeEmailSender()
    monkeypatch.setattr(senders, "get_email_sender", lambda: sender)
    assert sample_alert.main(["--to", "someone@example.test"]) == 0
    (sent,) = sender.sent
    assert sent.to == "someone@example.test"
    assert sent.subject == "Cash falls below your $5,000 minimum the week of Nov 9"
    assert "Coastal Supply Co, $14,500, on Thu, Nov 12" in sent.html
    with pytest.raises(SystemExit) as exit_info:
        sample_alert.main([])
    assert exit_info.value.code == 2
