"""Harbor Street Plumbing: the sample business of the mockups (spec 18, AD-068).

`generate(seed)` is pure: the same seed always gives the same data. Amounts are integer
cents in our sign (money in positive) and in CAD. The history runs 18 months up to
`REFERENCE_DAY`; `future` is the intended next 13 weeks, with the cash gap of the alert
mockup in the week of Nov 9. It is the target specs 21 to 25 reproduce, not a forecast.

Only the client payments' amounts, the supplier bills and the card purchases depend on
the seed. The balances, the expected payments and the future are the same for every seed.
Each client pays on a fixed day, so the forecast can date the money (feature 23a).
"""

import calendar
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.modules.bank_sync.labels import is_business_day

REFERENCE_DAY = date(2026, 9, 26)
FIRST_DAY = date(2025, 3, 26)
CURRENCY = "CAD"

PAYROLL_CENTS = -1_120_000
# The last payroll before the reference day; it repeats every 14 days.
LAST_PAYROLL = date(2026, 9, 18)
RENT_CENTS = -380_000
RENT_DAY = 15
SOFTWARE_CENTS = -64_000
SOFTWARE_DAY = 7
CARD_PAYMENT_DAY = 8
# The card owes September's purchases on the reference day, due Oct 8.
CARD_OWED_CENTS = 245_000

# Operating checking is topped up from savings so a day's payments leave this much...
OPERATING_FLOOR_CENTS = 300_000
# ...and swept back to about this on the 25th of each month; it ends at its balance.
OPERATING_TARGET_CENTS = 1_000_000
TRANSFER_STEP_CENTS = 50_000

# (client, day of month, base cents): each pays once a month, on that day or the next
# business day, within 2% of its base (AD-093). Clients pay only on the 16th to the 25th:
# an earlier day would land in the dashboard's next 14 days or in the week of Nov 9.
# Pine Ridge's odd cents are the calibration that ends the seed-0 forecast's
# week of Nov 9 at exactly $3,150.
MONTHLY_CLIENTS = (
    ("Acme Co", 16, 486_000),
    ("Northgate Dental", 18, 383_000),
    ("Pine Ridge Homes", 19, 604_966),
    ("Fairview Condos", 21, 448_000),
    ("Birch & Co", 23, 523_000),
    ("Delta Property Management", 24, 402_000),
)
CLIENT_NOISE = 0.02
# Delta's maintenance contract, paid in March, June, September and December.
QUARTERLY_CLIENT = ("Delta Property Management", 2, 1_300_000)
QUARTERLY_MONTHS = (3, 6, 9, 12)
SUPPLIER = "Coastal Supply Co"
SUPPLIER_BILLS_PER_MONTH = 2
SUPPLIER_BILL_CENTS = (80_000, 220_000)
CARD_MERCHANTS = (
    "Northside Fuel",
    "Bayline Hardware",
    "Metro Pipe & Fittings",
    "Quayside Auto Service",
)

TRANSFER_OUT_SAVINGS = ("TRANSFER_OUT", "TRANSFER_OUT_SAVINGS")
TRANSFER_OUT_ACCOUNT = ("TRANSFER_OUT", "TRANSFER_OUT_ACCOUNT_TRANSFER")
TRANSFER_IN = ("TRANSFER_IN", "TRANSFER_IN_ACCOUNT_TRANSFER")
CARD_PAYMENT = ("LOAN_PAYMENTS", "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT")
INCOME = ("INCOME", "INCOME_OTHER_INCOME")

Repeats = Literal["once", "every_3_months"]


@dataclass(frozen=True)
class SampleBusinessInfo:
    name: str
    province: str
    time_zone: str


@dataclass(frozen=True)
class SampleAccount:
    key: str
    name: str
    type: str
    mask: str
    currency: str
    # As the bank reports it: for a credit card, the amount owed.
    balance_cents: int
    available_cents: int | None


@dataclass(frozen=True)
class SampleBank:
    key: str
    institution_id: str
    institution_name: str
    accounts: tuple[SampleAccount, ...]


@dataclass(frozen=True)
class SampleTransaction:
    key: str
    account_key: str
    date: date
    amount_cents: int
    currency: str
    description: str
    counterparty: str | None
    category: str | None
    category_detailed: str | None


@dataclass(frozen=True)
class ExpectedPayment:
    description: str
    amount_cents: int
    currency: str
    date: date
    repeats: Repeats
    account_key: str


@dataclass(frozen=True)
class FutureItem:
    date: date
    amount_cents: int
    description: str


@dataclass(frozen=True)
class FutureWeek:
    # A Monday; the week runs to the Sunday after it.
    start: date
    end_cents: int


@dataclass(frozen=True)
class ReferenceFuture:
    opening_cents: int
    items: tuple[FutureItem, ...]
    weeks: tuple[FutureWeek, ...]


@dataclass(frozen=True)
class SampleBusiness:
    business: SampleBusinessInfo
    banks: tuple[SampleBank, ...]
    history: tuple[SampleTransaction, ...]
    expected_payments: tuple[ExpectedPayment, ...]
    future: ReferenceFuture


BUSINESS = SampleBusinessInfo(
    name="Harbor Street Plumbing", province="ON", time_zone="America/Toronto"
)
OPERATING = SampleAccount(
    "operating", "Operating checking", "checking", "2381", CURRENCY, 800_000, None
)
RESERVE = SampleAccount(
    "reserve", "Reserve savings", "savings", "9025", CURRENCY, 3_430_000, None
)
LINE_OF_CREDIT = SampleAccount(
    "line_of_credit", "Line of credit", "line_of_credit", "7702", CURRENCY, 0, 2_000_000
)
VISA = SampleAccount(
    "visa", "Business Visa", "credit_card", "5530", CURRENCY, CARD_OWED_CENTS, None
)
BANKS = (
    SampleBank(
        "harbor_community",
        "ins_sample_harbor_community",
        "Harbor Community Bank",
        (OPERATING, RESERVE, LINE_OF_CREDIT),
    ),
    SampleBank(
        "summit_federal",
        "ins_sample_summit_federal",
        "Summit Federal",
        (VISA,),
    ),
)
EXPECTED_PAYMENTS = (
    ExpectedPayment(
        "Acme Co, invoice 1042",
        800_000,
        CURRENCY,
        date(2026, 10, 6),
        "once",
        "operating",
    ),
    ExpectedPayment(
        "Coastal Supply Co, quarterly order",
        -1_450_000,
        CURRENCY,
        date(2026, 11, 12),
        "every_3_months",
        "operating",
    ),
    ExpectedPayment(
        "Birch & Co, invoice 1057",
        960_000,
        CURRENCY,
        date(2026, 11, 17),
        "once",
        "operating",
    ),
    ExpectedPayment(
        "Equipment lease deposit",
        -300_000,
        CURRENCY,
        date(2026, 12, 7),
        "once",
        "operating",
    ),
)
# Card payments after October's, and the supplier bills of a typical week after the
# dashboard's next 14 days, chosen so the week of Nov 9 ends at $3,150 and every other
# week at $17,650 or more (the alert mockup's gap and its three fixes).
FUTURE_CARD_PAYMENTS = ((date(2026, 11, 9), -230_966), (date(2026, 12, 8), -140_000))
FUTURE_SUPPLIER_FIRST_WEEK = date(2026, 10, 12)
TYPICAL_SUPPLIER_CENTS = -129_600
FUTURE_FIRST_WEEK = date(2026, 9, 28)
FUTURE_WEEKS = 13

Month = tuple[int, int]


def on_or_after_business_day(day: date) -> date:
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def _before_business_day(day: date) -> date:
    while not is_business_day(day):
        day -= timedelta(days=1)
    return day


def monthly_day(day_of_month: int, month: Month) -> date:
    """`day_of_month` of `month`, or the next business day when it is not one."""
    return on_or_after_business_day(date(month[0], month[1], day_of_month))


def payroll_day(friday: date) -> date:
    """A payroll Friday, or the business day before it when it is a holiday."""
    return _before_business_day(friday)


def _months(first: date, last: date) -> list[Month]:
    months, (year, month) = [], (first.year, first.month)
    while (year, month) <= (last.year, last.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _previous(month: Month) -> Month:
    return (month[0] - 1, 12) if month[1] == 1 else (month[0], month[1] - 1)


def _days(month: Month, *, last: date, business: bool) -> list[date]:
    """The days of `month` from `FIRST_DAY` up to `last`."""
    end = calendar.monthrange(*month)[1]
    days = [date(month[0], month[1], d) for d in range(1, end + 1)]
    return [
        d
        for d in days
        if FIRST_DAY <= d <= last and (not business or is_business_day(d))
    ]


def _split(rng: random.Random, total: int, count: int) -> list[int]:
    """`total` cents in `count` positive parts of random size that add up exactly."""
    weights = [rng.uniform(0.5, 1.5) for _ in range(count)]
    parts = [max(1, round(total * w / sum(weights))) for w in weights]
    parts[-1] += total - sum(parts)
    assert parts[-1] > 0
    return parts


@dataclass
class _Flow:
    account_key: str
    date: date
    amount_cents: int
    description: str
    counterparty: str | None
    category: tuple[str, str] | None
    kind: str


def _fixed_flows() -> list[_Flow]:
    flows = []
    friday = LAST_PAYROLL
    while friday >= FIRST_DAY:
        flows.append(
            _Flow(
                "operating",
                payroll_day(friday),
                PAYROLL_CENTS,
                "Payroll",
                "Payroll",
                None,
                "payroll",
            )
        )
        friday -= timedelta(days=14)
    for month in _months(FIRST_DAY, REFERENCE_DAY)[1:]:
        flows.append(
            _Flow(
                "operating",
                monthly_day(RENT_DAY, month),
                RENT_CENTS,
                "Rent",
                "Wharfside Properties",
                ("RENT_AND_UTILITIES", "RENT_AND_UTILITIES_RENT"),
                "rent",
            )
        )
        flows.append(
            _Flow(
                "operating",
                monthly_day(SOFTWARE_DAY, month),
                SOFTWARE_CENTS,
                "Software subscriptions",
                "Fieldworks Software",
                ("GENERAL_SERVICES", "GENERAL_SERVICES_OTHER_GENERAL_SERVICES"),
                "software",
            )
        )
    return flows


def _card_flows(rng: random.Random) -> list[_Flow]:
    """Purchases on the card, and on the 8th a payment of last month's purchases."""
    flows: list[_Flow] = []
    purchases: dict[Month, int] = defaultdict(int)
    months = _months(FIRST_DAY, REFERENCE_DAY)
    for month in months:
        days = _days(month, last=REFERENCE_DAY, business=False)
        count = len(days) // 3
        amounts = [rng.randint(2_500, 60_000) for _ in range(count)]
        if month == months[-1]:
            amounts = _split(rng, CARD_OWED_CENTS, count)
        for amount in amounts:
            merchant = rng.choice(CARD_MERCHANTS)
            flows.append(
                _Flow(
                    "visa",
                    rng.choice(days),
                    -amount,
                    merchant,
                    merchant,
                    (
                        "GENERAL_MERCHANDISE",
                        "GENERAL_MERCHANDISE_OTHER_GENERAL_MERCHANDISE",
                    ),
                    "card",
                )
            )
            purchases[month] += amount
    # The first payment also covers March's purchases from before the history starts.
    purchases[months[0]] += rng.randint(80_000, 180_000)
    for month in months[1:]:
        day = monthly_day(CARD_PAYMENT_DAY, month)
        amount = purchases[_previous(month)]
        flows.append(
            _Flow(
                "operating",
                day,
                -amount,
                "Business Visa payment",
                "Summit Federal",
                CARD_PAYMENT,
                "card-payment",
            )
        )
        flows.append(
            _Flow(
                "visa",
                day,
                amount,
                "Payment received",
                None,
                CARD_PAYMENT,
                "card-payment",
            )
        )
    return flows


def _supplier_and_client_flows(rng: random.Random) -> list[_Flow]:
    """Coastal Supply Co bills on random days, then each client's payments on its days."""
    flows: list[_Flow] = []
    last = REFERENCE_DAY - timedelta(days=1)
    for month in _months(FIRST_DAY, REFERENCE_DAY):
        days = _days(month, last=last, business=True)
        for _ in range(SUPPLIER_BILLS_PER_MONTH):
            flows.append(
                _Flow(
                    "operating",
                    rng.choice(days),
                    -rng.randint(*SUPPLIER_BILL_CENTS),
                    "Coastal Supply Co",
                    SUPPLIER,
                    (
                        "GENERAL_MERCHANDISE",
                        "GENERAL_MERCHANDISE_OTHER_GENERAL_MERCHANDISE",
                    ),
                    "supplier",
                )
            )
        payers = list(MONTHLY_CLIENTS)
        if month[1] in QUARTERLY_MONTHS:
            payers.append(QUARTERLY_CLIENT)
        for client, day_of_month, base in payers:
            amount = round(base * rng.uniform(1 - CLIENT_NOISE, 1 + CLIENT_NOISE))
            day = monthly_day(day_of_month, month)
            if FIRST_DAY <= day <= last:
                flows.append(
                    _Flow(
                        "operating",
                        day,
                        amount,
                        f"Payment from {client}",
                        client,
                        INCOME,
                        "client",
                    )
                )
    return flows


def _round_up(cents: int) -> int:
    return -(-cents // TRANSFER_STEP_CENTS) * TRANSFER_STEP_CENTS


def _transfer(day: date, amount: int) -> list[_Flow]:
    """Positive `amount` moves Operating to Reserve; negative moves it back."""
    if amount > 0:
        return [
            _Flow(
                "operating",
                day,
                -amount,
                "Transfer to Reserve savings",
                None,
                TRANSFER_OUT_SAVINGS,
                "transfer",
            ),
            _Flow(
                "reserve",
                day,
                amount,
                "Transfer from Operating checking",
                None,
                TRANSFER_IN,
                "transfer",
            ),
        ]
    return [
        _Flow(
            "reserve",
            day,
            amount,
            "Transfer to Operating checking",
            None,
            TRANSFER_OUT_ACCOUNT,
            "transfer",
        ),
        _Flow(
            "operating",
            day,
            -amount,
            "Transfer from Reserve savings",
            None,
            TRANSFER_IN,
            "transfer",
        ),
    ]


def _transfers(cash: list[_Flow]) -> list[_Flow]:
    """Moves between Operating and Reserve, walking forward from the history's start.

    Operating is topped up before a day whose payments would leave it under the floor,
    and swept towards the target on the 25th (or the business day before it). The last
    sweep, on the last business day before `REFERENCE_DAY`, lands it on its balance.
    """
    by_day: dict[date, int] = defaultdict(int)
    for flow in cash:
        by_day[flow.date] += flow.amount_cents
    out_by_day: dict[date, int] = defaultdict(int)
    for flow in cash:
        if flow.amount_cents < 0:
            out_by_day[flow.date] += flow.amount_cents
    net = sum(by_day.values())
    operating = OPERATING_TARGET_CENTS
    final_day = _before_business_day(REFERENCE_DAY)
    sweep_days = {
        _before_business_day(date(m[0], m[1], 25))
        for m in _months(FIRST_DAY, REFERENCE_DAY)
        if date(m[0], m[1], 25) >= FIRST_DAY
    } | {final_day}
    moves: list[_Flow] = []
    day = FIRST_DAY
    while day <= REFERENCE_DAY:
        if operating + out_by_day[day] < OPERATING_FLOOR_CENTS:
            amount = _round_up(OPERATING_FLOOR_CENTS - operating - out_by_day[day])
            moves += _transfer(day, -amount)
            operating += amount
        operating += by_day[day]
        if day in sweep_days:
            if day == final_day:
                amount = operating - OPERATING.balance_cents
            else:
                amount = round(
                    (operating - OPERATING_TARGET_CENTS) / TRANSFER_STEP_CENTS
                )
                amount = amount * TRANSFER_STEP_CENTS or TRANSFER_STEP_CENTS
            if amount:
                moves += _transfer(day, amount)
                operating -= amount
        day += timedelta(days=1)
    assert operating == OPERATING.balance_cents
    assert net  # the history moves cash; an empty one is a bug here
    return moves


def _history(rng: random.Random) -> tuple[SampleTransaction, ...]:
    fixed = _fixed_flows()
    card = _card_flows(rng)
    flows = fixed + card
    flows += _supplier_and_client_flows(rng)
    flows += _transfers([f for f in flows if f.account_key == "operating"])
    flows.sort(key=lambda f: (f.date, f.kind, f.account_key, f.amount_cents))
    counts: dict[tuple[date, str], int] = defaultdict(int)
    history = []
    for flow in flows:
        n = counts[(flow.date, flow.kind)] = counts[(flow.date, flow.kind)] + 1
        category, detailed = flow.category or (None, None)
        history.append(
            SampleTransaction(
                key=f"{flow.date.isoformat()}-{flow.kind}-{n:02d}",
                account_key=flow.account_key,
                date=flow.date,
                amount_cents=flow.amount_cents,
                currency=CURRENCY,
                description=flow.description,
                counterparty=flow.counterparty,
                category=category,
                category_detailed=detailed,
            )
        )
    return tuple(history)


def _future() -> ReferenceFuture:
    last = FUTURE_FIRST_WEEK + timedelta(weeks=FUTURE_WEEKS) - timedelta(days=1)
    items: list[FutureItem] = []
    friday = LAST_PAYROLL + timedelta(days=14)
    while friday <= last:
        items.append(FutureItem(payroll_day(friday), PAYROLL_CENTS, "Payroll"))
        friday += timedelta(days=14)
    for month in _months(REFERENCE_DAY + timedelta(days=1), last):
        for day_of_month, cents, name in (
            (RENT_DAY, RENT_CENTS, "Rent"),
            (SOFTWARE_DAY, SOFTWARE_CENTS, "Software subscriptions"),
        ):
            day = monthly_day(day_of_month, month)
            if REFERENCE_DAY < day <= last:
                items.append(FutureItem(day, cents, name))
    items.append(
        FutureItem(
            monthly_day(CARD_PAYMENT_DAY, (2026, 10)),
            -CARD_OWED_CENTS,
            "Business Visa payment",
        )
    )
    items += [
        FutureItem(d, c, "Business Visa payment") for d, c in FUTURE_CARD_PAYMENTS
    ]
    items += [
        FutureItem(p.date, p.amount_cents, p.description) for p in EXPECTED_PAYMENTS
    ]
    for month in _months(REFERENCE_DAY + timedelta(days=1), last):
        payers = list(MONTHLY_CLIENTS)
        if month[1] in QUARTERLY_MONTHS:
            payers.append(QUARTERLY_CLIENT)
        for client, day_of_month, base in payers:
            day = monthly_day(day_of_month, month)
            if REFERENCE_DAY < day <= last:
                items.append(FutureItem(day, base, f"Payment from {client}"))
    monday = FUTURE_SUPPLIER_FIRST_WEEK
    while monday <= last:
        items.append(
            FutureItem(monday, TYPICAL_SUPPLIER_CENTS, "Typical supplier bills")
        )
        monday += timedelta(weeks=1)
    items.sort(key=lambda i: (i.date, i.description))
    opening = OPERATING.balance_cents + RESERVE.balance_cents
    weeks = []
    for week in range(FUTURE_WEEKS):
        start = FUTURE_FIRST_WEEK + timedelta(weeks=week)
        end = start + timedelta(days=6)
        weeks.append(
            FutureWeek(
                start, opening + sum(i.amount_cents for i in items if i.date <= end)
            )
        )
    return ReferenceFuture(opening, tuple(items), tuple(weeks))


def generate(seed: int = 0) -> SampleBusiness:
    """Harbor Street Plumbing for `seed`: equal output for equal seeds, nothing else read."""
    rng = random.Random(seed)
    return SampleBusiness(
        business=BUSINESS,
        banks=BANKS,
        history=_history(rng),
        expected_payments=EXPECTED_PAYMENTS,
        future=_future(),
    )
