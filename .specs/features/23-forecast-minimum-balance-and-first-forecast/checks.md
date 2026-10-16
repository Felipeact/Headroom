# 23 - Minimum balance and the first forecast checks

Profile: light
Plan: `.specs/features/23-forecast-minimum-balance-and-first-forecast/plan.md`

34 checks in 5 slices · 5 one-way doors · 0 open, of which 0 block

`uv run` proofs run from `services/core`, and `npx` proofs from `frontend`. API tests use spec 20's `cash_business()` (Operating checking and Reserve savings included, Visa excluded) and write transactions through the real sync with a fake Plaid client. The request clock is overridden through `get_now`. The e2e proofs need the stack from `playwright.config.ts` (API on 8100, the Plaid sandbox, and Clerk test users).

## Checks

### S1 - The owner sets a minimum balance through the API · 8 files · 150 KB · ~38k

**C1** - `GET .../minimum-balance` on a business with no stored minimum answers `200` with exactly the keys `amount_cents`, `currency`, `suggested_cents`, `updated_at`; `amount_cents` null, `updated_at` null, `currency` `CAD` (AC 1, door 2)
Proof: `uv run pytest tests/test_minimum_balance_api.py -k "unset_shape"`

**C2** - `PUT` `{"amount_cents": 500000}` answers `200` with `amount_cents` 500000 and a non-null `updated_at`; a following `GET` answers `amount_cents` 500000. A second `PUT` of 250000 answers 250000, and the table still holds one row for the business (AC 2, door 1)
Proof: `uv run pytest tests/test_minimum_balance_api.py -k "put_then_get"`

**C3** - The suggestion is 2 × the median weekly money out, rounded up to the next 10000 cents. Today is Saturday 2026-09-26 (Toronto), so the 13 complete weeks are Monday 2026-06-22 to Sunday 2026-09-20. Week outflows (absolute) on included accounts: 12 weeks at 230000 and one at 900000 give median 230000, so the suggestion is 460000. Adding one 4567-cent outflow to every week makes the median 234567, and the suggestion rounds up to 470000 (AC 3)
Proof: `uv run pytest tests/test_minimum_balance_suggestion.py -k "median_rounded_up"`

**C4** - These don't count towards money out: inflows; outflows labelled `internal_transfer` or `in_transit`; outflows on the excluded Visa account; outflows dated in the current, incomplete week (2026-09-21 to 09-26); and outflows before 2026-06-22. Each one, added to C3's base data, leaves the suggestion at 460000 (AC 3)
Proof: `uv run pytest tests/test_minimum_balance_suggestion.py -k "what_counts"`

**C5** - With outflows only from Monday 2026-09-07 on (2 complete weeks: 100000 and 300000), only weeks from the oldest outflow's week count: the median of [100000, 300000] is 200000, so the suggestion is 400000. (AC 3)
Proof: `uv run pytest tests/test_minimum_balance_suggestion.py -k "short_history"`

**C6** - `suggested_cents` is null with no transactions, and null when the only outflows fall in the current incomplete week (AC 4)
Proof: `uv run pytest tests/test_minimum_balance_suggestion.py -k "no_complete_week"`

**C7** - `PUT` answers `422` problem details for each of `-1`, `1000000001`, `12.5`, `"5000"`, a missing `amount_cents`, `null`, and `{"amount_cents": 1, "currency": "USD"}`; `0` and `1000000000` answer `200`. After the rejected ones, `GET` still shows the last stored value (AC 5)
Proof: `uv run pytest tests/test_minimum_balance_api.py -k "body_bounds"`

**C8** - The first `PUT` and a `PUT` with a different value each write one audit row `minimum_balance.changed`, `target_type` `minimum_balance`, `details` `{"amount_cents": <new>}`, with the caller as actor. Each publishes one `forecast_inputs.changed` with payload exactly `{"source": "minimum_balance"}`, and a new session inside the handler already sees the new amount (published after commit) (AC 6, door 3)
Proof: `uv run pytest tests/test_minimum_balance_api.py -k "audit_and_event"`

**C9** - A `PUT` with the stored amount answers `200` and adds no audit row and no event (AC 7, door 3)
Proof: `uv run pytest tests/test_minimum_balance_api.py -k "same_amount_quiet"`

**C10** - A signed-in user with no membership, and an owner of another business, get `404` "Business not found." on `GET` and `PUT .../minimum-balance` and `GET .../forecast/status`; no token gets `401`. A member whose role isn't `owner` gets `403` "You don't have permission to do this." on `PUT`, and nothing is stored (AC 8, door 2)
Proof: `uv run pytest tests/test_minimum_balance_api.py -k "access_denied"`

**C11** - The migration creates `minimum_balances` with primary key `business_id`; inserting `amount_cents` -1 violates `ck_minimum_balances_amount_cents_nonnegative`; a second row for the same business violates the primary key; `alembic downgrade -1` drops the table (door 1)
Proof: `uv run pytest tests/test_migrations.py -k "minimum_balances"`

**C12** - Through the real handler chain (`subscriptions.register()`), a first `PUT` on a business whose transactions already synced and whose forecast exists runs `recompute_forecast`, which logs `forecast.unchanged` and stores no new snapshot (door 3, Impact)
Proof: `uv run pytest tests/test_minimum_balance_api.py -k "recompute_unchanged"`

### S2 - Step 5 knows when the first forecast is ready · 4 files · 110 KB · ~28k

**C13** - `GET .../forecast/status` answers `200` with exactly the keys `state`, `institution_names`, `transactions_read`, `history_months`, `recurring_count`, `recurring_names` (AC 13, door 4)
Proof: `uv run pytest tests/test_forecast_status.py -k "shape"`

**C14** - A business whose only connection has an included account with `last_synced_at` null answers `state` `building` and `transactions_read` false. This holds even after a `PUT` minimum balance has stored a snapshot (AC 9, AC 14)
Proof: `uv run pytest tests/test_forecast_status.py -k "never_synced_building"`

**C15** - After a sync through the real handlers, the status is `ready` and `transactions_read` true (AC 10)
Proof: `uv run pytest tests/test_forecast_status.py -k "synced_ready"`

**C16** - Synced, with `last_synced_at` set, it answers `building` when no snapshot exists, and `building` when a payment is planted straight into `expected_payments` after the last recompute (the fingerprint differs); after `recompute_forecast` it answers `ready` (AC 11)
Proof: `uv run pytest tests/test_forecast_status.py -k "stale_fingerprint_building"`

**C17** - The order of AC 14: `PUT` minimum balance before the first sync (snapshot from balances only) answers `building`; after the sync commits and its handlers run, `ready` (AC 14)
Proof: `uv run pytest tests/test_forecast_status.py -k "minimum_before_sync"`

**C18** - A connection with an included account and `login_required` true answers `needs_attention`, even when otherwise `ready`. A `login_required` connection with no included account doesn't change the state (AC 12)
Proof: `uv run pytest tests/test_forecast_status.py -k "needs_attention"`

**C19** - With two connections, `institution_names` lists them oldest first. `history_months` is 0 for an oldest included-account transaction on 2026-09-01 (today 2026-09-26), 3 for 2026-06-26, 2 for 2026-06-27, 24 for 2024-09-26, and null with no transactions; a transaction only on the excluded Visa doesn't count. `recurring_count` equals the stored patterns; `recurring_names` holds the 2 largest by absolute amount, as `counterparty`, else `description` when the counterparty is null; with one pattern, one name; with none, `[]` (AC 13)
Proof: `uv run pytest tests/test_forecast_status.py -k "details"`

### S3 - Onboarding step 4 screen · 9 files · 110 KB · ~28k

**C20** - With no stored minimum and `suggested_cents` 500000, step 4 renders "Step 4 of 5", heading "Set your minimum balance", the subtitle, a textbox labelled "Minimum balance" with value "5,000", "Suggested: $5,000, about two weeks of your typical spending.", "How alerts work" with "If your forecast dips below $5,000, you get an email that names the payments causing it and suggests ways to fix it.", "You can change this at any time in Settings." and a "Continue" button (AC 15)
Proof: `npx vitest run tests/minimum-balance-page.test.tsx -t "suggested"`

**C21** - With `amount_cents` 1200000 stored and a suggestion of 500000, the input shows "12,000" and the alerts card names $12,000 (AC 16)
Proof: `npx vitest run tests/minimum-balance-page.test.tsx -t "stored"`

**C22** - With `suggested_cents` null and nothing stored, the input is empty, no "Suggested" text is present, and the card reads "If your forecast dips below your minimum balance, you get an email that names the payments causing it and suggests ways to fix it." (AC 17)
Proof: `npx vitest run tests/minimum-balance-page.test.tsx -t "no suggestion"`

**C23** - Typing "7,500" makes the card name $7,500; typing "abc" keeps the card naming the last valid amount (AC 18)
Proof: `npx vitest run tests/minimum-balance-form.test.tsx -t "card follows input"`

**C24** - `parseWholeDollars` returns 500000 for "5000", "5,000", "$5,000" and " 5000 ", and 0 for "0", and 1000000000 for "10,000,000"; null for "", "abc", "5000.50", "-5", and "10,000,001". Continue with "", "5000.50" or "10,000,001" shows "Enter a whole-dollar amount from $0 to $10,000,000." linked to the input by `aria-describedby`, with `aria-invalid` true, and calls no action (AC 19)
Proof: `npx vitest run tests/format.test.ts -t "parseWholeDollars"`
Proof: `npx vitest run tests/minimum-balance-form.test.tsx -t "invalid input"`

**C25** - Continue with "7,500" calls `saveMinimumBalance(businessId, 750000)`; on `{ error: null }` the router pushes `/onboarding/forecast`. The action `PUT`s `{"amount_cents": 750000}` with the auth headers and returns `{ error: null }` on `200` (AC 20)
Proof: `npx vitest run tests/minimum-balance-form.test.tsx -t "saves and moves on"`
Proof: `npx vitest run tests/minimum-balance-action.test.ts -t "puts cents"`

**C26** - When the action answers `{ error: "saveFailed" }` (the API returned 500, or threw), an alert shows "We couldn't save your minimum balance. Try again.", the input keeps "7,500", and the router doesn't move (AC 21)
Proof: `npx vitest run tests/minimum-balance-form.test.tsx -t "save fails"`
Proof: `npx vitest run tests/minimum-balance-action.test.ts -t "save failed"`

**C27** - When `GET .../minimum-balance` answers 500, step 4 renders `LayoutError` and no form (AC 22)
Proof: `npx vitest run tests/minimum-balance-page.test.tsx -t "load fails"`

**C28** - Step 3's Continue, with an included account, pushes `/onboarding/minimum-balance` (AC 23)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "continue goes to step 4"`

### S4 - Onboarding step 5 screen · 7 files · 70 KB · ~18k

**C29** - With status `building`, `transactions_read` true, `history_months` 24, `recurring_count` 11 and names ["Payroll", "Rent"], step 5 renders "Step 5 of 5", "Building your forecast", "This usually takes a minute or two.", a `role="status"` region with "Connected Harbor Community Bank" (done), "Read 24 months of transactions" (done), "Finding recurring payments" with "Payroll, Rent, and 9 others so far" (in progress), "Building your 13-week forecast" (pending), and "You'll go to your dashboard as soon as it's ready." Each step exposes its state as `data-state` `done`, `active` or `pending` (AC 24, AC 25)
Proof: `npx vitest run tests/forecast-step-page.test.tsx -t "building"`

**C30** - Step texts across the states: `transactions_read` false shows "Reading your transactions" as `active`, and "Finding recurring payments" `pending`; `history_months` null with `transactions_read` true shows "Read your transactions"; `history_months` 1 shows "Read 1 month of transactions"; `recurring_count` 0 shows no sub-line; 1 shows "Payroll so far"; 2 shows "Payroll and Rent so far"; 3 shows "Payroll, Rent, and 1 other so far"; two institutions show "Connected Bank A and Bank B" (AC 25)
Proof: `npx vitest run tests/forecast-progress.test.tsx -t "step texts"`

**C31** - While `building`, the progress component calls `router.refresh()` every 3000 ms (fake timers: 0 calls at 2999 ms, 1 at 3000, 2 at 6000), and stops after unmount. After 180000 ms it shows "This is taking longer than usual. You can go to your dashboard; your forecast will appear there when it's ready." with a link to `/`, and keeps refreshing; at 179999 ms it doesn't (AC 26, AC 29)
Proof: `npx vitest run tests/forecast-progress.test.tsx -t "polls"`

**C32** - On `ready`, step 5's page doesn't redirect on the server; it renders all four steps `done` and calls `router.replace('/')` at 2000 ms (not at 1999 ms) (amended with the user, 2026-10-09). On `needs_attention` it shows "Your bank needs you to log in again." with a link to `/settings/banks` and doesn't refresh (0 calls after 9000 ms). When `GET .../forecast/status` answers 500 it renders `LayoutError`. With `amount_cents` null it redirects to `/onboarding/minimum-balance` (AC 27, AC 28, AC 30, AC 31)
Proof: `npx vitest run tests/forecast-step-page.test.tsx -t "states"`
Proof: `npx vitest run tests/forecast-progress.test.tsx -t "ready"`
Proof: `npx vitest run tests/forecast-progress.test.tsx -t "needs attention"`

### S5 - Both screens meet the screen rules · 3 files · 40 KB · ~10k

**C33** - Both step pages redirect to `/onboarding/business` when the business list is empty, and to `/onboarding/bank` when the business has no connection (AC 34)
Proof: `npx vitest run tests/minimum-balance-page.test.tsx -t "redirects"`
Proof: `npx vitest run tests/forecast-step-page.test.tsx -t "redirects"`

**C34** - The Done-when e2e: a new user signs in, completes step 2, connects TD Canada Trust in the Plaid sandbox, presses Continue on step 3, reaches step 4 with the input prefilled or empty, then uses the keyboard alone (Tab to the input, type "5,000", press Enter) and reaches step 5's "Building your forecast" (shown at least while its 2-second finish runs). At 375 px wide both screens have no horizontal scroll, `Continue` is at least 44 px tall, and axe finds no violations on either. Then step 5 redirects to `/` within 120 s (AC 20, AC 24, AC 27, AC 32, AC 33; Done when 1)
Proof: `npx playwright test e2e/minimum-balance-onboarding.spec.ts -g "C34"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /v1/businesses/{business_id}/minimum-balance` statuses (3) | 200 C1 · 401 C10 · 404 C10 | - |
| `PUT /v1/businesses/{business_id}/minimum-balance` statuses (5) | 200 C2 · 401 C10 · 403 C10 · 404 C10 · 422 C7 | - |
| `GET /v1/businesses/{business_id}/forecast/status` statuses (3) | 200 C13 · 401 C10 · 404 C10 | - |
| `state` values (3) | `building` C14 · `ready` C15 · `needs_attention` C18 | - |
| `state` precedence (3 rules) | login_required wins C18 · never-synced is building C14 · stale fingerprint is building C16 | - |
| `amount_cents` bounds (4 edges) | -1 C7 · 0 C7 · 1000000000 C7 · 1000000001 C7 | - |
| money-out exclusions (6) | inflow C4 · `internal_transfer` C4 · `in_transit` C4 · excluded account C4 · current week C4 · before 13 weeks C4 | - |
| suggestion outcomes (4) | median of 13 C3 · rounding up C3 · short history C5 · null C6 | - |
| doors (5) | 1 C11, C2 · 2 C1, C10 · 3 C8, C9, C12 · 4 C13-C19 · 5 C33, C32, C34 | - |
| step 5 step states (3) | `done` C29 · `active` C29, C30 · `pending` C29, C30 | - |
| step 5 page states (6) | building C29 · ready C32 · needs_attention C32 · slow C31 · load failed C32 · no minimum C32 | - |
| step 4 page states (6) | suggested C20 · stored C21 · no suggestion C22 · invalid input C24 · save failed C26 · load failed C27 | - |
| onboarding redirects (4) | step 4 no business C33 · step 4 no bank C33 · step 5 no business C33 · step 5 no bank C33 | - |

- Claims naming a status code, route or response shape: C1, C2, C7, C10, C13 - each proof calls the route through `TestClient`.
- Startup config: no subscription is added. `forecast_inputs.changed` -> `recompute_forecast` is already registered in both `lifespan` and `run_due.main()` (AD-055); C12 runs it through `subscriptions.register()`.
- C34 is the only e2e. It proves the path works end to end and the screen rules. It doesn't stand in for the per-state proofs above.

## Swept

- validation: C7 (body bounds and types), C24 (input parsing), C11 (database check)
- failure modes: C26 (save fails, value kept), C27 and C32 (load fails); a `PUT` that raises before commit publishes nothing, because the event is published after `session.commit()` (C8 asserts the new session sees the row)
- idempotency: C9 (same amount: no audit, no event), C2 (one row per business on repeat), C12 (recompute on an unchanged fingerprint writes nothing)
- authorization: C10 (stranger 404, non-owner 403 on `PUT`, no token 401), all three routes
- concurrency: n/a - two owners' `PUT`s race to one primary-key row; the upsert's last writer wins, and both answer with what they wrote. v1 has one owner per business (AD-030)
- data lifecycle: n/a - one row per business, kept for its life; there's no backfill (plan, Impact: existing businesses read `amount_cents` null)
- dependency failure: C14 and C18 (Plaid's sync hasn't landed, or needs a login, so step 5 waits or says so); no external call is made by these routes
- state transitions: C14 -> C15 and C17 (`building` to `ready`), C16 (`ready` back to `building` when inputs change), C18 (`needs_attention`)
- observability: C8 (audit entry `minimum_balance.changed`), C12 (`forecast.unchanged` log on the recompute it triggers)

## Handoff

- S1-S2 read and touch: `forecasting/{api,service,models,repository,engine}.py` (about 50 KB), `bank_sync/service.py` 42 KB (read), `auth.py` 4 KB, `audit.py` 3 KB, `tests/test_expected_payments_api.py` 22 KB and `tests/test_forecast_recompute.py` 25 KB as models, `tests/test_migrations.py` 33 KB (append), `contracts/openapi.json` 70 KB (generated). New: the migration, 3 test files, about 30 KB. About 280 KB.
- S3-S5 read and touch: the onboarding pages and components (about 25 KB), `lib/format.ts` 5 KB, `messages/en.json` 20 KB, `lib/api/schema.d.ts` 60 KB (generated), the two mockups 9 KB, `tests/accounts-page.test.tsx` and `tests/choose-accounts.test.tsx` 20 KB as models, `e2e/expected-payments.spec.ts` 15 KB. New: 2 pages, 2 components, 1 action, 1 loader, 5 test files and 1 e2e file, about 45 KB. About 200 KB.
- 480 KB / 4 = ~120k, under the 150k budget - one builder

- **Boundary:** C1-C34 built by one builder; S1-S2 at a473e3c, S3-S4 at 507d728
- **Settled mid-build:** 2026-10-09, the user chose "brief finish": on the sandbox the forecast is ready before step 5 loads, so AC 27 and C32 now show all steps done and replace the route with `/` after 2 s instead of a server redirect (AD-092). Pattern `counterparty` is NOT NULL, so C19's "else description" branch is exercised with an empty counterparty
- **Abandoned:** an e2e that accepted skipping step 5 when already ready - it would have passed without ever showing the screen Done-when 1 names
