"""The params of a `weekly_digest` email (spec 30, door 3): JSON values, no account data."""

from datetime import date
from typing import Any

from app.modules.alerts.service import AlertView
from app.modules.forecasting.service import (
    AddedPaymentView,
    ForecastView,
    PinnedForecastView,
)

# The most new expected payments the digest names.
MAX_NEW_PAYMENTS = 3


def digest_params(
    *,
    business_name: str,
    monday: date,
    minimum_cents: int,
    forecast: ForecastView,
    open_alerts: list[AlertView],
    last_week: PinnedForecastView | None,
    new_payments: list[AddedPaymentView],
) -> dict[str, Any]:
    """The params of the digest for the business-local `monday`.

    The projected low is the lowest end-of-week balance of the forecast's weeks, the
    earlier week on a tie. `changes` compares the forecast with the one pinned to last
    Monday, and is None when there was none. `new_payments` is already largest first.
    """
    low = min(forecast.weeks, key=lambda w: w.end_balance_cents)
    changes = None
    if last_week is not None:
        changes = {
            "cash_change_cents": forecast.opening_balance_cents
            - last_week.opening_balance_cents,
            "low_change_cents": low.end_balance_cents - last_week.low_balance_cents,
            "new_payments": [
                {
                    "name": p.description,
                    "amount_cents": p.amount_cents,
                    "date": p.next_date.isoformat(),
                }
                for p in new_payments[:MAX_NEW_PAYMENTS]
            ],
        }
    return {
        "business_name": business_name,
        "currency": forecast.currency,
        "monday": monday.isoformat(),
        "cash_on_hand_cents": forecast.opening_balance_cents,
        "minimum_cents": minimum_cents,
        "low": {
            "balance_cents": low.end_balance_cents,
            "week_starts_on": low.starts_on.isoformat(),
        },
        "alerts": [
            {
                "alert_id": str(a.id),
                "minimum_cents": a.minimum_cents,
                "lowest_week_starts_on": a.lowest_week_starts_on.isoformat(),
                "fix_count": len(a.fixes),
            }
            for a in open_alerts
        ],
        "changes": changes,
    }
