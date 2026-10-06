# 18 - Sample data checks

Profile: light
Plan: `.specs/features/18-forecast-sample-data/plan.md`

37 checks in 4 slices · 3 one-way doors · 0 open

- **Commands** run from `services/core/` (`uv run pytest ...`). Commands that are not one test live in `.specs/features/18-forecast-sample-data/proofs.sh` (`bash proofs.sh c<n>`).
- **"The sample"** is `harbor_street.generate(0)` unless a check names another seed. Amounts are integer cents, our sign (money in positive).
- **"Week end"** is the reference future's opening plus every item dated up to that week's Sunday (plan AC 13).
- **Loader tests** call `app.fixtures.load.main(argv)` against the pytest session database (spec 03's `migrated_database`), each with its own `--clerk-user-id` unless a check names the default. Owner calls use `tests/tokens.py` tokens for that Clerk ID, through `TestClient`.

## Checks

### S1 - The same seed always gives the same Harbor Street Plumbing · 2 files · 30 KB · ~8k

**C1** - `generate(0)` called twice returns equal `SampleBusiness` values, and `json.dumps(dataclasses.asdict(...), default=str, sort_keys=True)` of the two is byte-identical. The same holds for seed 7 (AC 1, "Done when" 1)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "same_seed_identical"`

**C2** - `generate(0)` and `generate(1)` differ in at least one client payment's `amount_cents`, and have equal `banks`, `expected_payments` and `future` (AC 2)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "seeds_differ_only_in_history"`

**C3** - The business is `name` "Harbor Street Plumbing", `province` "ON", `time_zone` "America/Toronto" (AC 3)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "business_identity"`

**C4** - The banks, table-driven over 4 accounts, every one `CAD`:
- Harbor Community Bank / Operating checking: `checking`, `2381`, balance 800000
- Harbor Community Bank / Reserve savings: `savings`, `9025`, balance 3430000
- Harbor Community Bank / Line of credit: `line_of_credit`, `7702`, balance 0, available 2000000
- Summit Federal / Business Visa: `credit_card`, `5530`, balance 245000

and no other bank or account (AC 4)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "banks_and_accounts"`

**C5** - Every history transaction has `date` in 2025-03-26..2026-09-26, the minimum date is on or before 2025-04-01, `amount_cents` is an `int` (not `bool`, not `float`) and non-zero, `currency` is "CAD", and every `key` is unique (AC 5)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "history_span_and_types"`

**C6** - The Operating checking transactions with counterparty "Payroll" are each -1120000, and their dates are exactly the 14-day Friday cadence ending 2026-09-18 that starts at or after 2025-03-26, with 2025-04-18 -> 2025-04-17, 2025-12-26 -> 2025-12-24 (2025-12-25 is also a holiday) and 2026-04-03 -> 2026-04-02 (AC 6)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "payroll_schedule"`

**C7** - For each of the 18 months 2025-04..2026-09, Operating checking has exactly one "Rent" and exactly one "Software subscriptions" payment, all rent payments equal, all subscription payments equal, each on the same day-of-month rule (AC 7)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "monthly_rent_and_software"`

**C8** - For each of the 18 months, at least one negative "Coastal Supply Co" transaction exists and none equals -1450000; the positive transactions name at least 4 distinct counterparties, including "Acme Co" and "Birch & Co" (AC 8)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "suppliers_and_clients"`

**C9** - Business Visa has negative purchases; for each of the 18 months there is an Operating checking transaction with `category_detailed` `LOAN_PAYMENTS_CREDIT_CARD_PAYMENT` and a positive Business Visa transaction of the same absolute amount, at most 3 business days apart (AD-059) (AC 9)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "card_payments_pair"`

**C10** - For each of the 18 months there is at least one pair of an Operating checking and a Reserve savings transaction with opposite amounts on the same date, the outgoing half with `category_detailed` in `TRANSFER_OUT_ACCOUNT_TRANSFER` / `TRANSFER_OUT_SAVINGS` (AC 10)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "monthly_transfers"`

**C11** - For seeds 0..9, rebuilding each account's end-of-day balance backward from its reference balance: Operating checking and Reserve savings are `>= 0` and the Business Visa owed amount is `>= 0` on every day 2025-03-26..2026-09-26 (AC 11)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "balances_never_negative"`

### S2 - The sample holds the cash gap from the alert mockup · 2 files · 30 KB · ~8k

**C12** - `expected_payments` is exactly, in this order, each on Operating checking: ("Acme Co, invoice 1042", +800000, 2026-10-06, once), ("Coastal Supply Co, quarterly order", -1450000, 2026-11-12, every 3 months), ("Birch & Co, invoice 1057", +960000, 2026-11-17, once), ("Equipment lease deposit", -300000, 2026-12-07, once) (AC 12)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "future_expected_payments"`

**C13** - `future.opening_cents` is 4230000, which equals Operating plus Reserve balances; `future.weeks` has 13 entries whose `start` dates are the Mondays 2026-09-28 to 2026-12-21; each `end_cents` equals the opening plus every item dated up to `start + 6 days`; every item is dated 2026-09-27..2026-12-27 (AC 13)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "future_weeks_add_up"`

**C14** - The week starting 2026-11-09 ends at 315000; each of the other 12 weeks ends at `>= 1765000` (AC 14)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "future_gap_week_of_nov_9"`

**C15** - The future has Coastal Supply Co -1450000 on 2026-11-12, Payroll -1120000 on 2026-11-13, and Birch & Co +960000 on 2026-11-17 (AC 15)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "future_gap_causes"`

**C16** - The future items dated 2026-09-27..2026-10-09 are exactly 4: Payroll -1120000 on 2026-10-02, Acme Co +800000 on 2026-10-06, Software subscriptions -64000 on 2026-10-07, Business Visa payment -245000 on 2026-10-08 (AC 16)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "future_next_14_days"`

**C17** - Recomputing the week ends, table-driven over 3 edits: Birch & Co moved to 2026-11-10 -> lowest 1275000; Coastal Supply Co moved to 2026-11-19 -> lowest 1765000; +200000 added on 2026-11-09 and -200000 on 2026-11-17 -> lowest 515000 (AC 17)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "future_three_fixes"`

**C18** - The future's Payroll dates are 2026-10-02, 10-16, 10-30, 11-13, 11-27, 12-11 and 12-24, each -1120000; its Rent and Software subscriptions items have the history's amounts and day-of-month rule (AC 18)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "future_continues_history"`

### S3 - One command loads the sample into the local database · 6 files · 120 KB · ~30k

**C19** - On a database where the Clerk ID is unknown, `main(["harbor_street", "--clerk-user-id", X])` returns 0 and prints one UUID line; that business has name "Harbor Street Plumbing", `ON`, `America/Toronto`, and X's user is its owner. Run with no `--clerk-user-id`, the owner's Clerk ID is `user_sample_harbor_street` (AC 19)
Proof: `uv run pytest tests/test_fixture_load.py -k "load_creates_owned_business"`
Proof: `uv run pytest tests/test_fixture_load.py -k "default_owner"`

**C20** - After a load, `GET /v1/businesses/{b}/bank/connections` as the owner answers `200` with 2 connections, "Harbor Community Bank" (Line of credit, Operating checking, Reserve savings) and "Summit Federal" (Business Visa), names, types, masks, `balance_cents`, `available_cents` as C4; `included` true only for Operating checking and Reserve savings; `primary` true only for Operating checking; each `status` `synced` and `last_synced_at` `2026-09-26T10:02:00Z` (AC 20, "Done when" 2)
Proof: `uv run pytest tests/test_fixture_load.py -k "accounts_through_api"`

**C21** - After a load, following `next_cursor` from `GET .../bank/transactions?limit=500` until null returns as many items as `generate(0).history`, and the multiset of (`date`, `amount_cents`, `currency`, `description`) equals the history's (AC 21, "Done when" 2)
Proof: `uv run pytest tests/test_fixture_load.py -k "transactions_through_api"`

**C22** - After a load, every C10 transfer half has `label` `internal_transfer`, every C9 card payment half has `card_payment`, and no transaction has `in_transit` (AC 22)
Proof: `uv run pytest tests/test_fixture_load.py -k "labels_after_load"`

**C23** - With a handler subscribed to `transactions.synced`, a load delivers exactly 2 events, one per connection, each with the loaded `business_id` and `added` equal to that bank's history count (AC 23)
Proof: `uv run pytest tests/test_fixture_load.py -k "publishes_transactions_synced"`

**C24** - A second `main` with the same `--clerk-user-id` returns 0, prints a line containing "already loaded" and the business ID, and the row counts of `businesses`, `bank_connections`, `bank_accounts`, `bank_transactions` and `audit_log` are unchanged (AC 24)
Proof: `uv run pytest tests/test_fixture_load.py -k "second_load_is_noop"`

**C25** - Table-driven over 2 owners: one who owns a business created through `accounts.service.create_business` with no bank, and one whose sample load holds only 1 of the 2 connections. `main` returns 1, writes one stderr line containing that business's ID, and the same 5 row counts are unchanged (AC 25)
Proof: `uv run pytest tests/test_fixture_load.py -k "owner_with_other_business"`

**C26** - With `DATABASE_URL` host `db.example.com`, `main(["harbor_street"])` returns 1, writes "Refusing to load sample data into a non-local database." to stderr, and `create_engine` is never called. Hosts `localhost`, `127.0.0.1` and `::1` are accepted by the same check (AC 26)
Proof: `uv run pytest tests/test_fixture_load.py -k "refuses_non_local_database"`

**C27** - `main(["acme"])` raises `SystemExit` with code 2, and stderr contains `harbor_street` (AC 27)
Proof: `uv run pytest tests/test_fixture_load.py -k "unknown_fixture"`

**C28** - A load writes exactly one `fixture.loaded` JSON log line with `fixture` "harbor_street", `seed` 0, `business_id` and `transactions` equal to the history count; neither stdout nor stderr nor any log line contains `sample-not-a-token` (AC 28)
Proof: `uv run pytest tests/test_fixture_load.py -k "logs_fixture_loaded"`

**C29** - After a load, every `bank_connections.plaid_item_id`, `bank_accounts.plaid_account_id` and `bank_transactions.plaid_transaction_id` of the business starts with `sample-`, and `decrypt_access_token(access_token_ciphertext)` is `sample-not-a-token` while the ciphertext is not. `FixturePlaidClient.create_link_token`, `remove_item` and `get_webhook_verification_key` each raise `PlaidError` with `error_code` `NOT_SUPPORTED` (door 3)
Proof: `uv run pytest tests/test_fixture_load.py -k "fixture_plaid_identifiers"`

### S4 - The owner reads transactions through the API · 4 files · 70 KB · ~18k

**C30** - For a business with 5 synced transactions on 3 dates (two sharing a date), `GET .../bank/transactions` answers `200` with keys exactly `items`, `next_cursor`; items sorted by `date` descending then `id` descending; each item's keys are exactly `id`, `account_id`, `date`, `amount_cents`, `currency`, `pending`, `description`, `counterparty`, `label`, with `amount_cents` in our sign (AC 29, door 1)
Proof: `uv run pytest tests/test_bank_transactions_api.py -k "order_and_shape"`

**C31** - With 205 transactions, the default page has 100 items and a non-null `next_cursor`; following cursors yields pages of 100, 100, 5, the last with `next_cursor` null, and the 205 IDs are each returned exactly once. `limit=500` returns all 205 with `next_cursor` null (AC 29, AC 30)
Proof: `uv run pytest tests/test_bank_transactions_api.py -k "pages_visit_each_once"`

**C32** - A business with no transactions answers `200` `{"items": [], "next_cursor": null}` (AC 31)
Proof: `uv run pytest tests/test_bank_transactions_api.py -k "empty_business"`

**C33** - Table-driven over 5 requests, each `422` `application/problem+json`: `limit=0`, `limit=501`, `limit=abc`, `cursor=!!!` (not base64), and `cursor` = base64 of `not-a-date/xyz` (AC 32)
Proof: `uv run pytest tests/test_bank_transactions_api.py -k "invalid_params_422"`

**C34** - A caller who is not a member gets `404` "Business not found.". With `accounts.service.get_membership` patched to role `viewer`, the owner gets `403` "You don't have permission to do this.". The owner of business A, holding transactions in A and in B, sees only A's transaction IDs (AC 33)
Proof: `uv run pytest tests/test_bank_transactions_api.py -k "access_denied"`

**C35** - No response body of the route contains the stored `plaid_transaction_id`, `plaid_account_id` or `plaid_item_id` values, or those key names (AC 34)
Proof: `uv run pytest tests/test_bank_transactions_api.py -k "no_plaid_ids"`

**C36** - Regenerating `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` leaves no diff, and the contract has `get` on `/v1/businesses/{business_id}/bank/transactions` (door 1)
Proof: `bash .specs/features/18-forecast-sample-data/proofs.sh c36`

**C37** - Every AGENTS.md check passes: API `ruff format --check`, `ruff check`, `mypy app`, `pytest`; web `lint`, `typecheck`, `test`, `build` (the web consumes the regenerated `schema.d.ts`)
Proof: `bash .specs/features/18-forecast-sample-data/proofs.sh c37`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET .../bank/transactions` statuses (4) | 200 C30, C31, C32 · 403 C34 · 404 C34 · 422 C33 | - |
| loader exit codes (3) | 0 C19, C24 · 1 C25, C26 · 2 C27 | - |
| loader outcomes (5) | fresh load C19 · already loaded C24 · other business C25 · partial sample C25 · non-local DB C26 | - |
| local hosts accepted (3) | `localhost` C26 · `127.0.0.1` C26 · `::1` C26 | - |
| accounts (4) | Operating checking C4, C20 · Reserve savings C4, C20 · Line of credit C4, C20 · Business Visa C4, C20 | - |
| history flow kinds (7) | payroll C6 · rent C7 · software C7 · supplier bills C8 · client payments C8 · card payments C9 · transfers C10 | - |
| payroll holiday shifts (3) | 2025-04-17 C6 · 2025-12-24 C6 · 2026-04-02 C6 | - |
| expected payments (4) | Acme C12 · Coastal C12 · Birch C12 · Equipment lease C12 | - |
| alert fixes (3) | Birch early C17 · Coastal moved C17 · credit draw C17 | - |
| next-14-days items (4) | Payroll Oct 2 C16 · Acme Oct 6 C16 · Software Oct 7 C16 · Visa payment Oct 8 C16 | - |
| `422` causes (5) | C33, table-driven over all 5 | - |
| labels after load (3) | `internal_transfer` C22 · `card_payment` C22 · no `in_transit` C22 | - |
| `FixturePlaidClient` unsupported methods (3) | `create_link_token` C29 · `remove_item` C29 · `get_webhook_verification_key` C29 | - |
| doors (3) | 1 C30, C31, C33, C36 · 2 C1, C5, C13 · 3 C29, C26 | - |
| "Done when" (2) | 1 C1 · 2 C20, C21 | - |

- Claims naming a status code or response shape: C20, C21, C30-C35 - each proof calls the route through `TestClient` with a signed token.
- C11 samples seeds 0..9 only; any other seed is not claimed to stay non-negative.
- The reference future is proven as arithmetic over its own items (C13-C18). Whether spec 21's forecast reproduces it is spec 21's and 24's claim, not this one.

## Swept

- validation: C33 (`limit` and `cursor`), C27 (fixture name)
- failure modes: C25 (partial load reported, not called "loaded"), C26 (refused before connecting)
- idempotency: C24 (second load changes nothing), C1 (same seed same data)
- authorization: C34; the loader is a local command with no caller identity, gated by C26
- concurrency: n/a - the loader is run once by hand against a local database; two loads for one owner race on AD-030's owner index, and the loser fails in `create_business` (existing)
- data lifecycle: n/a - the sample is only created; removing it is a fresh local database (plan Out of scope)
- dependency failure: n/a - the only external dependency, Plaid, is replaced by `FixturePlaidClient` (C29); the database being down fails the command with exit 1 like any startup failure
- state transitions: C20 (connections end `synced`), C22 (labels computed by the real relabel)
- observability: C28 (`fixture.loaded`, no token in output)

## Handoff

- Estimate, from `wc -c` of the files each slice reads or writes, divided by 4: S1 = 8k (new generator, new test); S2 = 8k (same two files); S3 = 30k (loader, fake Plaid, `bank_sync.service`, `accounts.service`, `subscriptions.py`, new test); S4 = 18k (`bank_sync/api.py`, `repository.py`, new test, generated files). Running total 64k, under the 150k budget - one builder.
- Mechanism: one builder (fits; no ask).

- **Boundary:** C1-C37 closed at the sample-data commit after `10e89d5` (route at `10e89d5`). Proofs green there: `tests/test_fixture_harbor_street.py` (27), `tests/test_fixture_load.py` (13), `tests/test_bank_transactions_api.py` (10); `proofs.sh c36 c37` (API 517 passed; web 224 passed; lint, typecheck, build). The real command also ran against a throwaway local database: loaded in under 2 s, a second run printed "already loaded", an unknown name exited 2.
- **Settled mid-build:**
  - User-approved (2026-10-06): door 3's Plaid IDs are `sample-<business_id>-<key>` instead of `sample-harbor_street-<seed>-<bank key>`, because the unique Plaid ID columns made a second load of one seed fail.
  - C20's `last_synced_at` is compared as an instant. The API writes it with the database session's offset (`-07:00` locally), not `Z`; that is existing spec 17 behaviour (its Verifier noted the same of C2), left untouched.
- **Abandoned:** none
