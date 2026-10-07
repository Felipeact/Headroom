# 21 - The 13-week forecast checks

Profile: light
Plan: `.specs/features/21-forecast-engine/plan.md`

44 checks in 5 slices · 6 one-way doors · 0 open, of which 0 block

All `uv run` proofs run from `services/core`. Pure strategy tests build `ForecastInputs` by hand. Database tests write synthetic transactions through `bank_sync`'s sync service with a fake Plaid client, as spec 20's tests do. Clocks are passed in, never read from the wall.

## Checks

### S1 - Every business gets a 13-week forecast · 9 files · 120 KB · ~30k

**C1** - Handling one `transactions.synced` stores one snapshot with exactly 13 `forecast_weeks` rows numbered 1-13, each `starts_on` the Monday door 6 gives (AC 1)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "stores_thirteen_weeks"`

**C2** - The opening balance is the sum over included CAD accounts. In one business with a checking account at 100000, a savings account at 50000, a savings account with a null balance, an excluded checking account at 70000, a credit card at 9000, a line of credit at 30000 and a USD checking account at 40000, the opening balance is 150000 (AC 2)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "opening_balance"`

**C3** - For each week, `money_in_cents` is the sum of its positive items, `money_out_cents` is the sum of its negative items (0 or less), and `end_balance_cents` is the previous end (the opening balance for week 1) plus both. Proven on inputs with items in weeks 1, 2 and 13 and none in week 3 (AC 3)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "week_totals"`

**C4** - For both strategies, every item has an `account_id`, a date from today to the window end, and a `week` whose Monday-to-Sunday range holds its date (week 1 also holds today to its Monday). Each week's `item_ids` in the API are exactly its items' IDs, ordered by `date`, `source`, `id` (AC 4, door 4)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "items_in_their_weeks"`
Proof: `uv run pytest tests/test_forecast_api.py -k "week_item_ids"`

**C5** - Both strategies return 13 weeks without raising on inputs with no transactions, with 2 weeks of transactions, and with 2 years of transactions (6 cases) (AC 5)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "history_lengths"`

**C6** - Through the real path (sync, then handlers, then `GET .../forecast`), a business with no transactions, one with 2 weeks and one with 2 years each answer `200` with 13 weeks (AC 5, spec 21 "Done when" 1)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "done_when_history_lengths"`

**C7** - With no transactions, no patterns, no open occurrences and no card balance, every one of the 13 week ends equals the opening balance, and there are no items (AC 5)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "empty_is_flat"`

**C8** - A selected strategy that raises, and one that returns 12 weeks, each lead to a stored snapshot with `strategy` = `rolling_average` and the `rolling_average` weeks, plus one `forecast.strategy_failed` log with `business_id`, `strategy` and `error_type` (AC 6, door 2)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "strategy_fallback"`

**C9** - `Settings().forecast_strategy` is `recurring_pattern` with no `FORECAST_STRATEGY` set. `rolling_average` is accepted. `FORECAST_STRATEGY=average` fails validation, naming the field (door 2)
Proof: `uv run pytest tests/test_settings.py -k "forecast_strategy"`

**C10** - With `FORECAST_STRATEGY=rolling_average`, a recompute stores `strategy` = `rolling_average`. `STRATEGIES` holds exactly `recurring_pattern` and `rolling_average`, each a `ForecastStrategy` whose `name` is its key (door 2)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "strategy_setting_selects"`

**C11** - Door 6's week starts, for an `America/Toronto` business:
- at Saturday 2026-09-26 10:00 UTC, week 1 starts 2026-09-28 and week 13 starts 2026-12-21
- at Monday 2026-09-28 14:00 UTC, week 1 starts 2026-09-28
- at Monday 2026-09-28 02:00 UTC (still Sunday in Toronto), week 1 starts 2026-09-28 and today is 2026-09-27

An item dated on Saturday 2026-09-26 counts in week 1 (door 6)
Proof: `uv run pytest tests/test_forecast_engine.py -k "week_starts"`

### S2 - `recurring_pattern` projects named payments and an estimate of the rest · 6 files · 90 KB · ~23k

**C12** - A biweekly pattern with `next_date` 2026-10-02 gives items on 2026-10-02, 10-16, 10-30, 11-13, 11-27 and 12-11, and none after the window end. A monthly pattern anchored on the 15th gives 2026-11-16 for November, because the 15th is a Sunday. Each item carries the pattern's amount, description, counterparty, schedule and account, and `source_id` = the pattern's ID (AC 7)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "pattern_occurrences"`

**C13** - A pattern whose `next_date` is 3 days before today gives an item dated today, followed by its later occurrences on the cadence (AC 7)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "late_pattern_today"`

**C14** - A pattern on an excluded account, and one on a USD account, give no items (AC 7, definitions)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "pattern_account_not_cash"`

**C15** - Each open occurrence on an included account gives one `expected_payment` item with its amount, description, account, `schedule` = `repeats` and `source_id` = the payment's ID. An overdue one-off is dated today. A matched occurrence gives no item, and neither does a payment on an excluded account (AC 8)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "expected_items"`

**C16** - AC 9's de-duplication on one expected item of -100000 on 2026-11-12:
- a recurring item of -109000 on 2026-11-13, same account: dropped, expected kept
- -111000: both kept
- 8 days apart: both kept
- +100000: both kept
- another account: both kept

When two recurring items qualify, the one with the smaller day difference is dropped. A recurring item pairs with at most one expected item (AC 9)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "expected_wins_over_recurring"`

**C17** - A card with balance 245000, whose last 3 linked cash-side payments were on the 8th, 9th and 8th for 250000, 260000 and 270000, gives:
- with today 2026-09-26: -245000 on 2026-10-08
- then -260000 on 2026-11-09 (the 8th is a Sunday) and on 2026-12-08

Each item has the cash-side account, `description` = the card's name and `source_id` = the card's ID (AC 10)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "card_payments"`

**C18** - A card whose latest card-side `card_payment` is unlinked, or linked to an excluded account, gives no items. A linked card with a balance of 0, or a null balance, gives no first item but still gives the later monthly items (AC 10)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "card_payment_edges"`

**C19** - The estimate's window and exclusions. Each of these is left out of a seeded estimate, and changing it changes no estimate item:
- a transaction dated today
- one dated 7·k+1 days ago
- one listed in a pattern's `transaction_ids`
- one matched to an expected payment
- one labelled `internal_transfer`, `in_transit` or `card_payment`
- one on an excluded account

A `normal` transaction dated yesterday changes it (AC 11)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "estimate_window_and_exclusions"`

**C20** - `k` is 1 when the oldest transaction is 3 days old, 2 when it is 14 days old, 13 when it is 2 years old, and no estimate item exists with no transactions. With k = 2 and an account's in-transactions totalling 300001, each week has one in item of 150000 on that account, and out-transactions totalling -300003 give one out item of -150002 (AC 11, rounding half to even: 150000.5 -> 150000)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "estimate_k_and_amounts"`

**C21** - Estimate items are dated each week's Monday, and week 1's is dated today when today is that Monday or earlier. They have null `description`, `counterparty`, `schedule` and `source_id`, and an account with a zero total in a direction has no item for it (AC 11)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "estimate_item_shape"`

**C22** - With weekly net estimate totals of 100000, 300000, 200000 and 400000 (k = 4, σ = 111803.3988...), week n's `low_cents` and `high_cents` are `end_balance_cents` -/+ round(σ·√n): 111803 for week 1 and 403113 for week 13. With k = 1 every week has low = end = high (AC 12)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "band"`

**C23** - On Harbor Street Plumbing (seed 0) with today 2026-09-26, the non-estimate items are exactly AC 13's list:
- 6 payrolls
- 3 rents
- 3 software items
- the 2026-10-08 -245000 card payment, plus the card's later items
- the 4 expected payments

Every named reference future item except the 2026-12-24 payroll and the 2026-11-09 and 2026-12-08 card payments is matched by date and amount (AC 13)
Proof: `uv run pytest tests/test_forecast_sample.py -k "named_items"`

### S3 - `rolling_average`, the fallback · 2 files · 30 KB · ~8k

**C24** - `rolling_average` on inputs with a pattern, a linked card and an open expected occurrence gives no `recurring_pattern` and no `card_payment` items, gives the `expected_payment` item, and gives estimate items averaged over every transaction in AC 11's window. It includes those labelled `normal`, `card_payment`, `credit_draw` and `credit_repayment`, and leaves out `internal_transfer`, `in_transit` and expected-matched ones (AC 14)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "rolling_average_items"`

**C25** - `rolling_average`'s band uses its own weekly totals. With the C22 totals plus a weekly -50000 `card_payment`, its week-1 band half-width equals the population σ of those shifted totals (unchanged, 111803), and with a varying card payment it differs from `recurring_pattern`'s (AC 15)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "rolling_average_band"`

### S4 - Recompute once per real change · 7 files · 110 KB · ~28k

**C26** - `SUBSCRIPTIONS` is exactly, in order: `(transactions.synced, refresh_recurring_patterns)`, `(transactions.synced, match_expected_payments)`, `(transactions.synced, recompute_forecast)`, `(forecast_inputs.changed, recompute_forecast)` (AC 16, door 3)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "subscriptions_order"`

**C27** - Handling the same `transactions.synced` event twice leaves one `forecast_snapshots` row for the business, and the recording handler receives one `forecast.updated` (AC 17, spec 21 "Done when" 2)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "same_event_twice"`

**C28** - After an expected payment is added and then deleted:
- the latest snapshot's `id` is the one from before the add
- the business has exactly 2 snapshot rows
- 3 `forecast.updated` events were published (initial, add, delete), the last carrying the first snapshot's ID (AC 18, door 1)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "inputs_revert"`

**C29** - Two threads recomputing one business at the same moment both finish, and leave one snapshot row per fingerprint. With a 1-second sleep injected inside the first recompute's lock, the second starts its write only after the first commits (AC 19)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "concurrent_recomputes"`

**C30** - A new latest snapshot publishes exactly one `forecast.updated`, after the commit (the handler sees the row from a fresh session), with the business's ID and payload exactly `{"snapshot_id": "<id>"}`. A strategy and a fallback that both raise roll back: the earlier latest snapshot stays, nothing is published, and `event.handler_failed` is logged (AC 20, door 3)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "updated_event_after_commit"`
Proof: `uv run pytest tests/test_forecast_recompute.py -k "failure_keeps_latest"`

**C31** - The fingerprint is 64 lowercase hex characters. It does not change when a pattern refresh issues new pattern IDs with the same content. It changes when the strategy, a balance, today or an open occurrence changes (door 1)
Proof: `uv run pytest tests/test_forecast_engine.py -k "fingerprint"`

**C32** - The migration creates the 3 tables, and upgrade, downgrade and upgrade run cleanly. The database rejects:
- a second snapshot with the same `(business_id, inputs_sha256)`
- week number 0 or 14
- item source `other`
- item amount 0

Deleting a snapshot deletes its weeks and items. `alembic check` then finds no difference (door 1)
Proof: `uv run pytest tests/test_migrations.py -k "forecast_snapshots_upgrade_downgrade_and_check"`

**C33** - The sample's 2026-12-25 payroll is not an item (2026-12-29 is past week 13). A monthly occurrence on Saturday 2026-11-07 moves to Monday 2026-11-09 (AC 21)
Proof: `uv run pytest tests/test_forecast_strategies.py -k "holiday_rule"`

**C34** - `update_account` changing `included` publishes exactly one `forecast_inputs.changed` after its commit, with payload `{"source": "bank_accounts", "account_id": "<id>"}`. Changing only `primary` publishes none, and a rejected change publishes none (AC 22, door 5)
Proof: `uv run pytest tests/test_bank_accounts.py -k "inclusion_change_publishes"`

**C35** - A written snapshot logs one `forecast.updated` with exactly `business_id`, `snapshot_id`, `strategy`, `items` and `duration_ms`. An unchanged fingerprint logs `forecast.unchanged` with `business_id` only. Neither log line holds an amount, a description or a counterparty from the inputs (AC 23)
Proof: `uv run pytest tests/test_forecast_recompute.py -k "logged_without_amounts"`

### S5 - The owner reads the forecast and the next payments · 6 files · 120 KB · ~30k

**C36** - `GET .../forecast` answers `200` with exactly door 4's fields:
- `id`, `as_of`, `computed_at`, `strategy`, `currency`, `opening_balance_cents`, `incomplete`, `weeks`, `items`
- in each week: `number`, `starts_on`, `ends_on`, `end_balance_cents`, `low_cents`, `high_cents`, `money_in_cents`, `money_out_cents`, `item_ids`
- in each item: `id`, `date`, `account_id`, `amount_cents`, `currency`, `source`, `source_id`, `description`, `counterparty`, `schedule`

Weeks are numbered 1-13 in order, `ends_on` is `starts_on` + 6 days, and items are ordered by `date`, `source`, `id` (AC 24, door 4)
Proof: `uv run pytest tests/test_forecast_api.py -k "forecast_shape"`

**C37** - A business with no snapshot answers `404` with detail "Forecast not ready." on both `GET .../forecast` and `GET .../upcoming` (AC 24, AC 26)
Proof: `uv run pytest tests/test_forecast_api.py -k "not_ready"`

**C38** - `incomplete` with a request clock `now`, one row per case:
- all included connections synced 47 hours ago: false
- one synced exactly 48 hours ago: false
- 48 hours and 1 second ago: true
- `last_synced_at` null: true
- `login_required`: true
- `sync_failing` (3 failed nights): true
- a connection with only excluded accounts that is failing: false

The flag changes with the request clock and no new snapshot (AC 25, door 4)
Proof: `uv run pytest tests/test_forecast_api.py -k "incomplete_cases"`

**C39** - `GET .../upcoming?days=N` returns the latest snapshot's non-estimate items dated from today to today + N - 1, ordered by `date`, `source`, `id`:
- with N omitted, the range is 14 days
- an item dated today + N is left out; one dated today + N - 1 is kept
- an estimate in range is left out
- `days` = 0, 91 and `x` each answer `422`; 1 and 90 answer `200`

(AC 26)
Proof: `uv run pytest tests/test_forecast_api.py -k "upcoming_range"`

**C40** - On the sample (seed 0, today 2026-09-26), `GET .../upcoming?days=14` returns exactly 4 items in this order: Payroll -1120000 2026-10-02, "Acme Co, invoice 1042" +800000 2026-10-06, Software subscriptions -64000 2026-10-07, Business Visa -245000 2026-10-08 (AC 26)
Proof: `uv run pytest tests/test_forecast_sample.py -k "upcoming_next_14_days"`

**C41** - A recompute for a business with 2 years of history (20 included-account transactions per business day, 3 patterns, 4 expected payments) takes under 2.0 seconds of wall time, measured once from the handler's start to its commit against the local test database (AC 27, spec 21 "Done when" 3)
Proof: `uv run pytest tests/test_forecast_performance.py -k "two_years_under_two_seconds"`

**C42** - Both routes: a non-member gets `404` "Business not found.", a bookkeeper member gets `403`, and a non-UUID `business_id` gets `422`. An owner of business A asking for business B's ID gets `404`, and never B's forecast or items (AC 28)
Proof: `uv run pytest tests/test_forecast_api.py -k "access_denied"`

**C43** - Regenerating `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` leaves no diff. The contract has `get` on `/v1/businesses/{business_id}/forecast` and on `/v1/businesses/{business_id}/upcoming`, and the latter has an integer `days` query parameter (door 4)
Proof: `bash .specs/features/21-forecast-engine/proofs.sh c43`

**C44** - Every AGENTS.md check for the API passes: ruff format, ruff check, mypy and the whole pytest suite. The web app's lint, typecheck, test and build pass with the regenerated types (AGENTS.md "Before you finish")
Proof: `bash .specs/features/21-forecast-engine/proofs.sh c44`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET .../forecast` statuses (4) | 200 C36 · 403 C42 · 404 C37, C42 · 422 C42 | - |
| `GET .../upcoming` statuses (4) | 200 C39, C40 · 403 C42 · 404 C37, C42 · 422 C39, C42 | - |
| item sources (4) | `recurring_pattern` C12 · `expected_payment` C15 · `card_payment` C17 · `estimate` C21 | - |
| strategies (2) | `recurring_pattern` C5, C10, C12-C23 · `rolling_average` C5, C8, C10, C24, C25 | - |
| fallback triggers (2) | raises C8 · wrong week count C8 | - |
| history lengths (3) | none C5, C6, C7 · 2 weeks C5, C6, C20 · 2 years C5, C6, C20, C41 | - |
| opening balance accounts (7) | included checking C2 · included savings C2 · null balance C2 · excluded C2 · credit card C2 · line of credit C2 · non-CAD C2 | - |
| estimate exclusions (8) | today C19 · before window C19 · pattern transaction C19 · expected-matched C19 · `internal_transfer` C19 · `in_transit` C19 · `card_payment` C19 · excluded account C19 | - |
| de-duplication conditions (5) | amount within 10% C16 · over 10% C16 · over 7 days C16 · opposite sign C16 · other account C16 | - |
| card cases (5) | linked first item C17 · later items C17 · unlinked C18 · linked to excluded C18 · zero or null balance C18 | - |
| `incomplete` causes (5) | `login_required` C38 · `sync_failing` C38 · null `last_synced_at` C38 · over 48 h C38 · excluded-only connection ignored C38 | - |
| `days` bounds (5) | default C39 · 0 C39 · 1 C39 · 90 C39 · 91 C39 | - |
| recompute triggers (3) | `transactions.synced` C1, C27 · `forecast_inputs.changed` from expected payments C28 · from inclusion C34 | - |
| check constraints (4) | fingerprint unique C32 · week number C32 · item source C32 · item amount non-zero C32 | - |
| startup config: forecast handlers subscribed (2 assemblies) | API lifespan C26 + existing `tests/test_run_due.py::test_subscriptions_reach_job_events` · jobs `run_due.main` C26 + the same test. Both register the one `SUBSCRIPTIONS` list (AD-055) | - |
| doors (6) | 1 C28, C31, C32 · 2 C8, C9, C10 · 3 C26, C30 · 4 C36, C38, C43 · 5 C34 · 6 C11 | - |
| relations (3 entities) | snapshot C1, C32 · week C1, C32 · item C4, C32 | - |
| "Done when" (3) | 1 C5, C6 · 2 C27 · 3 C41 | - |

- Claims naming a status code or response shape are C36-C40 and C42. Each proof calls the route through `TestClient` with a signed token.
- C5 and C12-C25 prove the strategies at their own layer, on hand-built inputs. C6, C23 and C40 are the only proofs that run the whole path from a sync to the API.
- C41 is one timed run on the machine that runs it. It does not claim a percentile.

## Swept

- validation: C39 (`days`), C42 (non-UUID), C9 (setting), C32 (database constraints)
- failure modes: C8 (strategy failure falls back), C30 (both fail: rollback, earlier latest kept, nothing published)
- idempotency: C27 (same event twice), C28 (inputs revert to an earlier fingerprint), C31 (pattern ID churn doesn't change the fingerprint)
- authorization: C42, both routes. The handler takes the business only from the event
- concurrency: C29 (two recomputes under the advisory lock)
- data lifecycle: C32 (a snapshot cascades to its weeks and items); every snapshot is kept (plan, Out of scope), with no backfill (plan, Impact)
- dependency failure: n/a - no external service is called. The database failing is C30's rollback path; Plaid is reached only by the sync that publishes the event
- state transitions: C28 (the latest snapshot moves forward and back), C38 (`incomplete` flips with the clock)
- observability: C35 (`forecast.updated`, `forecast.unchanged`), C8 (`forecast.strategy_failed`), C30 (`event.handler_failed`)

## Handoff

- S1-S5 touch the forecasting module (api 7 KB, service 14 KB, models 4 KB, repository 4 KB, events 1 KB, detection 9 KB read), `bank_sync/service.py` 42 KB (2 small edits), `subscriptions.py` 1 KB, `settings.py` 3 KB, the fixtures read 27 KB, `tests/test_migrations.py` 33 KB, `tests/test_settings.py` 5 KB, `tests/conftest.py` 4 KB, `tests/test_bank_accounts.py` (edit) and the spec 20 tests as models 42 KB: about 268 KB with `contracts/openapi.json` 65 KB. New files are about 100 KB: strategies, the migration, 6 test files and `proofs.sh`. 368 KB / 4 = ~92k, under the 150k budget - one builder
