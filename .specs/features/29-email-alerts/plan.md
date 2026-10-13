# Spec 29: Alert emails

## Problem

When the forecast finds a cash gap, or an existing gap grows, Headroom shows it only on the dashboard and on the alert page. An owner who doesn't open the app that week doesn't learn about the gap until the bank balance shows it, which is too late to ask a client to pay early or move a bill. Getting this warning without opening the app is the product's core promise (`context/project-overview.md`). The onboarding screen already tells owners it happens: "If your forecast dips below {amount}, you get an email that names the payments causing it" (`Onboarding.Minimum.alertsBody`). Today no email is sent.

When this ships, each owner of the business gets one email when a gap appears (`alert.created`), and one more each time it grows past the threshold in AD-096 (`alert.updated`). The email names the payments causing the gap, shows the top fix, and links to the alert page.

## Flow

This reuses the alert events (AD-097), the email pipeline from spec 28 (`request_email` → commit → `deliver`, dedup index, preferences, retries, footer: AD-106 to AD-110), Clerk contacts (AD-111), and the alert page URL (AD-105). It adds a handler, one template, and two formatting filters.

1. `alerts.service.check_cash_gaps` (exists) commits, then publishes `alert.created` or `alert.updated` with `{"alert_id"}` (AD-097).
2. Event bus (exists) → `SUBSCRIPTIONS` (door 1) → `notifications.service.email_alert` (exists as a module, new function).
3. `email_alert` opens a session. It reads the alert through `alerts.service.get_alert` (exists), scoped to `event.business_id`, and stops unless the alert is `open`. It reads the business name through `accounts.service` (exists) and the owners through a new `accounts.service` member query (placement).
4. For each owner, `notifications.service.request_email` (exists) records a pending `alert` delivery. The delivery gets dedup key `alert:{alert_id}:{notified_shortfall_cents}` (door 2) and template `alert` with the params in door 3. A user who turned alert emails off gets a `skipped` row instead. Then one commit.
5. After the commit, `notifications.service.deliver` (exists) runs for each new delivery. It renders `alert.subject.txt`, `alert.html` and `alert.txt` over `base.*` with the `money` and `day` filters (door 4), then sends. A retryable failure stays `pending` for the hourly `email_retries` job (exists).

## Impact

| Front | What changes |
| --- | --- |
| events | `SUBSCRIPTIONS` gains two rows after the alert handlers: `alert.created` and `alert.updated` both go to `notifications.service.email_alert`. `alert.resolved` stays unsubscribed |
| latency | The API requests and jobs that publish an alert event (the minimum balance `PUT`, expected payment changes, the bank sync job) now also call Clerk and Resend inline, once per owner. v1 has one owner per business |
| notifications | `rendering.environment()` gains the `money` and `day` filters. The render context gains `web_url`, so the alert link is built when the email is sent, not stored |
| accounts | `accounts.service` gains a public read of a business's owner user IDs. Spec 31 extends it to bookkeepers who opt in |
| copy | The email repeats the dashboard alert copy (`Dashboard.alert.*` in `frontend/messages/en.json`) in Jinja templates. Emails are rendered by the API and the jobs process, which have no Node (AD-110). A wording change has to be made in both places |
| alerts | `alerts.service.AlertView` gains `notified_shortfall_cents`, which door 2 keys on. The API's `Alert` model is built `from_attributes` and doesn't declare it, so the JSON doesn't change |
| tests | Existing alert tests that publish events will now also run the email handler. Spec 28 fakes Clerk only inside its `mail` fixture, so `tests/conftest.py` gains an autouse fake Clerk with no users. Without it, those tests would call Clerk with the placeholder key. A missing contact only fails the delivery |
| tooling | `uv run python -m app.modules.notifications.sample_alert --to <address>` sends the mockup's sample alert email through the configured sender, for the manual check in AC 21 |
| specs | `context/specs/29-email-alerts.md` gets a note: bookkeepers who opt in are added by spec 31 (user decision 2026-10-13) |
| stored data | Nothing to migrate. `email_deliveries.kind` already allows `alert`, and no schema changes |

## Relations

`None - no stored-data shape change`

## Surface

`None - nothing consumed outside`. The email is the outside surface, and it's covered in `## Observable`. Its alert link uses `/alerts/{alert_id}`, which AD-105 already fixes.

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. Who sends alert emails | `app/subscriptions.py`: `(ALERT_CREATED, notifications_service.email_alert)`, `(ALERT_UPDATED, notifications_service.email_alert)`, appended after `check_cash_gaps`. `notifications` reads the alert through `alerts.service.get_alert` | `alerts._reconcile` calling `request_email` itself. That makes `alerts` depend on email, and the Clerk and Resend calls would run while the business's alerts lock is held. AGENTS.md says modules tell each other through events |
| 2. The dedup key | `alert:{alert_id}:{notified_shortfall_cents}`, unique per user under `uq_email_deliveries_dedup_key_user_id` (AD-106) | `alert:{id}:{event name}` allows only one update email per alert, ever. `alert:{id}:{updated_at}` would send again when an event is replayed after a fixes-only change, because that change updates `updated_at` silently (AD-100). Trade-off: if a dismissed alert grows back to exactly the amount already emailed, that owner gets no second email |
| 3. Params stored in `email_deliveries.params` | `{"alert_id": str, "business_name": str, "change": "created"\|"updated", "currency": str, "minimum_cents": int, "lowest_balance_cents": int, "lowest_week_starts_on": "YYYY-MM-DD", "causes": [{"name": str, "amount_cents": int, "date": "YYYY-MM-DD"}], "top_fix": {"kind": str, "name": str, "amount_cents": int, "keeps_above": bool} \| null, "fix_count": int}` | Storing the rendered HTML. The template couldn't change for retries, and the stored HTML would hold unsubscribe URLs. Storing the whole `AlertView`. Its `source_id`, `description` and account fields would go into a table that never needs them. Retries render stored params hours later, so the template must keep reading this shape |
| 4. Formatting money and dates in email | Jinja filters registered in `rendering.environment()`: `money(cents, currency)` → `"$14,500"`, whole dollars rounded half away from zero, `−` for negatives, CAD only (any other currency raises, which fails the delivery). `day(iso)` → `"Nov 9"`; `day(iso, weekday=True)` → `"Thu, Nov 12"`. Both mirror `frontend/lib/format.ts`, and spec 30 copies them | Formatting in the handler and storing strings in params. Copy and format would then be split between two files, and a stored string can't be restyled. Adding Babel: a new dependency for one currency and one locale |

- Nothing else in this change is hard to reverse.

## Criteria

### S1: One email per owner when a gap appears or grows (P1)

When a gap appears or grows past the AD-096 threshold, every owner of the business receives exactly one email about it.

**Acceptance Criteria**

1. WHEN `alert.created` is handled for an `open` alert THEN the system SHALL record one `alert` delivery for each owner of the alert's business. Each delivery has dedup key `alert:{alert_id}:{notified_shortfall_cents}`, template `alert` and reason "You're getting this email because you're an owner of {business name} on Headroom." The system SHALL deliver each one after the commit.
2. WHEN `alert.updated` is handled for an `open` alert THEN the system SHALL record and deliver one `alert` delivery per owner the same way, keyed on the alert's new `notified_shortfall_cents`.
3. IF the same `alert.created` or `alert.updated` event is handled twice THEN the system SHALL send one email per owner in total.
4. WHEN `alert.resolved` is published THEN the system SHALL record no delivery.
5. IF the alert is `dismissed` or `resolved` when its event is handled THEN the system SHALL record no delivery, and SHALL log `email.alert_skipped` with `alert_id` and `state`.
6. IF the event's `alert_id` is not an alert of the event's `business_id` THEN the system SHALL record no delivery, and SHALL log `email.alert_skipped` with `alert_id` and `state` `not_found`.
7. The system SHALL record alert deliveries only for owners of the alert's business. An owner of a different business SHALL get no delivery.
8. IF an owner turned alert emails off THEN the system SHALL record that owner's delivery as `skipped` and send nothing to them, while the other owners' emails are still sent.
9. WHEN deliveries are recorded for an alert THEN the system SHALL log `email.alert_requested` with `alert_id`, the event name and the number of deliveries recorded.

**Independent test:** with the fake sender, publish `alert.created` for a Harbor Street alert twice. Exactly one email reaches the owner, and an owner of another business gets nothing.

### S2: The email matches its mockup (P1)

The rendered alert email shows the same content and arrangement as `design/mockups/email-alert.dc.html`.

**Acceptance Criteria**

10. The subject SHALL be "Cash falls below your {minimum} minimum the week of {week}", for example "Cash falls below your $5,000 minimum the week of Nov 9". The HTML `h1` and the first heading line of the plain-text part SHALL be the same text.
11. The label above the heading SHALL read "Cash gap" for `alert.created` and "Cash gap got bigger" for `alert.updated`.
12. WHERE the recipient has a first name THEN the first paragraph SHALL read "Hi {first name}, the forecast for {business name} shows cash dropping to {lowest balance} in the week of {week}.", with the lowest balance in bold. Without a first name, it SHALL read "The forecast for {business name} shows cash dropping to {lowest balance} in the week of {week}."
13. The email SHALL list every cause under "What's causing it" as "{name}, {amount}, on {weekday date}", for example "Coastal Supply Co, $14,500, on Thu, Nov 12". Causes SHALL be ordered by amount, largest first, with ties broken by earlier date. The name SHALL be the counterparty, or else the description up to its first comma.
14. WHERE the alert has at least one fix, the email SHALL show a box starting "Top fix:" with the first fix in kind order (AD-101). The fix text SHALL be "ask {name} to pay their {amount} invoice a week early." for `pay_early`, "move the {amount} payment to {name} a week later." for `move_payment`, "draw {amount} from your {name}." for `draw_credit`, and "arrange {amount} of short-term financing for the length of the gap." for `financing`. The box SHALL add "That keeps you above your minimum." when that fix's `new_lowest_balance_cents` ≥ `minimum_cents`.
15. IF the alert has no fix THEN the email SHALL have no "Top fix:" box.
16. The email SHALL have one button linking to `{WEB_URL}/alerts/{alert_id}`. Its text SHALL be "See all {n} fixes" for n ≥ 2, "See the fix" for 1, and "See details" for 0.
17. The email SHALL show payment and fix amounts as unsigned whole dollars, for example "$14,500", and the minimum and the lowest balance as signed whole dollars, so a projected low below zero reads "−$3,150". Week dates SHALL appear as "Nov 9", and cause dates as "Thu, Nov 12". (Amended while deriving the checks: an unsigned low would hide an overdraft.)
18. The plain-text part SHALL contain, in order: the label, the heading, the first paragraph, "What's causing it" with one line per cause, the top fix line (when there is one), and the alert URL.
19. The HTML content block SHALL use only tables and inline `style` attributes for layout, with no `display: flex`, `display: grid` or `position`. The button SHALL be a table cell with `bgcolor="#1D4E89"` around an `<a>` with white (`#FFFFFF`) text. The email SHALL load no external stylesheet, script or image.
20. The HTML SHALL use the mockup's colours: label `#7A4300`, fix box background `#FFF4E2` with border `#F0D3A4` and text `#3D2E1C`, and button `#1D4E89`.
21. WHEN the sample alert email is sent through Resend to Gmail (web), Outlook and Apple Mail THEN each client SHALL show the wordmark, label, heading, causes, top fix box, button and footer in one column, with nothing clipped or overlapping. One screenshot per client is saved in `.specs/features/29-email-alerts/`.

**Independent test:** render the `alert` template from the Harbor Street sample alert, and compare its text and its order with the mockup.

### S3: Nothing in the email can expose an account or sign someone in (P1)

**Acceptance Criteria**

22. The system SHALL store in an alert delivery's `params` exactly the keys of door 3, and no account ID, account number, account mask, `source_id` or Clerk or Plaid identifier.
23. The system SHALL make every link in an alert email exactly one of these: `{WEB_URL}/alerts/{alert_id}`, `{WEB_URL}/settings/email`, or `{WEB_URL}/unsubscribe/{token}`. No link SHALL carry a query string, and the alert link SHALL require sign-in (existing `auth.protect()`, AD-026).

**Independent test:** render an alert email whose credit line is named with digits, then assert the link set and the absence of any account field.

## Out of scope

| Excluded | Why |
| --- | --- |
| Alert emails to bookkeepers, and their opt-in | No bookkeeper role exists until spec 31. Spec 31 adds bookkeepers who opt in through the same owner query (user decision 2026-10-13) |
| An email when a gap resolves | The spec emails on `alert.created` and `alert.updated` only. The alert page already shows "This gap is no longer in your forecast." |
| Rechecking the alert when a retry sends hours later | A retry sends what was true when the event was handled. Rechecking would make `notifications` depend on the alerts' state machine |
| French emails | v1 is English only (AGENTS.md) |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Whether an update email reads differently | The same template, with the label "Cash gap got bigger" instead of "Cash gap" (AC 11) | The mockup shows only a new gap. The heading already states the current low, so only the label needs to change | n |
| Greeting without a first name | Drop "Hi …," and start with "The forecast for …" (AC 12) | Clerk can have no first name (AD-111). "Hi," on its own reads like a mistake | n |
| Which causes and in what order | All causes, largest first, the same as the dashboard's `causesBySize` (AC 13) | The mockup lists two, in descending amount. AD-096 keeps only payments of at least 20% of money out that week, so the list stays short | n |
| Sending inline or from the job | Deliver inline after the commit, as AD-107 says | Spec 28 chose this. Waiting for the hourly job could delay a warning by up to an hour | y |
| Bookkeepers | Owners only in spec 29; spec 31 adds bookkeepers who opt in | No bookkeeper role exists yet (user decision 2026-10-13) | y |

**Open questions:**

| # | Kind | Question | Until answered |
| --- | --- | --- | --- |
| 1 | blocks | You (the user) send the sample alert email through Resend, using a `RESEND_API_KEY`, to a Gmail, an Outlook and an Apple Mail inbox, and save the three screenshots (user decision 2026-10-13) | AC 21 can't be proven, so spec 29 can't be set to Done |

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| email `alert` | structure | AC 10–16, 18 |
| email `alert` | tone | existing: the copy is the dashboard's `Dashboard.alert.*`, written under DESIGN.md |
| email `alert` | depth | AC 13, 14: the causes and the top fix. The full list of fixes stays on the alert page (AC 16) |
| email `alert` | what the reader does next | AC 16: one button to the alert page |
| email `alert` | rendering in mail clients | AC 19, 20, 21 |
| email `alert` | unsubscribe and preferences | existing: spec 28's footer and `List-Unsubscribe` headers (AD-108) |
| email `alert` | empty state | AC 15: no fix. A gap always has a shortfall, so a heading always exists |
| email `alert` | error state | existing: a delivery that can't render is `failed` (spec 28). A retryable send error stays `pending` (AD-107) |
| email `alert` | unauthorised reader | AC 23: the link requires sign-in. The alert page shows `not-found` for a foreign alert (AD-105) |
| email `alert` | loading state | n/a - an email has no loading state |

## Sources

- `context/specs/29-email-alerts.md`: the goal and the Done-when items
- `design/mockups/email-alert.dc.html`: binding for the copy and the arrangement
- `.specs/STATE.md` AD-096, AD-097, AD-101, AD-105 to AD-111: the alert events, and the email pipeline this spec calls
