"""Email templates (spec 28, door 5): Jinja2 under `templates/`.

An email named `x` is three files: `x.subject.txt`, `x.html` (extends `base.html`) and
`x.txt` (extends `base.txt`). The base layout adds the wordmark and the footer. HTML is
autoescaped; the subject and the plain-text part are not, because they are not HTML.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

TEMPLATES = Path(__file__).parent / "templates"


@dataclass(frozen=True)
class Footer:
    reason: str
    preferences_url: str
    unsubscribe_url: str
    mailing_address: str


@dataclass(frozen=True)
class Rendered:
    subject: str
    html: str
    text: str


@lru_cache
def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(enabled_extensions=("html",), default=False),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


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
