# 16 - Transaction labels checks

Profile: light
Plan: `.specs/features/16-bank-transaction-labels/plan.md`

28 checks in 4 slices · 5 one-way doors · 0 open

Commands run from `services/core/` (`uv run pytest ...`).

- **Plaid:** the tests use spec 14's `SyncFake` and spec 15's `NightlyFake`. No test calls Plaid.
- **Amounts** in claims are our sign: money in is positive, money out negative, in cents. The fake's Plaid amounts are the negation.
- **Accounts:** "savings", "checking", "card" and "credit line" are accounts of types `savings`, `checking`, `credit_card` and `line_of_credit`, all `CAD` and of the same business, unless the claim says otherwise.
- **Business days** are door 4's. In 2026, Mon 10-12 (Thanksgiving) is not a business day.
- **"Today"**: claims that depend on the business-local date (S3, C24) run through spec 15's `run_due(now)`, in a database of their own (`isolated_database`), for a business in `America/Toronto`. Every other claim uses dates for which today's date does not matter.
- **Pair:** "paired" means both rows have the claimed label and each one's `linked_transaction_id` is the other's `id`. "Unpaired" means `linked_transaction_id` is null.

## Checks

### S1 - A transfer between the business's own accounts is labelled on both sides · 6 files · 95 KB · ~24k

**C1** - One sync stores savings -1,000,000 dated Mon 2026-09-14 and checking +1,000,000 dated Wed 2026-09-16. Both are `internal_transfer` and paired (AC 1, spec "Done when" 1)
Proof: `uv run pytest tests/test_transaction_labels.py -k "savings_to_checking_paired"`

**C2** - Savings is on connection A and checking on connection B of the same business, with C1's amounts and dates. A is synced first: its outflow is `normal` and unpaired. After B's sync, both are `internal_transfer` and paired (AC 2)
Proof: `uv run pytest tests/test_transaction_labels.py -k "across_connections_paired"`

**C3** - Savings -300,000 dated Thu 2026-09-17 and checking +300,000 dated Tue 2026-09-15 (2 business days before the outflow) are `internal_transfer` and paired (AC 3)
Proof: `uv run pytest tests/test_transaction_labels.py -k "money_in_first_paired"`

**C4** - Window edges, table-driven over 4 cases, savings -200,000 and checking +200,000:
- out Fri 2026-10-09, in Thu 2026-10-15: paired (Thanksgiving skipped)
- out Fri 2026-10-09, in Fri 2026-10-16: both `normal`, unpaired
- out Fri 2026-09-18, in Wed 2026-09-23: paired (weekend skipped)
- out Fri 2026-09-18, in Thu 2026-09-24: both `normal`, unpaired

(AC 4)
Proof: `uv run pytest tests/test_transaction_labels.py -k "window_edges"`

**C5** - Table-driven over 4 near-misses to C1's savings -1,000,000 dated 2026-09-14. In each case both rows are `normal` and unpaired:
- checking +999,999
- checking +1,000,000 in `USD`
- +1,000,000 on the same savings account
- checking +1,000,000 of another business

(AC 5)
Proof: `uv run pytest tests/test_transaction_labels.py -k "near_misses_not_paired"`

**C6** - Pairing order, table-driven over 3 cases, with savings -500,000 dated Wed 2026-09-16:
- checking +500,000 on Thu 2026-09-17 and a second checking account +500,000 on Mon 2026-09-21: the outflow pairs with 09-17, and 09-21 is `normal`
- checking +500,000 on Tue 2026-09-15 and a second checking account +500,000 on Thu 2026-09-17 (both 1 business day away): it pairs with 09-15
- two checking accounts each +500,000 on Thu 2026-09-17: it pairs with the one whose `id` is lower, and the other is `normal`

In every case exactly 2 rows have a link (AC 6)
Proof: `uv run pytest tests/test_transaction_labels.py -k "pairing_order"`

### S2 - Card and credit line activity is labelled for what it is · 2 files · 35 KB · ~9k

**C7** - Card -8,500 dated 2026-09-14, unpaired, is `card_purchase` (AC 7, spec "Done when" 2)
Proof: `uv run pytest tests/test_transaction_labels.py -k "card_purchase_labelled"`

**C8** - Checking -245,000 dated Thu 2026-10-08 and card +245,000 dated Fri 2026-10-09 are `card_payment` and paired (AC 8, spec "Done when" 2)
Proof: `uv run pytest tests/test_transaction_labels.py -k "card_payment_paired"`

**C9** - Card +12,000, unpaired, table-driven over its Plaid primary category: `LOAN_PAYMENTS` -> `card_payment`, `TRANSFER_IN` -> `card_payment`, none -> `card_payment`, `GENERAL_MERCHANDISE` -> `card_purchase` (AC 9)
Proof: `uv run pytest tests/test_transaction_labels.py -k "card_credit_by_category"`

**C10** - Checking -60,000 with Plaid detailed category `LOAN_PAYMENTS_CREDIT_CARD_PAYMENT`, with no card account in the business, is `card_payment` and unpaired (AC 10)
Proof: `uv run pytest tests/test_transaction_labels.py -k "card_payment_unconnected_card"`

**C11** - Credit line -1,500,000 dated 2026-09-14 and checking +1,500,000 dated 2026-09-15 are `credit_draw` and paired. In a second business, an unpaired credit line -40,000 is `credit_draw` (AC 11)
Proof: `uv run pytest tests/test_transaction_labels.py -k "credit_draw"`

**C12** - Checking -700,000 dated 2026-09-14 and credit line +700,000 dated 2026-09-15 are `credit_repayment` and paired. In a second business, an unpaired credit line +40,000 is `credit_repayment` (AC 12)
Proof: `uv run pytest tests/test_transaction_labels.py -k "credit_repayment"`

**C13** - Credit line -90,000 dated 2026-09-14 and card +90,000 dated 2026-09-15 are `card_payment` and paired (AC 13)
Proof: `uv run pytest tests/test_transaction_labels.py -k "card_beats_credit_line"`

### S3 - A transfer whose other half hasn't arrived is in transit, then normal · 3 files · 60 KB · ~15k

**C14** - A checking -400,000 dated Fri 2026-10-09, unpaired, table-driven over its Plaid detailed category, nightly sync at `2026-10-15T06:00Z` (Thu 02:00 local):
- `TRANSFER_OUT_ACCOUNT_TRANSFER` -> `in_transit`
- `TRANSFER_OUT_SAVINGS` -> `in_transit`
- `TRANSFER_OUT_WITHDRAWAL` -> `normal`
- `TRANSFER_OUT_INVESTMENT_AND_RETIREMENT_FUNDS` -> `normal`

(AC 14)
Proof: `uv run pytest tests/test_transaction_labels_nightly.py -k "in_transit_by_category"`

**C15** - The `TRANSFER_OUT_ACCOUNT_TRANSFER` row of C14 is `in_transit` after the nightly sync at `2026-10-15T06:00Z`, and `normal` (unpaired) after the nightly sync at `2026-10-16T06:00Z` (Fri 02:00 local), with no new Plaid data in between (AC 15, spec "Done when" 3)
Proof: `uv run pytest tests/test_transaction_labels_nightly.py -k "in_transit_expires"`

**C16** - C15's outflow is `in_transit` after the sync at `2026-10-13T06:00Z`. The next nightly sync, at `2026-10-14T06:00Z`, adds savings +400,000 dated Wed 2026-10-14. Both are then `internal_transfer` and paired (AC 16)
Proof: `uv run pytest tests/test_transaction_labels_nightly.py -k "in_transit_then_paired"`

**C17** - Table-driven over unpaired checking transactions, each dated 2026-09-14: +50,000 with no category, +50,000 `INCOME`, +50,000 `TRANSFER_IN_ACCOUNT_TRANSFER`, -50,000 with no category, -50,000 `GENERAL_MERCHANDISE`. Every one is `normal` (AC 17)
Proof: `uv run pytest tests/test_transaction_labels.py -k "everything_else_normal"`

### S4 - Labels stay current and consistent through every sync · 7 files · 120 KB · ~30k

**C18** - After one sync of a business that holds all 7 labels (C1, C7, C8, C11, C12, C14's `in_transit` and C17's rows combined):
- every row's label is one of the 7
- only `internal_transfer`, `card_payment`, `credit_draw` and `credit_repayment` rows have a link
- for every row A linked to B, B is linked to A

(AC 18)
Proof: `uv run pytest tests/test_transaction_labels_nightly.py -k "all_labels_consistent"`

**C19** - The database refuses, each with `IntegrityError` naming the constraint:
- a label `transfer` (`ck_bank_transactions_label`)
- a link on a `normal` row (`ck_bank_transactions_linked_label`)
- a row linked to itself (`ck_bank_transactions_linked_not_self`)
- a second row linked to an already linked row (`uq_bank_transactions_linked_transaction_id`)

(AC 18, doors 1, 2)
Proof: `uv run pytest tests/test_transaction_labels.py -k "constraints_refuse"`

**C20** - Each sync path relabels the business, table-driven over 3: `sync_in_background` (the webhook path), `POST /v1/businesses/{id}/bank/connections` (the connect path), and `run_due` (the nightly path). In each, a stored checking +1,000,000 that is `normal` becomes `internal_transfer` once the sync stores the matching savings outflow (AC 19)
Proof: `uv run pytest tests/test_transaction_labels.py -k "every_sync_path_relabels"`
Proof: `uv run pytest tests/test_transaction_labels_nightly.py -k "nightly_path_relabels"`

**C21** - In C2's second sync, the relabelled connection-A outflow and the inserted connection-B inflow have the same Postgres `xmin` (one transaction) (AC 19)
Proof: `uv run pytest tests/test_transaction_labels.py -k "relabel_same_transaction"`

**C22** - C1's pair is stored. A sync whose first page removes the savings half, and whose second page carries a transaction for an unknown account, raises. Afterwards, both halves still exist, are `internal_transfer` and are paired (AC 20)
Proof: `uv run pytest tests/test_transaction_labels.py -k "failed_sync_keeps_labels"`

**C23** - C1's pair is stored:
- a sync that removes the savings half leaves checking +1,000,000 `normal` and unpaired
- in a fresh business, a pending savings -1,000,000 paired with checking +1,000,000 is replaced by its posted version (`pending_transaction_id`); the checking row is then paired with the posted row

(AC 21)
Proof: `uv run pytest tests/test_transaction_labels.py -k "removed_half_relabels"`

**C24** - After C1's sync, a second nightly sync on the same business-local date with no new Plaid data leaves every label and link unchanged, reports `relabeled` 0, and publishes no `transactions.synced` (AC 22)
Proof: `uv run pytest tests/test_transaction_labels_nightly.py -k "same_day_resync_unchanged"`

**C25** - Two threads sync connection A (savings -1,000,000, 2026-09-14) and connection B (checking +1,000,000, 2026-09-15) of one business at once. The fake holds A's Plaid call until B's has started. Both calls return without an exception, and afterwards the two rows are `internal_transfer` and paired (AC 23, door 3)
Proof: `uv run pytest tests/test_transaction_labels.py -k "concurrent_syncs_pair"`

**C26** - Event payload:
- C1's sync publishes `transactions.synced` with `relabeled` 2
- C15's sync at `2026-10-16T06:00Z` publishes `transactions.synced` with `added` 0, `modified` 0, `removed` 0, `balances_changed` false, and `relabeled` 1

(AC 24, door 5)
Proof: `uv run pytest tests/test_transaction_labels.py -k "event_counts_relabeled"`
Proof: `uv run pytest tests/test_transaction_labels_nightly.py -k "relabel_only_publishes"`

**C27** - C1's sync logs `bank_sync.synced` with `relabeled` 2. No log line from the sync contains the description, the counterparty, or the amount string `10000` of either transaction (AC 25)
Proof: `uv run pytest tests/test_transaction_labels.py -k "log_relabeled_no_details"`

**C28** - Migration:
- at the previous revision, a stored transaction upgraded to head has label `normal` and a null link
- downgrade to the previous revision removes both columns
- `holidays` is a runtime dependency in `pyproject.toml` and `uv.lock`

(AC 26, doors 1, 2, 4)
Proof: `uv run pytest tests/test_migrations.py -k "transaction_labels"`
Proof: `uv run pytest tests/test_transaction_labels.py -k "holidays_dependency"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| one-way doors (5) | door 1 C19, C28 · door 2 C19, C18 · door 3 C25 · door 4 C4, C28 · door 5 C26 | - |
| entities (1) | `bank_transactions` label and link C19, C28 | - |
| labels (7) | `internal_transfer` C1 · `in_transit` C14 · `card_purchase` C7 · `card_payment` C8, C10, C13 · `credit_draw` C11 · `credit_repayment` C12 · `normal` C17 | - |
| pair kinds by account types (4) | cash<->cash C1 · cash->card C8 · credit line->cash C11 · cash->credit line C12 (card beats credit line C13) | - |
| unpaired rules by account side (5) | card negative C7 · card positive C9 · cash negative with card-payment category C10 · credit line negative C11 · credit line positive C12 | - |
| pairing conditions (5) | amount C5 · currency C5 · different account C5 · same business C5 · window C4 | - |
| window directions (2) | money in after C1, C4 · money in before C3 | - |
| non-business days (2 kinds) | weekend C4 · federal holiday (Thanksgiving) C4 | - |
| tie-break keys (3) | fewest business days C6 · earliest date C6 · lowest `id` C6 | - |
| card positive categories (4) | `LOAN_PAYMENTS` C9 · `TRANSFER_IN` C9 · none C9 · other C9 | - |
| in-transit categories (4) | `TRANSFER_OUT_ACCOUNT_TRANSFER` C14 · `TRANSFER_OUT_SAVINGS` C14 · `TRANSFER_OUT_WITHDRAWAL` C14 · `..._INVESTMENT_AND_RETIREMENT_FUNDS` C14 | - |
| `in_transit` transitions (2) | -> `normal` C15 · -> `internal_transfer` C16 | - |
| sync paths (3) | webhook C20 · connect C20 · nightly C20 | - |
| changes that relabel (4) | added C1, C2 · removed C23 · pending replaced C23 · date passing C15 | - |
| constraints (4) | label C19 · linked label C19 · not self C19 · unique link C19 | - |
| event payload keys (6) | `connection_id` C26 · `added` C26 · `modified` C26 · `removed` C26 · `balances_changed` C26 · `relabeled` C26 (one exact-dict assertion) | - |

- No route changes, so no status rows. C20's connect path crosses the HTTP boundary only to start the sync spec 12 already starts.
- Every claim is asserted at the service layer through a real sync against Postgres. C19 and C21 read Postgres directly, because constraints and `xmin` can only be seen there.
- Spec 14's `test_event_published` asserts the exact payload, so it gains `relabeled` (door 5). No other existing assertion changes.

## Swept

- validation: C5 (amount, currency, account, business), C19 (the database refuses a bad label or link)
- failure modes: C22 (a failed sync keeps every label and link)
- idempotency: C24 (same data and date twice: no change, no event)
- authorization: C5 (no pairing across businesses); no route, so there is no caller to authorize; every sync is already scoped by `business_id` (spec 14)
- concurrency: C25 (two banks of one business syncing at once, door 3)
- data lifecycle: C28 (existing rows default to `normal`, relabelled by the next sync), C23 (a removed half clears its partner)
- dependency failure: n/a - labelling calls nothing outside Postgres; the `holidays` calendar is a local package with no network access; Plaid failure is C22
- state transitions: C15, C16 (`in_transit` -> `normal` or `internal_transfer`), C2 (`normal` -> paired)
- observability: C27 (`relabeled` on `bank_sync.synced`, no transaction details), C26 (event count)

## Handoff

- Existing files touched: `bank_sync/{service,models,repository}.py` (42 KB), `tests/test_transaction_sync.py` (30 KB, for `SyncFake` and the payload assertion), `tests/test_nightly_sync.py` (21 KB, for `NightlyFake` and its helpers), `tests/test_migrations.py` (25 KB), `tests/conftest.py` (4 KB), `accounts/service.py` (5 KB, read only), `pyproject.toml` (1 KB): ~128 KB
- New files: the migration, `tests/test_transaction_labels.py`, `tests/test_transaction_labels_nightly.py`: ~60 KB
- Total: 188 KB / 4 = ~47k tokens, under the 150k budget - one builder

- **Boundary:** C1-C28 closed at `bbc18f1`. Proofs green there: every named proof, the API suite (419 passed), ruff, mypy, spec 14 `proofs.sh c39` (real sandbox sync) and `c46` (generated files unchanged)
- **Settled mid-build (builder decisions, none asked):**
  - Labelling lives in `bank_sync/labels.py` as pure functions; `service._relabel` loads, compares and writes only changed rows, clearing old links before setting new ones because the link is unique.
  - `sync_connection` gained an optional `now` (default the current UTC time); the nightly path passes its `now`, so "today" is business-local at the run's clock.
  - The accounts lock is taken after the Plaid pages are fetched and before the first write, so a long Plaid call does not hold the business lock (C25's proof depends on this).
  - Three test-setup fixes before the first green run, no assertion changed: reused transaction names across two businesses in one test (Plaid IDs are globally unique), and `move`'s first parameter renamed from `name` to `key` (it clashed with `tx`'s description keyword).
  - Running `pytest -m "not sandbox"` overrides the project's `-m 'not plaid_sandbox'` default and runs the keyless sandbox tests; plain `uv run pytest` is the suite.
- **Abandoned:** none
