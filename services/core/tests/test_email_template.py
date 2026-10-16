"""Spec 28: the base email layout (C10-C12, C14)."""

import re
from html.parser import HTMLParser

import pytest

from app.modules.notifications import rendering
from tests.email_support import REASON, with_test_templates

TOKEN = "tok_" + "a" * 39
FOOTER = rendering.Footer(
    reason=REASON,
    preferences_url="https://app.example.test/settings/email",
    unsubscribe_url=f"https://app.example.test/unsubscribe/{TOKEN}",
    mailing_address="1 Test St, Toronto ON M5V 1A1",
)
SANS = "-apple-system, 'Segoe UI', Helvetica, sans-serif"


@pytest.fixture(autouse=True)
def test_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    env = with_test_templates()
    monkeypatch.setattr(rendering, "environment", lambda: env)


def render(**params: str) -> rendering.Rendered:
    values = {"heading": "Cash gap", "body": "Cash falls."} | params
    return rendering.render("test_message", values, first_name="Dana", footer=FOOTER)


class Text(HTMLParser):
    """The visible text of the body, in order, and every link."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "title"):
            self._skip += 1
        if tag == "a":
            self._href = dict(attrs).get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "title"):
            self._skip -= 1
        if tag == "a":
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._skip or not data.strip():
            return
        self.parts.append(data.strip())
        if self._href is not None:
            self.links.append((data.strip(), self._href))


def visible(html: str) -> Text:
    parser = Text()
    parser.feed(html)
    return parser


def test_layout() -> None:
    """C10: one 600 px column, the wordmark first in Georgia, the house colours."""
    html = render().html

    assert 'width="600"' in html
    assert "width: 600px" in html
    assert visible(html).parts[0] == "Headroom"
    wordmark = re.search(r'<div style="([^"]*)">Headroom</div>', html)
    assert wordmark is not None
    assert "font-family: Georgia, serif" in wordmark.group(1)
    assert re.search(r"h1[^{]*\{[^}]*font-family: Georgia, serif", html)
    assert f"font-family: {SANS}" in html
    assert "background: #F5F3EE" in html
    assert "background: #FFFFFF" in html
    assert "color: #16202B" in html


def test_footer() -> None:
    """C11: reason, the two links, then the mailing address, in that order."""
    page = visible(render().html)

    footer = page.parts[page.parts.index(REASON) :]
    assert footer == [
        REASON,
        "Email preferences",
        "·",
        "Unsubscribe",
        "Headroom · 1 Test St, Toronto ON M5V 1A1",
    ]
    assert page.links == [
        ("Email preferences", "https://app.example.test/settings/email"),
        ("Unsubscribe", f"https://app.example.test/unsubscribe/{TOKEN}"),
    ]


def test_plain_text() -> None:
    """C12: the text part has the content and the footer, links written out."""
    text = render().text

    lines = [line for line in text.splitlines() if line.strip()]
    for expected in (
        "Cash gap",
        "Hi Dana, Cash falls.",
        REASON,
        "Email preferences: https://app.example.test/settings/email",
        f"Unsubscribe: https://app.example.test/unsubscribe/{TOKEN}",
        "Headroom · 1 Test St, Toronto ON M5V 1A1",
    ):
        assert expected in lines
    assert lines.index(REASON) < lines.index("Headroom · 1 Test St, Toronto ON M5V 1A1")
    assert "<" not in text


def test_escapes_params() -> None:
    """C14: a param is escaped in HTML and left as written in the text part."""
    rendered = render(body="<b>Acme</b> & Co")

    assert "&lt;b&gt;Acme&lt;/b&gt; &amp; Co" in rendered.html
    assert "<b>" not in rendered.html
    assert "<b>Acme</b> & Co" in rendered.text
