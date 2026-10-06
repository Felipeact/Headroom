# 19 - Recurring payments checks

Profile: light
Plan: `.specs/features/19-forecast-recurring-payments/plan.md`

33 checks in 4 slices · 3 one-way doors · 0 open

- **Commands** run from `services/core/` (`uv run pytest ...`). Commands that are not one test live in `.specs/features/19-forecast-recurring-payments/proofs.sh` (`bash proofs.sh c<n>`).
- **Detection tests** (S1) call the pure detector with synthetic transactions only, each a value carrying `id`, `account_id`, `date`, `amount_cents` (our sign), `currency` `CAD`, `pending`, `description`, `counterparty` and `label`, with `normal` and not pending unless the check says otherwise. "A series" is the same account, counterparty and amount on the dates named. The as-of day is the newest input date (plan's Criteria preamble). Where a check moves it, it adds one unrelated one-off transaction on that date.
- **"The sample"** is Harbor Street Plumbing loaded with `app.fixtures.load.main(["harbor_street", "--seed", N, "--clerk-user-id", X])` against the pytest session database. "Its patterns" are what `GET .../recurring-patterns` returns to that owner.
- **Refresh tests** (S3) write transactions through `bank_sync.service.sync_connection` with spec 14's `SyncFake`, after `subscriptions.register()`, so the handler runs as it does in the app.

## Checks

### S1 - The detector finds payments that repeat on a schedule · 3 files · 30 KB · ~8k

**C1** - Table-driven over 7 cases: a monthly series of 6 on the 15th, labelled `card_purchase`, `card_payment`, `internal_transfer`, `in_transit`, `credit_draw` or `credit_repayment`, or labelled `normal` but `pending`, gives no pattern. The same series labelled `normal`, not pending, gives exactly 1 (AC 1)
Proof: `uv run pytest tests/test_recurring_detection.py -k "only_normal_posted"`

**C2** - Grouping, table-driven over 5 cases, all on the 15th with equal absolute amounts:
- "Wharfside Properties" in the odd months and "  WHARFSIDE properties " in the even months of 2025-10 to 2026-09 -> exactly 1 pattern, with 12 transaction IDs
- one monthly series of 6 on each of two accounts, same counterparty and dates -> 2 patterns
- the same counterparty and dates with -50000 and with +50000 -> 2 patterns
- the same counterparty and dates in `CAD` and in `USD` -> 2 patterns
- counterparty null, descriptions "Invoice 1001" to "Invoice 1006" over 6 months -> 1 pattern whose `counterparty` is "Invoice 1006"

(AC 2)
Proof: `uv run pytest tests/test_recurring_detection.py -k "grouping_key"`

**C3** - Amount bands: a monthly series of 6 on the 15th with amounts -100000 (months 1 to 3) and -115000 (months 4 to 6) gives exactly 1 pattern with 6 transaction IDs. The same with -115001 for months 4 to 6 gives exactly 1 pattern, amount -115001 and 3 transaction IDs (the -100000 band stopped, AC 10) (AC 3)
Proof: `uv run pytest tests/test_recurring_detection.py -k "amount_bands"`

**C4** - Schedules, table-driven over 5 series. Each gives exactly 1 pattern with this `schedule` and every transaction in `transaction_ids`:
- 8 Tuesdays 7 days apart from 2026-06-02 -> `weekly`
- 8 Fridays 14 days apart from 2026-04-03 -> `biweekly`
- the 1st and the 15th of 2026-03 to 2026-08 -> `semimonthly`
- the 15th of 2026-01 to 2026-08 -> `monthly`
- the 10th of 2025-01, 2025-04, 2025-07, 2025-10 and 2026-01 -> `quarterly`

(AC 4, AC 5)
Proof: `uv run pytest tests/test_recurring_detection.py -k "each_schedule"`

**C5** - Tolerances, table-driven over the 5 C4 series with their 5th date moved later. When moved by exactly the tolerance (`weekly` 1, `biweekly` 3, `semimonthly` 3, `monthly` 4, `quarterly` 7 days), it stays a hit: same schedule, all transactions in `transaction_ids`. When moved by 1 day more, that transaction is not in `transaction_ids` (AC 4)
Proof: `uv run pytest tests/test_recurring_detection.py -k "tolerance_edges"`

**C6** - Share threshold: the 15th in 9 of the 12 months 2025-10 to 2026-09 (first and last months present) gives 1 `monthly` pattern with confidence 75. The 15th in 8 of those 12 months gives no pattern (AC 4)
Proof: `uv run pytest tests/test_recurring_detection.py -k "share_threshold"`

**C7** - A payment seen twice: a monthly series of 2 gives no pattern. A monthly series of 3 gives 1 `monthly` pattern with confidence 50 (AC 6, spec 19 "Done when" 2)
Proof: `uv run pytest tests/test_recurring_detection.py -k "three_needed"`

**C8** - Next date, table-driven over 3 series:
- the biweekly C4 series with its last date moved 1 day earlier (Thursday) -> next date is the Friday 14 days after the cadence's last Friday
- the 31st of 2025-08, 2025-10, 2025-12 and 2026-01, and the 30th of 2025-09 and 2025-11 (median day 31) -> next date 2026-03-02 (Feb 28, 2026 is a Saturday, clamped then moved forward)
- the 15th of 2026-03 to 2026-07 -> next date 2026-08-17 (Aug 15, 2026 is a Saturday)

(AC 7)
Proof: `uv run pytest tests/test_recurring_detection.py -k "next_date"`

**C9** - Amount: a monthly series of 8 with amounts, oldest first, -90000, -90000, -100000, -100001, -100002, -100003, -100004, -100005 gives amount -100002 (median of the last 6, -100002.5, rounded half to even). A series of 3 with -100000, -100003, -100001 gives -100001 (AC 8)
Proof: `uv run pytest tests/test_recurring_detection.py -k "median_amount"`

**C10** - Confidence, table-driven over 4 monthly series with every date hit: 3 hits -> 50, 4 -> 67, 6 -> 100, 12 -> 100. C6's 9-of-12 series -> 75 (AC 9)
Proof: `uv run pytest tests/test_recurring_detection.py -k "confidence"`
Proof: `uv run pytest tests/test_recurring_detection.py -k "share_threshold"`

**C11** - Stopped payments, table-driven over the 5 C4 series: with the as-of day moved to the pattern's next date plus half its interval (`weekly` 3, `biweekly` 7, `semimonthly` 7, `monthly` 15, `quarterly` 45 days), the pattern is reported. With the as-of day 1 day later, it is not (AC 10)
Proof: `uv run pytest tests/test_recurring_detection.py -k "stopped"`

**C12** - Pattern fields: a monthly series of 6 whose counterparties are "WHARFSIDE PROPERTIES" for months 1 to 5 and "Wharfside Properties" for month 6, with descriptions "Rent 1" to "Rent 6", gives `counterparty` "Wharfside Properties", `description` "Rent 6", the series' account, `currency` `CAD`, and `transaction_ids` equal to the 6 IDs in date order. A seventh transaction in month 3 that is not a hit (on the 1st) is in no pattern's `transaction_ids` (AC 11)
Proof: `uv run pytest tests/test_recurring_detection.py -k "pattern_fields"`

**C13** - Order: the C4 and C12 inputs together, shuffled with `random.Random(n)` for n in 0..4, give patterns equal to those of the unshuffled input (AC 12)
Proof: `uv run pytest tests/test_recurring_detection.py -k "input_order"`

### S2 - On the sample data, payroll, rent and software are found, and nothing else · 4 files · 60 KB · ~15k

**C14** - Seed 0's patterns include one with `counterparty` "Payroll", the Operating checking account ID, `schedule` `biweekly`, `amount_cents` -1120000, `currency` `CAD`, `next_date` "2026-10-02" (AC 13, spec 19 "Done when" 1)
Proof: `uv run pytest tests/test_recurring_sample.py -k "payroll"`

**C15** - Seed 0's patterns include one with `counterparty` "Wharfside Properties", `description` "Rent", Operating checking, `monthly`, -380000, `next_date` "2026-10-15" (AC 14, spec 19 "Done when" 1)
Proof: `uv run pytest tests/test_recurring_sample.py -k "rent"`

**C16** - Seed 0's patterns include one with `counterparty` "Fieldworks Software", `description` "Software subscriptions", Operating checking, `monthly`, -64000, `next_date` "2026-10-07" (AC 15)
Proof: `uv run pytest tests/test_recurring_sample.py -k "software"`

**C17** - For each seed 0 to 9, the sample has exactly 3 patterns, and their `counterparty` values are exactly "Payroll", "Wharfside Properties" and "Fieldworks Software" (AC 16)
Proof: `uv run pytest tests/test_recurring_sample.py -k "exactly_three"`

**C18** - For seed 0, no `transaction_ids` entry of any pattern is a transaction of Reserve savings or a transaction labelled `internal_transfer` (checked against `GET .../bank/transactions`), and the sample does hold `internal_transfer` transactions on both Operating checking and Reserve savings (AC 17, spec 19 "Done when" 3)
Proof: `uv run pytest tests/test_recurring_sample.py -k "no_transfers"`

### S3 - Every committed sync refreshes the stored patterns · 8 files · 110 KB · ~28k

**C19** - A business holds a stored pattern written directly by `forecasting.repository` for a counterparty that has no transactions. A sync that adds a monthly series of 6 publishes `transactions.synced`. Afterwards the business's rows are exactly the 1 pattern the detector returns for its stored transactions, and the planted row is gone. A second business's planted row is unchanged (AC 18)
Proof: `uv run pytest tests/test_recurring_refresh.py -k "sync_replaces_patterns"`

**C20** - Calling `refresh_recurring_patterns` twice with the same `Event` leaves the same rows as after the first call: the same count, and equal (`account_id`, `counterparty`, `description`, `schedule`, `amount_cents`, `currency`, `next_date`, `confidence`, `transaction_ids`) (AC 19)
Proof: `uv run pytest tests/test_recurring_refresh.py -k "same_event_twice"`

**C21** - With the detector patched to sleep 0.5 s, two threads calling `refresh_recurring_patterns` for the same business at the same time both return. The business then holds exactly as many rows as the detector returns, with no two rows sharing (`account_id`, `counterparty`, `schedule`) (AC 20)
Proof: `uv run pytest tests/test_recurring_refresh.py -k "concurrent_refreshes"`

**C22** - A business with 1 stored pattern syncs a page that removes all its transactions. Afterwards it holds 0 patterns (AC 21)
Proof: `uv run pytest tests/test_recurring_refresh.py -k "no_transactions_no_patterns"`

**C23** - With the detector patched to raise `RuntimeError`, a sync that adds transactions still commits them. The business keeps exactly its earlier pattern rows (same IDs), and one `event.handler_failed` log line names the handler `refresh_recurring_patterns` and `error_type` `RuntimeError` (AC 22)
Proof: `uv run pytest tests/test_recurring_refresh.py -k "failure_keeps_patterns"`

**C24** - A refresh that stores 1 pattern writes exactly one `recurring_patterns.refreshed` JSON log line, with `business_id` and `patterns` 1. No log line of the refresh contains the series' counterparty, description or amount (AC 23)
Proof: `uv run pytest tests/test_recurring_refresh.py -k "refresh_logged"`

**C25** - `app.subscriptions.SUBSCRIPTIONS[0]` is `("transactions.synced", forecasting.service.refresh_recurring_patterns)` (door 2)
Proof: `uv run pytest tests/test_recurring_refresh.py -k "subscribed_first"`

**C26** - The table refuses bad rows, table-driven over 3 inserts that each raise `IntegrityError` naming the constraint: `schedule` "yearly" -> `ck_recurring_patterns_schedule`, `confidence` 101 -> `ck_recurring_patterns_confidence`, `amount_cents` 0 -> `ck_recurring_patterns_amount_nonzero`. A row with `confidence` 0 and one with 100 are accepted (door 1)
Proof: `uv run pytest tests/test_recurring_refresh.py -k "constraints_refuse"`

**C27** - The `recurring_patterns` migration upgrades from spec 17's head, creates the table with `transaction_ids` as `ARRAY` (`uuid[]`) and `confidence` as `smallint`, downgrades to spec 17's head leaving no `recurring_patterns` table, upgrades again, and `alembic check` then finds no difference between the models and the database (door 1)
Proof: `uv run pytest tests/test_migrations.py -k "recurring_patterns_upgrade_downgrade_and_check"`

### S4 - The owner reads the patterns through the API · 4 files · 60 KB · ~15k

**C28** - For a business with a weekly, a monthly and a second monthly pattern whose next dates are 2026-10-07, 2026-10-02 and 2026-10-02 (counterparties "Zed" and "Acme"), `GET .../recurring-patterns` as the owner answers `200` with keys exactly `items`. The items are ordered "Acme" (10-02), "Zed" (10-02), then the 10-07 one. Each item's keys are exactly `id`, `account_id`, `counterparty`, `description`, `schedule`, `amount_cents`, `currency`, `next_date`, `confidence`, `transaction_ids`, with `next_date` an ISO date and `confidence` an int (AC 24, door 3)
Proof: `uv run pytest tests/test_recurring_patterns_api.py -k "order_and_shape"`

**C29** - A business with no patterns answers `200` `{"items": []}` (AC 25)
Proof: `uv run pytest tests/test_recurring_patterns_api.py -k "empty_business"`

**C30** - A caller who isn't a member gets `404` "Business not found.". With `accounts.service.get_membership` patched to role `viewer`, the owner gets `403` "You don't have permission to do this.". The owner of business A, with patterns stored in A and in B, sees only A's pattern IDs (AC 26)
Proof: `uv run pytest tests/test_recurring_patterns_api.py -k "access_denied"`

**C31** - `GET /v1/businesses/not-a-uuid/recurring-patterns` as a signed-in user answers `422` `application/problem+json` (AC 27)
Proof: `uv run pytest tests/test_recurring_patterns_api.py -k "invalid_business_id"`

**C32** - Regenerating `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` leaves no diff, and the contract has `get` on `/v1/businesses/{business_id}/recurring-patterns` (door 3)
Proof: `bash .specs/features/19-forecast-recurring-payments/proofs.sh c32`

**C33** - Every AGENTS.md check passes: API `ruff format --check`, `ruff check`, `mypy app`, `pytest`; web `lint`, `typecheck`, `test`, `build` (the web consumes the regenerated `schema.d.ts`)
Proof: `bash .specs/features/19-forecast-recurring-payments/proofs.sh c33`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET .../recurring-patterns` statuses (4) | 200 C28, C29 · 403 C30 · 404 C30 · 422 C31 | - |
| schedules (5) | `weekly` C4, C5, C11 · `biweekly` C4, C5, C8, C11 · `semimonthly` C4, C5, C11 · `monthly` C4, C5, C8, C11 · `quarterly` C4, C5, C11 | - |
| excluded inputs (7) | `card_purchase` C1 · `card_payment` C1 · `internal_transfer` C1 · `in_transit` C1 · `credit_draw` C1 · `credit_repayment` C1 · pending C1 | - |
| grouping key parts (5) | account C2 · currency C2 · direction C2 · counterparty normalised C2 · description fallback C2 | - |
| next-date rules (3) | cadence kept after a holiday shift C8 · month-end clamp C8 · weekend moved forward C8 | - |
| confidence values (5) | 3 hits C7, C10 · 4 hits C10 · 6 hits C10 · 12 hits C10 · 9 of 12 C6, C10 | - |
| sample patterns (3) | Payroll C14, C17 · Rent C15, C17 · Software C16, C17 | - |
| sample non-patterns (5) | Coastal Supply Co C17 · client payments C17 · card purchases C17 · card payments C17 · transfers C17, C18 | - |
| refresh outcomes (4) | replaced C19 · repeated C20 · emptied C22 · failed and kept C23 | - |
| check constraints (3) | schedule C26 · confidence C26 · amount non-zero C26 | - |
| startup config: handler subscribed (2 assemblies) | API lifespan C25 + existing `tests/test_run_due.py::test_subscriptions_reach_job_events` · jobs `run_due.main` C25 + the same existing test. Both register the one `SUBSCRIPTIONS` list (AD-055) | - |
| doors (3) | 1 C26, C27, C19 · 2 C19, C21, C25 · 3 C28, C32 | - |
| "Done when" (3) | 1 C14, C15 · 2 C7 · 3 C18 | - |

- Claims naming a status code or response shape: C14-C18, C28-C31. Each proof calls the route through `TestClient` with a signed token.
- AC 5's tie-break (larger share, then shorter interval) is proven only through C4: each series reports its own schedule and no other. No input in C4 makes two schedules fit with equal share.
- C17 samples seeds 0 to 9 only. No other seed is claimed to give exactly 3 patterns.

## Swept

- validation: C31 (`business_id`), C26 (stored values refused by the database)
- failure modes: C23 (a failed refresh rolls back and keeps the earlier set; the sync stays committed)
- idempotency: C20 (same event twice), C13 (same input in any order)
- authorization: C30. The handler takes the business only from the event the publisher built after its own commit
- concurrency: C21 (two refreshes of one business under the advisory lock)
- data lifecycle: C22 (patterns removed when their transactions are), C19 (stale rows replaced); no backfill (plan Out of scope)
- dependency failure: n/a - the refresh calls no external service. The database failing is C23's rollback path
- state transitions: n/a - a pattern has no states; a whole set replaces the previous one (C19)
- observability: C24 (`recurring_patterns.refreshed`, nothing sensitive), C23 (`event.handler_failed`)

## Handoff

- Estimate, from `wc -c` of the files each slice reads or writes, divided by 4: S1 = 8k (new detector, new test, `labels.py` for `is_business_day`); S2 = 15k (`fixtures/load.py`, `harbor_street.py`, new test, the transactions test helpers); S3 = 28k (`bank_sync/service.py` 45 KB, `repository.py`, `subscriptions.py`, `app/events.py`, new `forecasting` module, migration, new test, `test_transaction_sync.py` helpers); S4 = 15k (`bank_sync/api.py` as the route model, `main.py`, new test, generated files). Running total 66k, under the 150k budget - one builder.
- Mechanism: one builder (fits; no ask).
