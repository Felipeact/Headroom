"""Send the mockup's weekly digest to one address, for checking it in mail clients (spec 30).

    uv run python -m app.modules.notifications.sample_digest --to you@example.com

It renders the `weekly_digest` email for Harbor Street Plumbing (the values of
`design/mockups/email-digest.dc.html`, synthetic data only) and sends it through the
configured sender (`EMAIL_SENDER`). Nothing is read from or written to the database.
"""

import argparse
import uuid
from collections.abc import Sequence
from typing import Any

from app.modules.notifications import rendering, senders
from app.settings import get_settings

SAMPLE: dict[str, Any] = {
    "business_name": "Harbor Street Plumbing",
    "currency": "CAD",
    "monday": "2026-09-28",
    "cash_on_hand_cents": 4230000,
    "minimum_cents": 500000,
    "low": {"balance_cents": 315000, "week_starts_on": "2026-11-09"},
    "alerts": [
        {
            "alert_id": "00000000-0000-4000-8000-000000000030",
            "minimum_cents": 500000,
            "lowest_week_starts_on": "2026-11-09",
            "fix_count": 3,
        }
    ],
    "changes": {
        "cash_change_cents": 412000,
        "low_change_cents": -60000,
        "new_payments": [
            {"name": "Acme Co", "amount_cents": 800000, "date": "2026-10-06"},
        ],
    },
}
REASON = (
    "You're getting this email because you're an owner of Harbor Street Plumbing"
    " on Headroom."
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send the sample weekly digest.")
    parser.add_argument("--to", required=True, help="the address to send it to")
    args = parser.parse_args(argv)
    settings = get_settings()
    rendered = rendering.render(
        "weekly_digest",
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
