"""Transaction labels (spec 16): which transactions are transfers or credit activity.

Pure functions over a business's transactions; `service` loads them and stores the result.
Amounts are our sign: money in positive, money out negative.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta

import holidays
from holidays.constants import GOVERNMENT, PUBLIC

# Both halves of a transfer must be at most this many business days apart, and an
# outgoing transfer stays in transit for this many business days after its date.
WINDOW_BUSINESS_DAYS = 3
# A gap this many calendar days wide always holds more than the window's business days.
_WINDOW_CALENDAR_DAYS = 14

# Canadian federal statutory holidays; banks are federally regulated (AD-059).
_HOLIDAYS = holidays.country_holidays("CA", categories=(GOVERNMENT, PUBLIC))

CARD_PAYMENT_DETAILED = "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"
# A credit on a card is a payment unless Plaid says it is something else (a refund).
CARD_PAYMENT_CATEGORIES = ("LOAN_PAYMENTS", "TRANSFER_IN")
IN_TRANSIT_DETAILED = ("TRANSFER_OUT_ACCOUNT_TRANSFER", "TRANSFER_OUT_SAVINGS")


@dataclass(frozen=True)
class Item:
    """What labelling needs to know about one transaction."""

    id: uuid.UUID
    account_id: uuid.UUID
    amount_cents: int
    currency: str
    date: date
    category: str | None
    category_detailed: str | None


@dataclass(frozen=True)
class Label:
    label: str
    linked_transaction_id: uuid.UUID | None = None


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in _HOLIDAYS


def business_days_between(earlier: date, later: date) -> int:
    """How many business days fall after `earlier`, up to and including `later`."""
    count, day = 0, earlier
    while day < later:
        day += timedelta(days=1)
        count += is_business_day(day)
    return count


def add_business_days(day: date, count: int) -> date:
    while count > 0:
        day += timedelta(days=1)
        count -= is_business_day(day)
    return day


def _pair_label(out_type: str, in_type: str) -> str:
    if "credit_card" in (out_type, in_type):
        return "card_payment"
    if out_type == "line_of_credit":
        return "credit_draw"
    if in_type == "line_of_credit":
        return "credit_repayment"
    return "internal_transfer"


def _is_card_payment(item: Item) -> bool:
    """A credit on a card that is a payment, not a refund."""
    return item.amount_cents > 0 and (
        item.category is None or item.category in CARD_PAYMENT_CATEGORIES
    )


def _can_pair(
    out: Item, incoming: Item, account_types: Mapping[uuid.UUID, str]
) -> bool:
    """Whether two opposite amounts may be the two halves of one move.

    A card half must be a payment arriving on the card: a purchase or a refund on the
    card never pairs with an unrelated cash amount (spec 16 AC 27).
    """
    if out.account_id == incoming.account_id:
        return False
    if account_types[out.account_id] == "credit_card":
        return False
    return account_types[incoming.account_id] != "credit_card" or _is_card_payment(
        incoming
    )


def _unpaired_label(item: Item, account_type: str, today: date) -> str:
    amount = item.amount_cents
    if account_type == "credit_card":
        if _is_card_payment(item):
            return "card_payment"
        return "card_purchase" if amount != 0 else "normal"
    if account_type == "line_of_credit":
        if amount < 0:
            return "credit_draw"
        return "credit_repayment" if amount > 0 else "normal"
    if amount < 0 and item.category_detailed == CARD_PAYMENT_DETAILED:
        return "card_payment"
    if (
        amount < 0
        and item.category_detailed in IN_TRANSIT_DETAILED
        and today <= add_business_days(item.date, WINDOW_BUSINESS_DAYS)
    ):
        return "in_transit"
    return "normal"


def _pairs(
    items: Iterable[Item], account_types: Mapping[uuid.UUID, str]
) -> list[tuple[Item, Item]]:
    """Each transaction's other half, at most one each.

    Halves have opposite amounts in the same currency, on different accounts
    (`_can_pair`), at most `WINDOW_BUSINESS_DAYS` apart in either order. Closest first,
    then earliest, then lowest ID.
    """
    groups: dict[tuple[str, int], tuple[list[Item], list[Item]]] = defaultdict(
        lambda: ([], [])
    )
    for item in items:
        if item.amount_cents != 0:
            outs, ins = groups[(item.currency, abs(item.amount_cents))]
            (outs if item.amount_cents < 0 else ins).append(item)

    candidates: list[tuple[int, date, date, uuid.UUID, uuid.UUID, Item, Item]] = []
    for outs, ins in groups.values():
        for out in outs:
            for incoming in ins:
                if not _can_pair(out, incoming, account_types):
                    continue
                earlier, later = sorted((out.date, incoming.date))
                if (later - earlier).days > _WINDOW_CALENDAR_DAYS:
                    continue
                apart = business_days_between(earlier, later)
                if apart <= WINDOW_BUSINESS_DAYS:
                    candidates.append(
                        (
                            apart,
                            out.date,
                            incoming.date,
                            out.id,
                            incoming.id,
                            out,
                            incoming,
                        )
                    )
    candidates.sort(key=lambda c: c[:5])

    used: set[uuid.UUID] = set()
    pairs: list[tuple[Item, Item]] = []
    for *_, out, incoming in candidates:
        if out.id not in used and incoming.id not in used:
            used.update((out.id, incoming.id))
            pairs.append((out, incoming))
    return pairs


def label_all(
    items: Iterable[Item], account_types: Mapping[uuid.UUID, str], today: date
) -> dict[uuid.UUID, Label]:
    """The label and link of every transaction of one business, on `today`.

    `account_types` maps each account ID to its type; `today` is the business-local
    date, which decides whether an unmatched outgoing transfer is still in transit.
    """
    items = list(items)
    result: dict[uuid.UUID, Label] = {}
    for out, incoming in _pairs(items, account_types):
        label = _pair_label(
            account_types[out.account_id], account_types[incoming.account_id]
        )
        result[out.id] = Label(label, incoming.id)
        result[incoming.id] = Label(label, out.id)
    for item in items:
        if item.id not in result:
            result[item.id] = Label(
                _unpaired_label(item, account_types[item.account_id], today)
            )
    return result
