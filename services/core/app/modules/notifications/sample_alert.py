"""Send the mockup's alert email to one address, for checking it in mail clients (spec 29).

    uv run python -m app.modules.notifications.sample_alert --to you@example.com

It renders the `alert` email for Harbor Street Plumbing's sample alert (the values of
`design/mockups/email-alert.dc.html`, synthetic data only) and sends it through the
configured sender (`EMAIL_SENDER`). Nothing is read from or written to the database.
"""

import argparse
import uuid
from collections.abc import Sequence
from typing import Any

from app.modules.notifications import rendering, senders
from app.settings import get_settings

SAMPLE: dict[str, Any] = {
    "alert_id": "00000000-0000-4000-8000-000000000029",
    "business_name": "Harbor Street Plumbing",
    "change": "created",
    "currency": "CAD",
    "minimum_cents": 500000,
    "lowest_balance_cents": 315000,
    "lowest_week_starts_on": "2026-11-09",
    "causes": [
        {"name": "Coastal Supply Co", "amount_cents": 1450000, "date": "2026-11-12"},
        {"name": "Payroll", "amount_cents": 1120000, "date": "2026-11-13"},
    ],
    "top_fix": {
        "kind": "pay_early",
        "name": "Birch & Co",
        "amount_cents": 960000,
        "keeps_above": True,
    },
    "fix_count": 3,
}
REASON = (
    "You're getting this email because you're an owner of Harbor Street Plumbing"
    " on Headroom."
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send the sample alert email.")
    parser.add_argument("--to", required=True, help="the address to send it to")
    args = parser.parse_args(argv)
    settings = get_settings()
    rendered = rendering.render(
        "alert",
        SAMPLE,
        first_name="Dana",
        footer=rendering.Footer(
            reason=REASON,
            preferences_url=f"{settings.web_url}/settings/email",
            unsubscribe_url=f"{settings.web_url}/unsubscribe/sample",
            mailing_address=settings.email_mailing_address,
        ),
    )
    senders.get_email_sender().send(
        senders.OutgoingEmail(
            to=args.to,
            sender=settings.email_from,
            subject=rendered.subject,
            html=rendered.html,
            text=rendered.text,
            headers={},
            idempotency_key=str(uuid.uuid4()),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
