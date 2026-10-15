"""Email templates (spec 28, door 5): Jinja2 under `templates/`.

An email named `x` is three files: `x.subject.txt`, `x.html` (extends `base.html`) and
`x.txt` (extends `base.txt`). The base layout adds the wordmark and the footer. HTML is
autoescaped; the subject and the plain-text part are not, because they are not HTML.
Templates format money with `money` and plain dates with `day` (spec 29, door 4), which
follow `frontend/lib/format.ts`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.settings import get_settings

TEMPLATES = Path(__file__).parent / "templates"
MINUS_SIGN = "−"
# English names, whatever the server's locale is.
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class Footer:
    reason: str
    # None for a one-time email to someone with no preferences, such as an invitation.
    preferences_url: str | None
    unsubscribe_url: str | None
    mailing_address: str


@dataclass(frozen=True)
class Rendered:
    subject: str
    html: str
    text: str


def money(amount_cents: int, currency: str) -> str:
    """Whole dollars, as `formatMoney` writes them: "$14,500", "−$3,150", "$0".

    Only CAD: a cash gap is in the business's currency, and v1 businesses are Canadian.
    """
    if currency != "CAD":
        raise ValueError(f"emails format CAD only, got {currency}")
    # Round half away from zero in integer cents, like Math.round on the absolute value.
    dollars = (abs(amount_cents) + 50) // 100
    sign = MINUS_SIGN if amount_cents < 0 and dollars else ""
    return f"{sign}${dollars:,}"


def day(iso_date: str, weekday: bool = False) -> str:
    """A plain date, as `formatDate` writes it: "Nov 9", or "Thu, Nov 12" with the weekday."""
    found = date.fromisoformat(iso_date)
    text = f"{MONTHS[found.month - 1]} {found.day}"
    return f"{WEEKDAYS[found.weekday()]}, {text}" if weekday else text


@lru_cache
def environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(enabled_extensions=("html",), default=False),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["money"] = money
    env.filters["day"] = day
    return env


def render(
    template: str,
    params: Mapping[str, Any],
    *,
    first_name: str | None,
    footer: Footer,
) -> Rendered:
    """Render email `template` with its params, the recipient's first name and the footer."""
    env = environment()
    context = {
        **params,
        "web_url": get_settings().web_url,
        "first_name": first_name,
        "reason": footer.reason,
        "preferences_url": footer.preferences_url,
        "unsubscribe_url": footer.unsubscribe_url,
        "mailing_address": footer.mailing_address,
    }
    subject = env.get_template(f"{template}.subject.txt").render(context).strip()
    context["subject"] = subject
    return Rendered(
        subject=subject,
        html=env.get_template(f"{template}.html").render(context),
        text=env.get_template(f"{template}.txt").render(context),
    )
