# 30 - Weekly digest checks

Profile: light
Plan: `.specs/features/30-email-weekly-digest/plan.md`

34 checks in 3 slices · 4 one-way doors · 1 open, which blocks (AC 27)

Unless noted, `uv run` proofs run from `services/core`. API and job tests use the real local Postgres from `tests/conftest.py` (`isolated_database`), plus spec 28's `mail` fixture: a `FakeEmailSender` and a `FakeClerkUsers`, so no test calls Resend or Clerk. The job is called as `weekly_digest(now)` with a fixed UTC `now`, which is the simulated clock. "The sample" is Harbor Street seed 0 with its owner registered in the fake Clerk as "Dana" at `dana@example.test`, after `PUT minimum-balance` with `500000`: projected low $3,150 in the week of Nov 9, one open alert with 3 fixes. "Hand-built" forecasts use the planting helpers of `tests/test_forecast_accuracy.py` (`plant_snapshot`, `plant_pin`). Test settings include `WEB_URL=https://app.example.test`. New tests live in `tests/test_weekly_digest.py` (the job and the builder), `tests/test_weekly_digest_template.py` (rendering) and `tests/test_digest_reads.py` (the new service reads).

## Checks

### S1 - One digest per owner, Monday in the 8 AM hour · 7 files · 75 KB · ~20k

**C1** - For a business in `America/Toronto` with two owners, both with Clerk contacts, `weekly_digest` at 12:00 UTC on Monday 2026-10-26 records exactly 2 `email_deliveries` rows, one per owner. Each has kind `weekly_digest`, template `weekly_digest`, dedup key `weekly_digest:{business_id}:2026-10-26` and reason "You're getting this email because you're an owner of {business name} on Headroom.". Both are `sent` after the job returns, and `FakeEmailSender` holds 2 sends, one to each owner's address (AC 1, doors 1 and 2)
Proof: `uv run pytest tests/test_weekly_digest.py -k "emails_each_owner"`

**C2** - For a Toronto business, the job records 0 rows at each of these times: Monday 2026-10-26 11:59 UTC (07:59 local), 13:00 UTC (09:00 local), Sunday 2026-10-25 12:30 UTC, Tuesday 2026-10-27 12:00 UTC. It records 1 row per owner at 12:00 UTC and at 12:59 UTC on the Monday (AC 2)
Proof: `uv run pytest tests/test_weekly_digest.py -k "only_the_eight_o_clock_hour"`

**C3** - With three businesses, one each in `America/St_Johns`, `America/Toronto` and `America/Vancouver`, the job at 11:00 UTC on Monday 2026-10-26 (St. John's is on daylight time, so 08:30 local) records deliveries for the St. John's business only. Run at 11:00 UTC on Monday 2026-11-02 (after the clocks change, 07:30 local) it records none for it, and at 12:00 UTC that day it records one for the St. John's business (08:30 NST) (AC 3)
Proof: `uv run pytest tests/test_weekly_digest.py -k "newfoundland_half_hour"`

**C4** - With the same three businesses, the job at 12:00 UTC on Monday 2026-10-26 records deliveries for the Toronto business only, and at 15:00 UTC the same day for the Vancouver business only (AC 4)
Proof: `uv run pytest tests/test_weekly_digest.py -k "eastern_and_pacific"`

**C5** - Running the job twice at 12:00 UTC on Monday 2026-10-26 leaves 1 row and 1 send per owner. Running it at 12:30 UTC the same Monday adds none (AC 5, door 2)
Proof: `uv run pytest tests/test_weekly_digest.py -k "same_hour_twice"`

**C6** - With two owners, where the first turned `weekly_digest` off, the job leaves the first owner's row `skipped` with 0 sends to them. The second owner's row is `sent`, and `FakeEmailSender` holds 1 send. An owner who turned only `alerts` off still gets the digest (AC 6)
Proof: `uv run pytest tests/test_weekly_digest.py -k "owner_opted_out"`

**C7** - With two businesses in the same zone, each with its own owner, the job records deliveries whose `user_id` set equals the two owners, each for their own business only: each delivery's `business_id` and `business_name` param are its own (AC 7)
Proof: `uv run pytest tests/test_weekly_digest.py -k "only_this_business_owners"`

**C8** - A business with no snapshot gets 0 rows and logs `email.digest_skipped` with its `business_id` and `reason` `no_forecast`. A business with a snapshot and no minimum balance gets 0 rows and logs the same with `reason` `no_minimum`. A third business with both still gets its digest in the same run (AC 8)
Proof: `uv run pytest tests/test_weekly_digest.py -k "skipped_without_forecast_or_minimum"`

**C9** - When building the first business's digest raises (a patched reader), the job logs `email.digest_failed` with that `business_id` and the error type, records 0 rows for it, records the second business's digest, and returns `digests_failed` 1 (AC 9)
Proof: `uv run pytest tests/test_weekly_digest.py -k "one_failure_does_not_stop_the_rest"`

**C10** - For a business with two owners, the job logs one `email.digest_requested` with `business_id`, the local Monday `2026-10-26` and `deliveries` 2, and returns `{"digests_requested": 2, "digests_failed": 0}`. A run with no business due returns both counts as 0 (AC 10)
Proof: `uv run pytest tests/test_weekly_digest.py -k "requested_logged_and_counted"`

**C11** - `jobs.JOBS` is `(nightly_bank_sync, forecast_accuracy, weekly_digest, email_retries)` in that order. `run_due(now)` returns a summary holding `weekly_digest` with both keys, and the keys `digests_requested` and `digests_failed` do not appear in any other job's counts (AC 11, door 1)
Proof: `uv run pytest tests/test_weekly_digest.py -k "registered_in_jobs"`

### S2 - The email matches its mockup · 9 files · 60 KB · ~16k

**C12** - The sample digest's subject is exactly "Your cash for the next 13 weeks". The HTML `h1` text is the same, and so is the plain-text part's first line after the label (AC 12)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "sample_heading"`

**C13** - For `monday` `2026-09-28` the label in both the HTML and the text is "Weekly forecast · Monday, Sep 28". In HTML the label comes before the `h1` (AC 13)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "label"`

**C14** - With first name "Dana", the first paragraph reads "Hi Dana, here's where Harbor Street Plumbing stands this week." in HTML and text. With no first name it reads "Here's where Harbor Street Plumbing stands this week." and the HTML has no "Hi" (AC 14)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "greeting"`

**C15** - Built from a hand-made forecast whose opening balance is 4230000, the params hold `cash_on_hand_cents` 4230000 and the HTML "Cash on hand" tile shows "$42,300". With an opening balance of -150000 it shows "−$1,500" (AC 15)
Proof: `uv run pytest tests/test_weekly_digest.py -k "cash_on_hand_from_snapshot"`
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "cash_tile"`

**C16** - Over the 13 weeks, the params' `low` is the lowest `end_balance_cents` and its week's Monday; with two weeks tied it is the earlier one. The sample's tile shows "$3,150" and "Week of Nov 9". A low of -315000 shows "−$3,150". The tile has the amber style (`background: #FFF4E2`) when the low is below the minimum, and does not when the low equals the minimum or is above it (AC 16)
Proof: `uv run pytest tests/test_weekly_digest.py -k "projected_low"`
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "low_tile"`

**C17** - On the sample the "Open alerts (1)" heading and one box read "Cash falls below your $5,000 minimum the week of Nov 9." with a link to `https://app.example.test/alerts/{alert_id}` whose text is "See the fixes". Rendered with `fix_count` 0, 1 and 2, the link text is "See details", "See the fix" and "See the fixes". With two alerts, ordered by start date, the heading reads "Open alerts (2)" and the boxes follow that order (AC 17)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "open_alerts"`
Proof: `uv run pytest tests/test_weekly_digest.py -k "alerts_by_start_date"`

**C18** - A business with no open alert and a projected low of $6,200 against a $5,000 minimum shows "All clear. Your forecast stays above your $5,000 minimum for the next 13 weeks." in HTML and text, and no "Open alerts". A low exactly equal to the minimum also shows it (AC 18)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "all_clear"`
Proof: `uv run pytest tests/test_weekly_digest.py -k "all_clear_params"`

**C19** - A business whose only alert is `dismissed` and whose low is below the minimum has `alerts` `[]` in its params. Its email shows neither "Open alerts" nor "All clear", and the low tile is amber (AC 19)
Proof: `uv run pytest tests/test_weekly_digest.py -k "dismissed_gap"`
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "dismissed_gap"`

**C20** - With a pin for last Monday, the params' `changes` hold: `cash_change_cents` as the latest opening balance minus the pin's; `low_change_cents` as the latest low minus the pin's; and `new_payments` for unmatched expected payments created on or after the start of last local Monday, at most 3, the largest amount first. Rendered, a change of +412000 reads "Cash on hand is up $4,120.", -50000 reads "Cash on hand is down $500.", and 0 omits the bullet. A low change of -60000 reads "Your projected low is $600 lower than last week.", +60000 "… $600 higher than last week.", 0 omits it. A payment reads "New expected payment: Acme Co, $8,000, on Tue, Oct 6." Bullets are in that order. Of 4 new payments only the 3 largest appear; a payment created before the cutoff, and one already matched, do not appear (AC 20)
Proof: `uv run pytest tests/test_weekly_digest.py -k "changes_since_last_monday"`
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "changes_bullets"`

**C21** - With a pin whose opening balance and low equal the latest, and no new payments, the section reads "Nothing has changed since last week." and has no bullet (AC 21)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "nothing_changed"`

**C22** - With no pin for last local Monday (a pin only for two Mondays ago, and a pin only for this Monday), the params' `changes` is `null` and the HTML and text have no "What changed since last week" (AC 22, door 4)
Proof: `uv run pytest tests/test_weekly_digest.py -k "no_baseline_pin"`
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "no_changes_section"`

**C23** - The email has exactly one button link, `https://app.example.test/`, with the text "Open your dashboard" (AC 23)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "dashboard_button"`

**C24** - The sample's plain-text part contains these lines, in this order: the label, the heading, the first paragraph, "Cash on hand", the projected low, "Open alerts (1)", the alert text, "What changed since last week", and `https://app.example.test/` (AC 24)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "plain_text_order"`

**C25** - The sample's HTML contains none of `display: flex`, `display:flex`, `grid` or `position:` (in any case). It contains no `<link`, `<script` or `<img`. The two tiles are two `<td>` in one `<tr>`. The button is a `<td>` with `bgcolor="#1D4E89"` around an `<a>` whose style sets `color: #FFFFFF` (AC 25)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "email_safe_html"`

**C26** - The sample's HTML styles the label with `color: #5A6370`, the plain tile with `#E2DDD3` in its border, the amber tile and the alert box with `background: #FFF4E2` and `#F0D3A4` in their border, the amber figure with `color: #5C3300`, the amber tile text with `color: #7A4300`, the alert box text with `color: #3D2E1C`, and the button with `#1D4E89` (AC 26)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "mockup_colours"`

**C27** - The sample digest sent through Resend shows the wordmark, label, heading, both tiles, the alerts or the all clear, the changes, the button and the footer in one column, with nothing clipped or overlapping, in Gmail (web), Outlook and Apple Mail. One screenshot per client exists in the feature folder, and you, the user, confirm what each shows (AC 27)
Proof: `test -f .specs/features/30-email-weekly-digest/gmail.png && test -f .specs/features/30-email-weekly-digest/outlook.png && test -f .specs/features/30-email-weekly-digest/apple-mail.png` (from the repo root)

**C28** - `python -m app.modules.notifications.sample_digest --to someone@example.test`, run against the fake sender, sends 1 email to that address. Its subject is the one from C12, and its HTML contains "Cash falls below your $5,000 minimum the week of Nov 9.". Without `--to`, it exits with status 2 (tooling for AC 27)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "sample_digest_command"`

**C29** - On the sample, with subscriptions registered, `run_due` at its business's Monday 2026-09-28 08:00 local sends exactly 1 email, to `dana@example.test`, with the subject from C12, whose HTML shows the low "$3,150" in "Week of Nov 9" and the alert text from C17 (AC 1, 16, 17 end to end)
Proof: `uv run pytest tests/test_weekly_digest.py -k "sample_end_to_end"`

### S3 - Nothing in the email exposes an account or signs someone in · 3 files · 18 KB · ~5k

**C30** - The sample delivery's stored `params` has exactly the keys `business_name`, `currency`, `monday`, `cash_on_hand_cents`, `minimum_cents`, `low`, `alerts` and `changes`. `low` has exactly `balance_cents` and `week_starts_on`; each alert has exactly `alert_id`, `minimum_cents`, `lowest_week_starts_on` and `fix_count`; `changes` has exactly `cash_change_cents`, `low_change_cents` and `new_payments`, whose items have exactly `name`, `amount_cents` and `date`. Neither the JSON of `params` nor the rendered HTML and text contain any sample account's `id`, `plaid_account_id` or mask (`2381`, `9025`, `5530`, `7702`), any item's `source_id`, an expected payment's `account_id`, or the owner's Clerk user id (AC 28, door 3)
Proof: `uv run pytest tests/test_weekly_digest.py -k "params_hold_no_account"`

**C31** - Every `href` in the sample's HTML is one of `https://app.example.test/`, `https://app.example.test/alerts/{alert_id}`, `https://app.example.test/settings/email` or `https://app.example.test/unsubscribe/{token}`, and each appears at least once. No `href` and no URL in the text part contains `?`. The web app protects every page except sign-in, sign-up and `/unsubscribe/[token]`, so `/` and `/alerts/[alertId]` require sign-in (AC 29)
Proof: `uv run pytest tests/test_weekly_digest_template.py -k "links"`
Proof: `npx vitest run tests/auth-protect.test.ts -t "every page protected"` (from `frontend`)

### Reads the digest depends on · 3 files · 55 KB · ~14k

**C32** - `forecasting.service` returns the forecast pinned to a given Monday as its opening balance and its projected low (lowest `end_balance_cents`, earlier week on a tie), and `None` when that Monday has no pin or the business has none. A pin of another business for the same Monday is not returned (AC 20, 22, door 4)
Proof: `uv run pytest tests/test_digest_reads.py -k "pinned_forecast"`

**C33** - `forecasting.service` returns the expected payments of a business created at or after a given moment, unmatched, with description, unsigned amount and next date. It excludes another business's payments, a payment created one second before the moment, and a one-off already matched to a transaction (AC 20)
Proof: `uv run pytest tests/test_digest_reads.py -k "payments_added_since"`

**C34** - `accounts.service` returns the ID and time zone of every business. Two businesses in different zones are both returned, with their own zone (AC 1-4, door 1)
Proof: `uv run pytest tests/test_digest_reads.py -k "all_business_zones"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| digest hour boundaries (5) | Mon 07:59 C2 · Mon 08:00 C1 · Mon 08:59 C2 · Mon 09:00 C2 · Sun 08:30 C2 | - |
| time zones in the acceptance example (3) | America/St_Johns C3 · America/Toronto C4 · America/Vancouver C4 | - |
| clock change (2) | NDT to NST, 08:30 before and after C3 · 07:30 does not send C3 | - |
| skip reasons (2) | `no_forecast` C8 · `no_minimum` C8 | - |
| recipient set (3) | every owner C1 · other business's owner C7 · opted-out owner C6 | - |
| digest block by alert state (3) | open alert C17 · none and low at or above the minimum C18 · dismissed gap C19 | - |
| alert link text by fix count (3) | 0 C17 · 1 C17 · 2 C17 | - |
| low versus minimum (3) | below C16 · equal C16 · above C16 | - |
| what changed bullets (4) | cash C20 · new payments C20 · projected low C20 · nothing changed C21 | - |
| change direction (3) | up/higher C20 · down/lower C20 · zero C20 | - |
| baseline pin (3) | present C20 · absent C22 · only other Mondays C22 | - |
| greeting (2) | first name C14 · none C14 | - |
| links in the email (4) | dashboard C31 · alert C31 · preferences C31 · unsubscribe C31 | - |
| one-way doors (4) | door 1 C11 · door 2 C5 · door 3 C30 · door 4 C32 | - |
| startup config: subscriptions and job list (2 assemblies) | API app and jobs process both call `subscriptions.register()` and read one `jobs.JOBS`, C11 · test harness C29 | - |

- C29 is the only check that crosses the real job runner end to end. C1-C10 call `weekly_digest` directly, and C12-C26 render a template, so each is proven at its own layer.
- No other check claims more than the cases its proof exercises.

## Swept

- validation: C16 and C18 cover the equal edges; a non-CAD currency raises in the `money` filter and spec 28 fails a delivery that can't render
- failure modes: C9 - one business failing does not stop the rest; a render error fails one delivery (spec 28)
- idempotency: C5
- authorization: C7, C31
- concurrency: existing - `uq_email_deliveries_dedup_key_user_id` with `ON CONFLICT DO NOTHING` and the `SKIP LOCKED` claim (AD-106, AD-107). Two overlapping job runs dedup the same way as C5
- data lifecycle: n/a - no new stored data; deliveries keep spec 28's lifecycle, and pins keep spec 22's
- dependency failure: existing - a Clerk or Resend failure keeps the delivery `pending` for `email_retries` (AD-107, spec 28 C17); the digest request phase calls neither
- state transitions: C19 - only an `open` alert is listed; a dismissed gap changes the block
- observability: C8, C9, C10

## Out of scope

- see plan.md `## Out of scope`

## Handoff

- S1 = ~20k, S2 = ~16k, S3 = ~5k, reads = ~14k. In bytes: `forecasting/service.py` 44 KB, `forecasting/repository.py` 12 KB, `accounts` service and repository 12 KB, `notifications/service.py` 12 KB, `rendering.py` 3 KB, `subscriptions.py` and `jobs/__init__.py` 3 KB, new job and templates ~14 KB, new tests ~40 KB, sample command ~3 KB. That's ~145 KB, or ~36k tokens, all in `notifications` with read-only hops into `forecasting`, `alerts` and `accounts`. That is under the 150k budget, so one builder.
- Mechanism: one builder (under budget, no ask)

- **Boundary:** C1-C34 written, not closed. Proofs run on this PC: all of `tests/test_weekly_digest_template.py` (C12-C14, C15 and C16 rendering, C17, C18, C19, C20 rendering, C21-C26, C28, C31 rendering; 18 passed), plus ruff and mypy. Every proof that needs Postgres (`tests/test_weekly_digest.py`, `tests/test_digest_reads.py`) is collected (48 tests in all) but not run: this PC has no Postgres or Docker, as in spec 29. They run on the user's other computer before the Verifier
- **Settled mid-build:** `tests/test_run_due.py::test_jobs_registered` now expects `weekly_digest` before `email_retries` (AC 11); the sample-based tests (C29, C30) call `send_sample()` from spec 29 inside an isolated database and run last in the file, because the planting helpers clear every forecast
- **Abandoned:** nothing
