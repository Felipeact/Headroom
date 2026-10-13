# 29 - Alert emails checks

Profile: light
Plan: `.specs/features/29-email-alerts/plan.md`

26 checks in 3 slices · 4 one-way doors · 1 open, of which 1 blocks (AC 21: your manual send)

Unless noted, `uv run` proofs run from `services/core`. API tests use the real local Postgres from `tests/conftest.py`, plus spec 28's `mail` fixture: a `FakeEmailSender` and a `FakeClerkUsers`, so no test calls Resend or Clerk. "The sample" is Harbor Street seed 0 with its owner registered in the fake Clerk as "Dana" at `dana@example.test`, after `PUT minimum-balance` with `500000`. That request creates the alert the mockup shows: minimum $5,000, low $3,150 in the week of Nov 9, Coastal Supply Co $14,500 on Thu, Nov 12, Payroll $11,200 on Fri, Nov 13, and 3 fixes with Birch & Co's $9,600 first (spec 24 C7, spec 25 C9). "Hand-built alerts" use the `fake` forecasting fixture of `tests/test_alert_check.py`. Test settings include `WEB_URL=https://app.example.test`.

## Checks

### S1 - One email per owner when a gap appears or grows · 8 files · 45 KB · ~12k

**C1** - Handling `alert.created` for an `open` alert of a business with two owners, both with Clerk contacts, records exactly 2 `email_deliveries` rows, one per owner. Each row has kind `alert`, template `alert`, dedup key `alert:{alert_id}:{notified_shortfall_cents}`, and reason "You're getting this email because you're an owner of {business name} on Headroom.". Both rows are `sent` after the handler returns, and `FakeEmailSender` holds 2 sends, one to each owner's address (AC 1, door 2)
Proof: `uv run pytest tests/test_alert_emails.py -k "created_emails_each_owner"`

**C2** - A hand-built alert first emailed at shortfall 100000, whose shortfall then grows to 300000 so that `check_cash_gaps` publishes `alert.updated`, gets a second delivery for the owner with key `alert:{id}:300000`. The owner then has 2 rows and 2 sends in total (AC 2, door 2)
Proof: `uv run pytest tests/test_alert_emails.py -k "updated_emails_again"`

**C3** - Handling the same `alert.created` event twice records 1 row and 1 send per owner. Handling the same `alert.updated` event twice adds exactly 1 more row and 1 more send (AC 3)
Proof: `uv run pytest tests/test_alert_emails.py -k "same_event_twice"`

**C4** - `app.subscriptions.SUBSCRIPTIONS` contains `(alert.created, notifications.service.email_alert)` and `(alert.updated, notifications.service.email_alert)`, both after every `check_cash_gaps` row, and no row for `alert.resolved`. When a hand-built alert resolves, with subscriptions registered, 0 new deliveries are recorded (AC 4, door 1)
Proof: `uv run pytest tests/test_alert_emails.py -k "subscriptions_and_resolved"`

**C5** - Handling `alert.created` for an alert that is `dismissed`, and then for one that is `resolved`, records 0 rows. Each logs `email.alert_skipped` with that `alert_id` and `state` `dismissed` or `resolved` (AC 5)
Proof: `uv run pytest tests/test_alert_emails.py -k "not_open_skipped"`

**C6** - An event whose `business_id` is business B and whose `alert_id` is an alert of business A records 0 rows for anyone. So does an event whose `alert_id` is a random UUID. Both log `email.alert_skipped` with `state` `not_found` (AC 6)
Proof: `uv run pytest tests/test_alert_emails.py -k "foreign_alert_skipped"`

**C7** - With two businesses, each with its own owner, handling `alert.created` for A's alert records deliveries whose `user_id` set equals A's owners exactly. B's owner has 0 rows (AC 7)
Proof: `uv run pytest tests/test_alert_emails.py -k "only_this_business_owners"`

**C8** - With two owners, where the first turned `alerts` off, handling `alert.created` leaves the first owner's row `skipped` with 0 sends to them. The second owner's row is `sent`, and `FakeEmailSender` holds 1 send (AC 8)
Proof: `uv run pytest tests/test_alert_emails.py -k "owner_opted_out"`

**C9** - Handling `alert.created` for a business with two owners logs one `email.alert_requested` line with `alert_id`, `event_name` `alert.created` and `deliveries` 2 (AC 9)
Proof: `uv run pytest tests/test_alert_emails.py -k "requested_logged"`

**C10** - On the sample, with subscriptions registered, the `PUT minimum-balance` request alone leaves `FakeEmailSender` with exactly 1 email, to `dana@example.test`, carrying the subject from C11 (AC 1, end to end through the bus)
Proof: `uv run pytest tests/test_alert_emails.py -k "sample_end_to_end"`

### S2 - The email matches its mockup · 7 files · 30 KB · ~8k

**C11** - The sample email's subject is exactly "Cash falls below your $5,000 minimum the week of Nov 9". The HTML `h1` text is the same, and so is the plain-text part's first line after the label (AC 10)
Proof: `uv run pytest tests/test_alert_email_template.py -k "sample_heading"`

**C12** - Rendered with `change` `created`, the label in both the HTML and the text is "Cash gap". With `change` `updated`, it is "Cash gap got bigger". In HTML the label comes before the `h1` (AC 11)
Proof: `uv run pytest tests/test_alert_email_template.py -k "label_by_change"`

**C13** - With first name "Dana", the sample's first paragraph reads "Hi Dana, the forecast for Harbor Street Plumbing shows cash dropping to <strong>$3,150</strong> in the week of Nov 9." in HTML. With no first name, the text reads "The forecast for Harbor Street Plumbing shows cash dropping to $3,150 in the week of Nov 9." and the HTML has no "Hi" (AC 12)
Proof: `uv run pytest tests/test_alert_email_template.py -k "greeting"`

**C14** - Under "What's causing it", the sample's HTML list items are, in order, "Coastal Supply Co, $14,500, on Thu, Nov 12" and "Payroll, $11,200, on Fri, Nov 13". The params builder orders causes [−5000 on Nov 10, −9000 on Nov 12, −9000 on Nov 11] as 9000 Nov 11, 9000 Nov 12, 5000 Nov 10. It names an item by its counterparty when set (counterparty "Acme", description "Other, x" gives "Acme"), and otherwise by its description up to the first comma ("Birch & Co, invoice 1057" gives "Birch & Co"). It leaves out the `arrives_after` item (AC 13)
Proof: `uv run pytest tests/test_alert_email_template.py -k "sample_causes"`
Proof: `uv run pytest tests/test_alert_emails.py -k "params_causes"`

**C15** - The top fix text, table-driven over all 4 kinds, is "ask Birch & Co to pay their $9,600 invoice a week early." for `pay_early`, "move the $14,500 payment to Coastal Supply Co a week later." for `move_payment`, "draw $2,000 from your Line of credit." for `draw_credit`, and "arrange $2,000 of short-term financing for the length of the gap." for `financing`. Each is preceded by "Top fix:". "That keeps you above your minimum." follows when `new_lowest_balance_cents` = `minimum_cents` and when it is greater, and is absent when it is `minimum_cents` − 1. The sample shows the `pay_early` line with that sentence (AC 14)
Proof: `uv run pytest tests/test_alert_email_template.py -k "top_fix"`

**C16** - An alert with no fixes renders no "Top fix:" in either the HTML or the text, and no element with background `#FFF4E2` (AC 15)
Proof: `uv run pytest tests/test_alert_email_template.py -k "no_fix"`

**C17** - The email has exactly one button link, `https://app.example.test/alerts/{alert_id}`. Its text over `fix_count` 0, 1, 2 and 3 is "See details", "See the fix", "See all 2 fixes" and "See all 3 fixes" (AC 16)
Proof: `uv run pytest tests/test_alert_email_template.py -k "button"`

**C18** - The `money` filter gives `1450000` → "$14,500", `315049` → "$3,150", `315050` → "$3,151", `-315000` → "−$3,150" (U+2212), `0` → "$0", `-49` → "$0", and `-50` → "−$1". Any currency other than `CAD` raises. The `day` filter gives "2026-11-09" → "Nov 9", and with a weekday "2026-11-12" → "Thu, Nov 12". The params builder stores cause and fix amounts unsigned. An alert whose low is −315000 renders "cash dropping to <strong>−$3,150</strong>" (AC 17, door 4)
Proof: `uv run pytest tests/test_alert_email_template.py -k "filters"`
Proof: `uv run pytest tests/test_alert_email_template.py -k "negative_low"`

**C19** - The sample's plain-text part contains these lines, in this order: "Cash gap", the heading, the first paragraph, "What's causing it", one "- " line per cause, "Top fix: …", and `https://app.example.test/alerts/{alert_id}` (AC 18)
Proof: `uv run pytest tests/test_alert_email_template.py -k "plain_text_order"`

**C20** - The sample's HTML contains none of `display: flex`, `display:flex`, `grid` or `position:` (in any case). It contains no `<link`, `<script` or `<img`. Its button is a `<td>` with `bgcolor="#1D4E89"` around an `<a>` whose style sets `color: #FFFFFF` (AC 19)
Proof: `uv run pytest tests/test_alert_email_template.py -k "email_safe_html"`

**C21** - The sample's HTML styles the label with `color: #7A4300`, the fix box with `background: #FFF4E2`, `#F0D3A4` in its border and `color: #3D2E1C`, and the button with `#1D4E89` (AC 20)
Proof: `uv run pytest tests/test_alert_email_template.py -k "mockup_colours"`

**C22** - The sample alert email sent through Resend shows the wordmark, label, heading, causes, top fix box, button and footer in one column, with nothing clipped or overlapping, in Gmail (web), Outlook and Apple Mail. One screenshot per client exists in the feature folder, and you, the user, confirm what each shows (AC 21)
Proof: `test -f .specs/features/29-email-alerts/gmail.png && test -f .specs/features/29-email-alerts/outlook.png && test -f .specs/features/29-email-alerts/apple-mail.png` (from the repo root)

**C23** - `python -m app.modules.notifications.sample_alert --to someone@example.test`, run against the fake sender, sends 1 email to that address. Its subject is the one from C11, and its HTML contains "Coastal Supply Co, $14,500, on Thu, Nov 12". Without `--to`, it exits with status 2 (tooling for AC 21)
Proof: `uv run pytest tests/test_alert_email_template.py -k "sample_alert_command"`

### S3 - Nothing in the email exposes an account or signs someone in · 2 files · 15 KB · ~4k

**C24** - The sample delivery's stored `params` has exactly the keys `alert_id`, `business_name`, `change`, `currency`, `minimum_cents`, `lowest_balance_cents`, `lowest_week_starts_on`, `causes`, `top_fix` and `fix_count`. Each cause has exactly `name`, `amount_cents` and `date`, and `top_fix` has exactly `kind`, `name`, `amount_cents` and `keeps_above`. Neither the JSON of `params` nor the rendered HTML and text contain any sample account's `id`, `plaid_account_id` or mask (`2381`, `9025`, `5530`, `7702`), any item's `source_id`, or the owner's Clerk user id (AC 22, door 3)
Proof: `uv run pytest tests/test_alert_emails.py -k "params_hold_no_account"`

**C25** - Every `href` in the sample's HTML is one of `https://app.example.test/alerts/{alert_id}`, `https://app.example.test/settings/email` or `https://app.example.test/unsubscribe/{token}`, and each appears at least once. No `href` and no URL in the text part contains `?`. The web app protects every page except sign-in, sign-up and `/unsubscribe/[token]`, so `/alerts/[alertId]` requires sign-in (AC 23)
Proof: `uv run pytest tests/test_alert_email_template.py -k "links"`
Proof: `npx vitest run tests/auth-protect.test.ts -t "every page protected"` (from `frontend`)

**C26** - In a test that doesn't use the `mail` fixture, `clerk.get_clerk_users()` returns a fake with no users, not `BackendClerkUsers`. So when an existing alert test now triggers the email handler, the delivery fails as `no_contact` and nothing calls Clerk (Impact: tests)
Proof: `uv run pytest tests/test_alert_emails.py -k "no_real_clerk_in_tests"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| alert events (3) | `alert.created` C1 · `alert.updated` C2 · `alert.resolved` C4 | - |
| alert state when handled (4) | `open` C1 · `dismissed` C5 · `resolved` C5 · not found C6 | - |
| fix kinds (4) | `pay_early` C15 · `move_payment` C15 · `draw_credit` C15 · `financing` C15 | - |
| keeps-above edge (3) | equal C15 · above C15 · one below C15 | - |
| label by change (2) | `created` C12 · `updated` C12 | - |
| greeting (2) | first name C13 · none C13 | - |
| button text by fix count (4) | 0 C17 · 1 C17 · 2 C17 · 3 C17 | - |
| links in the email (3) | alert C25 · preferences C25 · unsubscribe C25 | - |
| one-way doors (4) | door 1 C4 · door 2 C1 · door 3 C24 · door 4 C18 | - |
| recipient set (3) | every owner C1 · other business's owner C7 · opted-out owner C8 | - |
| startup config: subscriptions (2 assemblies) | API and jobs both call `subscriptions.register()` over one `SUBSCRIPTIONS` tuple, C4 · test harness C10 | - |

- C10 is the only check that crosses the event bus from a real request. C1–C9 call `email_alert` (or `check_cash_gaps`) directly, so each is proven at its own layer.
- No other check claims more than the cases its proof exercises.

## Swept

- validation: C18 - a currency other than CAD raises, and spec 28 marks a delivery that can't render `failed`
- failure modes: existing - a handler that raises is logged by the bus (`event.handler_failed`, AD-047), and a render error fails one delivery without stopping the others (spec 28)
- idempotency: C3
- authorization: C7, C25
- concurrency: existing - `uq_email_deliveries_dedup_key_user_id` with `ON CONFLICT DO NOTHING`, and the `SKIP LOCKED` claim (AD-106, AD-107; spec 28 C2, C3). Two processes handling one event dedup the same way as C3
- data lifecycle: n/a - no new stored data; deliveries keep spec 28's lifecycle
- dependency failure: existing - a Clerk or Resend failure keeps the delivery `pending` for `email_retries` (AD-107, spec 28 C17)
- state transitions: C5 - only an `open` alert is emailed
- observability: C9, C5, C6

## Handoff

- S1 = ~12k, S2 = ~8k, S3 = ~4k. In bytes: notifications service and rendering 13 KB, templates new ~6 KB, alerts service 15 KB, accounts service and repository 9 KB, subscriptions 2 KB, conftest and email support 12 KB, new tests ~30 KB, sample command ~3 KB. That's ~90 KB, or ~24k tokens, all in `notifications` with read-only hops into `alerts` and `accounts`. That is under the 150k budget, so one builder.
- Mechanism: one builder (under budget, no ask)

- **Boundary:** C1-C26 written; not closed. Proofs run here: C18 `filters` (pure part), C23, C25 (vitest). Every other proof needs Postgres, and this PC has none (the portable install in an old Temp scratchpad lost its files; no Docker). They run on the user's other computer before the Verifier
- **Settled mid-build:** AC 17 amended (a low below zero keeps its sign); `tests/conftest.py` gains an autouse Clerk with no users, so no test reaches Clerk now that alerts email; spec 24's C29 count of `SUBSCRIPTIONS` goes from 6 to 8 (same strictness, two rows appended); the user chose to build as-is and test on another computer (2026-10-13)
- **Abandoned:** pointing the tests at the `postgres` database to get round the broken `headroom` one; its files are damaged too
