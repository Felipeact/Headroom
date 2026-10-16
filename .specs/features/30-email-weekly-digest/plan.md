# Spec 30: Weekly digest

## Problem

An owner whose forecast is healthy has no reason to open Headroom, and an owner whose forecast changed has no way to learn that without logging in. Alerts (spec 29) cover only the moment a gap appears or grows. They say nothing in a week when cash is fine, or when cash on hand moved, or when a new expected payment was added. The spec states the goal as "so most weeks owners don't need to log in at all" (`context/specs/30-email-weekly-digest.md`). Today no weekly email is sent, and `email_preferences.weekly_digest` and the `weekly_digest` delivery kind exist with nothing using them.

When this ships, every owner of a business with a forecast gets one email on Monday morning, during the 8 AM hour in the business's own time zone. It shows cash on hand, the projected low, the open alerts or an "all clear", and what changed since last week.

## Flow

This reuses the hourly job runner (AD-085, `JOBS`), the pinned forecasts of spec 22 (AD-084) as last week's baseline, the alert reads of spec 24, and the email pipeline of spec 28 (`request_email` → commit → `deliver`, dedup index, preferences, retries, footer: AD-106 to AD-111) with the `money` and `day` filters (AD-115). It adds one job, one digest builder, one template.

1. Railway's hourly `jobs` service (exists) runs `app.jobs.run_due`, which calls `weekly_digest(now)` (door 1) from `JOBS`.
2. `weekly_digest` (new job, door 1) reads every business's time zone through `accounts.service` (exists as a module, new read in placement) and keeps the businesses whose local time is Monday in the 8 o'clock hour.
3. For each such business, in its own transaction, `notifications.service` (exists) builds the digest params (door 3) from `forecasting.service` (exists: the latest forecast, the minimum balance, new reads for last Monday's pin and for expected payments added since), `alerts.service.list_alerts` (exists, `open`) and `accounts.service` (exists: business name, owners).
4. For each owner, `notifications.service.request_email` (exists) records a pending `weekly_digest` delivery with dedup key door 2. A user who turned the digest off gets a `skipped` row. Then one commit.
5. After the commit, `notifications.service.deliver` (exists) runs for each new delivery. It renders `weekly_digest.subject.txt`, `weekly_digest.html` and `weekly_digest.txt` over `base.*`, then sends. A retryable failure stays `pending` for the `email_retries` job (exists).

## Impact

| Front | What changes |
| --- | --- |
| jobs | `JOBS` gains `weekly_digest` after `forecast_accuracy` (this week's pin exists first) and before `email_retries`. The job's counts `digests_requested` and `digests_failed` join `jobs.run_finished`, so the names must not collide with the other jobs' keys |
| latency | In the Monday 8 AM run, the job calls Clerk and Resend inline, once per owner, for every business in that zone. A run is one hour of the day; v1 has one owner per business |
| forecasting | `forecasting.service` gains a public read of the forecast pinned to a given Monday (opening balance, projected low) and a read of the expected payments created since a moment. `ExpectedPaymentView` is unchanged; the new read returns its own small view |
| accounts | `accounts.service` gains a public read of every business's ID and time zone, for jobs that act on all businesses |
| notifications | A third template set (`weekly_digest.*`) and a builder for its params. `rendering.environment()` and the `money` and `day` filters are reused, not changed |
| copy | The digest repeats the alert wording ("Cash falls below your {minimum} minimum the week of {week}") from `_alert_copy.jinja`. The new copy lives in Jinja templates, because emails are rendered by the API and the jobs process, which have no Node (AD-110) |
| tests | Spec 29 added an autouse fake Clerk in `tests/conftest.py`; the digest tests use spec 28's `mail` fixture the same way |
| tooling | `uv run python -m app.modules.notifications.sample_digest --to <address>` sends the mockup's sample digest through the configured sender, for the manual check in AC 27 |
| stored data | Nothing to migrate. `email_deliveries.kind` already allows `weekly_digest`, and `email_preferences.weekly_digest` already exists |

## Relations

`None - no stored-data shape change`

## Surface

`None - nothing consumed outside`. The email is the outside surface, and it's covered in `## Observable`. Its links use only `/`, `/alerts/{alert_id}`, `/settings/email` and `/unsubscribe/{token}`, which AD-105, AD-108 and AD-109 already fix.

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. When a digest is due | `app/jobs/weekly_digest.py`: `weekly_digest(now: datetime) -> dict[str, int]`; `JOBS = (nightly_bank_sync, forecast_accuracy, weekly_digest, email_retries)`. A business is due when `now.astimezone(ZoneInfo(business.time_zone))` has `weekday() == 0` and `hour == 8`. Returns `{"digests_requested": n, "digests_failed": n}` | A "last sent" column or table per business: a schema and a state to keep right, where the dedup key (door 2) already makes a second run harmless. Sending on the first run after 8:00 (catch-up): the spec says "during the 8 AM hour", and a catch-up would send at 3 PM after an outage |
| 2. The dedup key | `weekly_digest:{business_id}:{local Monday as YYYY-MM-DD}`, unique per user under `uq_email_deliveries_dedup_key_user_id` (AD-106) | `weekly_digest:{iso year}-W{week}` without the business: a user who belongs to two businesses (spec 31) would get only one digest. `weekly_digest:{now}`: every run in the hour would send again |
| 3. Params stored in `email_deliveries.params` | `{"business_name": str, "currency": str, "monday": "YYYY-MM-DD", "cash_on_hand_cents": int, "minimum_cents": int, "low": {"balance_cents": int, "week_starts_on": "YYYY-MM-DD"}, "alerts": [{"alert_id": str, "minimum_cents": int, "lowest_week_starts_on": "YYYY-MM-DD", "fix_count": int}], "changes": null \| {"cash_change_cents": int, "low_change_cents": int, "new_payments": [{"name": str, "amount_cents": int, "date": "YYYY-MM-DD"}]}}` | Storing rendered HTML (the template could not change for retries, and the HTML holds unsubscribe URLs). Storing `ForecastView` and `AlertView` whole: their `account_id`, `source_id` and item lists would go into a table that never needs them. Retries render stored params hours later, so the template must keep reading this shape |
| 4. Last week's baseline | The forecast pinned to last local Monday (`forecast_pins`, AD-084), read through a new public function of `forecasting.service`. No pin means no `changes` | Rebuilding last week from transactions: it cannot reproduce what the forecast said then, only what happened. A digest-only snapshot table: a schema, when pins already hold exactly this |

- Nothing else in this change is hard to reverse.

## Criteria

### S1: One digest per owner, Monday in the 8 AM hour (P1)

Every owner of a business that has a forecast gets exactly one digest in the 8 AM hour of Monday in the business's own time zone.

**Acceptance Criteria**

1. WHEN `weekly_digest(now)` runs and a business's local time at `now` is Monday between 08:00 and 08:59 THEN the system SHALL record one `weekly_digest` delivery for each owner of the business. Each delivery has dedup key `weekly_digest:{business_id}:{local Monday}`, template `weekly_digest` and reason "You're getting this email because you're an owner of {business name} on Headroom." The system SHALL deliver each one after the commit.
2. IF a business's local time at `now` is not Monday in the 8 o'clock hour, for example Monday 07:59, Monday 09:00 or Sunday 08:30, THEN the system SHALL record no delivery for it.
3. WHEN `now` is 11:00 UTC on Monday 2026-10-26 THEN the system SHALL record deliveries for America/St_Johns businesses (08:30 local) and for no other zone.
4. WHEN `now` is 12:00 UTC on Monday 2026-10-26 THEN the system SHALL record deliveries for America/Toronto businesses (08:00 local) and for no other zone. WHEN `now` is 15:00 UTC the same day THEN it SHALL do so for America/Vancouver businesses only.
5. IF the job runs twice in the same hour THEN the system SHALL send one digest per owner in total.
6. IF an owner turned the weekly digest off THEN the system SHALL record that owner's delivery as `skipped` and send nothing to them, while the other owners' digests are still sent.
7. The system SHALL record digests only for owners of the business. An owner of a different business SHALL get no delivery for it.
8. IF a business has no forecast snapshot, or no minimum balance set, THEN the system SHALL record no delivery for it and SHALL log `email.digest_skipped` with `business_id` and `reason` `no_forecast` or `no_minimum`.
9. IF building one business's digest raises THEN the system SHALL log `email.digest_failed` with `business_id` and the error type, record nothing for that business, and still handle the other businesses. The job's `digests_failed` SHALL count it.
10. WHEN deliveries are recorded for a business THEN the system SHALL log `email.digest_requested` with `business_id`, the local Monday and the number of deliveries recorded. The job SHALL return `digests_requested` as the total number of deliveries recorded.
11. The system SHALL list `weekly_digest` in `jobs.JOBS` after `forecast_accuracy` and before `email_retries`.

**Independent test:** with a simulated clock and the fake sender, run the job at the three times above. Exactly one zone's owner gets one email each time, and a second run in the same hour sends nothing more.

### S2: The email matches its mockup (P1)

The rendered digest shows the same content and arrangement as `design/mockups/email-digest.dc.html`.

**Acceptance Criteria**

12. The subject and the HTML `h1` SHALL both read "Your cash for the next 13 weeks". The first heading line of the plain-text part SHALL be the same text.
13. The label above the heading SHALL read "Weekly forecast · Monday, {date}", for example "Weekly forecast · Monday, Sep 28".
14. WHERE the recipient has a first name THEN the first paragraph SHALL read "Hi {first name}, here's where {business name} stands this week." Without a first name, it SHALL read "Here's where {business name} stands this week."
15. The email SHALL show a "Cash on hand" tile with the latest forecast's opening balance as signed whole dollars, for example "$42,300".
16. The email SHALL show a "Projected low" tile with the lowest `end_balance_cents` of the 13 weeks (the earlier week when tied) as signed whole dollars, for example "$3,150" or "−$3,150", and "Week of {date}", for example "Week of Nov 9". WHERE that low is below the minimum balance THEN the tile SHALL use the amber style of the mockup. Otherwise it SHALL use the plain style of the "Cash on hand" tile.
17. WHERE the business has at least one open alert THEN the email SHALL show "Open alerts ({n})", then one box per alert ordered by start date: "Cash falls below your {minimum} minimum the week of {week}." followed by a link to `/alerts/{alert_id}`. The link text SHALL be "See the fixes" for 2 or more fixes, "See the fix" for 1, and "See details" for 0.
18. WHERE the business has no open alert and the projected low is at or above the minimum THEN the email SHALL replace the open alerts block with "All clear. Your forecast stays above your {minimum} minimum for the next 13 weeks."
19. WHERE the business has no open alert and the projected low is below the minimum (every gap was dismissed) THEN the email SHALL show neither the open alerts block nor the all clear message.
20. WHERE last Monday's pinned forecast exists THEN the email SHALL show "What changed since last week" with these bullets, in this order, and no others:
    - "Cash on hand is up {amount}." or "Cash on hand is down {amount}." for the change in opening balance from last Monday's pin, omitted when it is 0.
    - One "New expected payment: {description}, {amount}, on {weekday date}." for each expected payment created since the start of last local Monday and not yet matched, at most 3, the largest amount first.
    - "Your projected low is {amount} higher than last week." or "… {amount} lower than last week." for the change in the projected low from last Monday's pin, omitted when it is 0.
    Amounts SHALL be unsigned whole dollars.
21. WHERE last Monday's pinned forecast exists and all three bullets would be omitted THEN the section SHALL read "Nothing has changed since last week."
22. WHERE last Monday's pinned forecast does not exist THEN the email SHALL omit the "What changed since last week" section.
23. The email SHALL have one button "Open your dashboard" linking to `{WEB_URL}/`.
24. The plain-text part SHALL contain, in order: the label, the heading, the first paragraph, cash on hand, the projected low, the open alerts or the all clear, the changes, and the dashboard URL.
25. The HTML content block SHALL use only tables and inline `style` attributes for layout, with no `display: flex`, `display: grid` or `position`. The two tiles SHALL be two table cells in one row. The button SHALL be a table cell with `bgcolor="#1D4E89"` around an `<a>` with white (`#FFFFFF`) text. The email SHALL load no external stylesheet, script or image.
26. The HTML SHALL use the mockup's colours: label `#5A6370`, tile border `#E2DDD3`, amber tile and alert box background `#FFF4E2` with border `#F0D3A4`, amber tile figure `#5C3300`, amber tile text `#7A4300`, alert box text `#3D2E1C`, and button `#1D4E89`.
27. WHEN the sample digest email is sent through Resend to Gmail (web), Outlook and Apple Mail THEN each client SHALL show the wordmark, label, heading, both tiles, alerts or all clear, changes, button and footer in one column, with nothing clipped or overlapping. One screenshot per client is saved in `.specs/features/30-email-weekly-digest/`.

**Independent test:** render the `weekly_digest` template from the Harbor Street sample, and compare its text and its order with the mockup.

### S3: Nothing in the email can expose an account or sign someone in (P1)

**Acceptance Criteria**

28. The system SHALL store in a digest delivery's `params` exactly the keys of door 3, and no account ID, account number, account mask, `source_id` or Clerk or Plaid identifier.
29. The system SHALL make every link in a digest exactly one of these: `{WEB_URL}/`, `{WEB_URL}/alerts/{alert_id}`, `{WEB_URL}/settings/email`, or `{WEB_URL}/unsubscribe/{token}`. No link SHALL carry a query string, and the dashboard and alert links SHALL require sign-in (existing `auth.protect()`, AD-026).

**Independent test:** render a digest whose expected payment is described with digits, then assert the link set and the absence of any account field.

## Out of scope

| Excluded | Why |
| --- | --- |
| Digests to bookkeepers, and their opt-in | No bookkeeper role exists until spec 31, which extends the owner query (AD-116) |
| Naming the payment that moved the projected low | The mockup's third bullet names a cause. Doing that needs a diff of two forecasts' items, which no spec asks for. The bullet states the change only (assumption below) |
| A catch-up send after a missed run | The spec says "during the 8 AM hour". A skipped hourly run loses that week's digest |
| A warning that the forecast is stale | The dashboard already shows `incomplete`. The digest sends what the latest forecast says |
| A chosen day or hour per user | The spec fixes Monday at 8 AM |
| French emails | v1 is English only (AGENTS.md) |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| The "projected low" bullet in "What changed" | States the change, without naming a cause (AC 20) | The mockup names Coastal Supply Co. Doing that needs a diff of forecast items between two pins, and only the mockup asks for it | n |
| "Since last week" for new expected payments | Created since the start of last local Monday, not yet matched, at most 3, largest first (AC 20) | The pin that supplies the baseline is taken on the first run of a Monday. Three keeps the list short | n |
| Wording of the all clear | "All clear. Your forecast stays above your {minimum} minimum for the next 13 weeks." (AC 18) | The spec asks for a short all clear message and the mockup shows none | n |
| Subject line | Same as the heading, "Your cash for the next 13 weeks" (AC 12) | The mockup has no subject; spec 29 made its subject equal its `h1` | n |
| A missed hourly run | The week's digest is lost (door 1) | The spec says "during the 8 AM hour"; a catch-up would need a window the spec doesn't give | n |
| A business without a forecast or a minimum | No digest, logged (AC 8) | Onboarding step 4 and step 5 create both; a digest before them would show nothing true | n |
| A business whose gap was dismissed | Amber tile, no alerts block, no all clear (AC 19) | "All clear" would be false, and the user chose to dismiss the alert | n |
| "Cash on hand" source | The latest snapshot's `opening_balance_cents` | It is the sum of the included cash accounts when the forecast was computed (AD-077), so the digest needs no read from `bank_sync` | n |

**Open questions:**

| # | Kind | Question | Until answered |
| --- | --- | --- | --- |
| 1 | blocks | You (the user) send the sample digest through Resend, using a `RESEND_API_KEY`, to a Gmail, an Outlook and an Apple Mail inbox, and save the screenshots, as for spec 29 (AD-117) | AC 27 can't be proven, so spec 30 can't be set to Done |

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| email `weekly_digest` | structure | AC 12–18, 20, 24 |
| email `weekly_digest` | tone | existing: the copy follows the alert email's, written under DESIGN.md |
| email `weekly_digest` | depth | AC 17, 20: one line per alert and at most 3 new payments. The full detail stays on the alert page and dashboard |
| email `weekly_digest` | what the reader does next | AC 23: one button to the dashboard, and one link per alert |
| email `weekly_digest` | rendering in mail clients | AC 25, 26, 27 |
| email `weekly_digest` | unsubscribe and preferences | existing: spec 28's footer and `List-Unsubscribe` headers (AD-108); AC 6 |
| email `weekly_digest` | empty state | AC 18, 21, 22: no alerts, no changes, no baseline |
| email `weekly_digest` | error state | existing: a delivery that can't render is `failed` (spec 28). A retryable send error stays `pending` (AD-107). AC 9 for the job |
| email `weekly_digest` | unauthorised reader | AC 29: the links require sign-in. The alert page shows `not-found` for a foreign alert (AD-105) |
| email `weekly_digest` | loading state | n/a - an email has no loading state |
| job `weekly_digest` | output format and verbosity | AC 10: one log line per business, counts in `jobs.run_finished` |
| job `weekly_digest` | flags and defaults | n/a - the job takes only `now`, like every job in `JOBS` |
| job `weekly_digest` | exit codes | existing: `run_due` exits 0 when a job fails and logs `jobs.job_failed` (spec 15) |
| job `weekly_digest` | what it prints when it fails halfway | AC 9: the failing business is logged and skipped, the rest go on |

## Sources

- `context/specs/30-email-weekly-digest.md`: the goal and the Done-when items
- `design/mockups/email-digest.dc.html`: binding for the copy and the arrangement
- `.specs/STATE.md` AD-084, AD-085, AD-106 to AD-111, AD-115, AD-116: the pins, the job runner, and the email pipeline this spec calls
