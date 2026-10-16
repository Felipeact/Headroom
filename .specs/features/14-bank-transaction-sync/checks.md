# 14 - Transaction sync checks

Profile: light
Plan: `.specs/features/14-bank-transaction-sync/plan.md`

47 checks in 7 slices · 8 one-way doors · 0 open

Commands run from `services/core/` (`uv run pytest ...`). `bash .specs/features/14-bank-transaction-sync/proofs.sh <cNN>` runs from anywhere in the repo. Unit tests drive `sync_connection` and the webhook with a fake `PlaidClient` (spec 12's pattern) and never call Plaid; webhook tests sign their own ES256 JWTs with a key generated per test session and served by the fake as the verification key. `TestClient` runs FastAPI background tasks before it returns, so a webhook or connect test reads the database right after the call. The test marked `plaid_sandbox` calls the real Plaid sandbox and runs only through `proofs.sh`, which exports `services/core/.env.local` first.

## Checks

### S1 - A sync stores every transaction once, signed and normalized · 8 files · 110 KB · ~28k

**C1** - On a connection with no cursor, `sync_connection` calls the fake's `sync_transactions` first with cursor `None`, then with page 1's `next_cursor`, stops after the page with `has_more` false, and stores every transaction of both pages (3 on page 1, 2 on page 2: 5 rows) (AC 1)
Proof: `uv run pytest tests/test_transaction_sync.py -k "first_sync_all_pages"`

**C2** - Stored `amount_cents` is the negated Plaid amount in cents, half-even (table-driven): `12.34` -> `-1234`, `-500.00` -> `50000`, `0.0` -> `0`, `1234.565` -> `-123456`, `-0.015` -> `2` (AC 2)
Proof: `uv run pytest tests/test_transaction_sync.py -k "amount_sign"`

**C3** - Stored `currency` is `iso_currency_code` when set (`CAD`), and `unofficial_currency_code` when the ISO code is null (`BTC`) (AC 3)
Proof: `uv run pytest tests/test_transaction_sync.py -k "currency_source"`

**C4** - A page holding a transaction with neither currency code makes `sync_connection` raise `PlaidError` with `error_type` `INVALID_RESPONSE` and `error_code` `NO_CURRENCY`; afterwards the connection has 0 transactions, its balances are as before and its cursor is still null (AC 4)
Proof: `uv run pytest tests/test_transaction_sync.py -k "no_currency_fails"`

**C5** - A transaction with Plaid `date` `2026-09-30`, `pending` `true` is stored with `date` equal to `datetime.date(2026, 9, 30)` in a `date` column and `pending` `true`; a posted one with `pending` `false` (AC 5)
Proof: `uv run pytest tests/test_transaction_sync.py -k "date_and_pending"`

**C6** - Text fields (table-driven): `description` is Plaid `name`; `counterparty` is the first `counterparties[].name` (`"Coastal Supply Co"`) when there are counterparties, else `merchant_name` (`"Birch & Co"`), else `null`; `category` / `category_detailed` are `personal_finance_category.primary` / `.detailed` (`"RENT_AND_UTILITIES"` / `"RENT_AND_UTILITIES_RENT"`), both `null` when Plaid gives no category (AC 6)
Proof: `uv run pytest tests/test_transaction_sync.py -k "text_fields"`

**C7** - Each stored transaction's `account_id` is the stored `bank_accounts.id` whose `plaid_account_id` matches the transaction's `account_id`, and its `business_id` is that account's `business_id` - checked across a connection with 2 accounts (AC 7)
Proof: `uv run pytest tests/test_transaction_sync.py -k "account_and_business"`

**C8** - A page whose `accounts` and transactions include a Plaid account not stored yet adds one `bank_accounts` row for it on the same connection with `included` `false` and `is_primary` `false`, mapped type and currency, and stores its transactions against it (AC 8)
Proof: `uv run pytest tests/test_transaction_sync.py -k "new_account_added"`

**C9** - After a sync whose last page reports a checking account at `current` `8000.00` / `available` `7900.50` and a line of credit at `current` `500.00` / `available` `19500.00`, those rows hold `balance_cents` `800000` / `available_cents` `790050` and `50000` / `1950000` (AC 9)
Proof: `uv run pytest tests/test_transaction_sync.py -k "balances_refreshed"`

**C10** - After a two-page sync, `bank_connections.transactions_cursor` equals page 2's `next_cursor`, and the next `sync_connection` call sends exactly that cursor to the fake (AC 10, door 2)
Proof: `uv run pytest tests/test_transaction_sync.py -k "cursor_stored"`

**C11** - A second `sync_connection` whose fake reports no added, modified or removed transactions and the same balances leaves every `bank_transactions` row (all columns, including `updated_at`), every balance and the cursor equal to before, and publishes no event (AC 11, "Done when" 1)
Proof: `uv run pytest tests/test_transaction_sync.py -k "second_sync_changes_nothing"`

**C12** - The same Plaid transaction ID in `added` on two syncs, the second with amount `20.00` instead of `10.00`, leaves exactly 1 row for that ID, holding `-2000` (AC 12, door 1 unique)
Proof: `uv run pytest tests/test_transaction_sync.py -k "added_twice_one_row"`

**C13** - A transaction reported in `modified` with a new amount, date and `name` updates the stored row to those values and keeps the row's `id` (AC 13)
Proof: `uv run pytest tests/test_transaction_sync.py -k "modified_updates_in_place"`

### S2 - Pending, removed and failed syncs leave the right data · 2 files · 45 KB · ~11k

**C14** - A Plaid transaction ID in `removed` deletes the stored row with that ID; the other rows remain (AC 14, "Done when" 2)
Proof: `uv run pytest tests/test_transaction_sync.py -k "removed_is_deleted"`

**C15** - A `removed` ID that is not stored is ignored: the sync completes, stores the page's other changes and the new cursor (AC 15)
Proof: `uv run pytest tests/test_transaction_sync.py -k "unknown_removed_ignored"`

**C16** - Sync 1 stores pending `p1`; sync 2 adds posted `t1` with `pending_transaction_id` `p1` and does not list `p1` in `removed`: afterwards `p1` is gone and `t1` is the one row; when sync 2 lists `p1` in `removed` on the same page instead, the result is the same single `t1` row (AC 16, "Done when" 2)
Proof: `uv run pytest tests/test_transaction_sync.py -k "pending_posts_once"`

**C17** - A fake that raises `TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION` on page 2 of the first attempt makes `sync_connection` restart with the stored cursor (the fake records cursors `None`, `c1`, `None`, `c1`), succeed, and store only the second attempt's transactions - a transaction present only in the first attempt's page 1 is not stored (AC 17)
Proof: `uv run pytest tests/test_transaction_sync.py -k "mutation_restarts"`

**C18** - A fake that raises the mutation error on every attempt makes `sync_connection` raise `PlaidError` after exactly 3 attempts; a fake that raises `ITEM_LOGIN_REQUIRED` on page 2 makes it raise `PlaidError` with that code; in both cases transactions, balances and the cursor equal their values before the sync (AC 18)
Proof: `uv run pytest tests/test_transaction_sync.py -k "failed_sync_rolls_back"`

**C19** - Two threads run `sync_connection` on one connection while the fake holds the first thread's Plaid call open: the second thread's first Plaid call happens only after the first thread's commit and carries the cursor the first stored; the connection ends with the first sync's rows, once each (AC 19)
Proof: `uv run pytest tests/test_transaction_sync.py -k "concurrent_syncs_serialize"`

### S3 - Other modules hear that data changed · 3 files · 25 KB · ~6k

**C20** - A sync that adds 2, modifies 1 and removes 1 transaction publishes exactly one event `Event(name="transactions.synced", business_id=<the connection's business>, payload={"connection_id": "<connection id>", "added": 2, "modified": 1, "removed": 1, "balances_changed": <bool>})`; a sync that changes only a balance publishes one with `added`, `modified`, `removed` `0` and `balances_changed` `true` (AC 20, door 4)
Proof: `uv run pytest tests/test_transaction_sync.py -k "event_published"`

**C21** - A handler subscribed to `transactions.synced` reads, through a new session, the rows the sync stored when it is called (it runs after the commit) (AC 21)
Proof: `uv run pytest tests/test_transaction_sync.py -k "event_after_commit"`

**C22** - With handlers `h1`, `h2` subscribed to `a.happened` and `h3` to `b.happened`, `publish(Event(name="a.happened", ...))` calls `h1` then `h2` with that event and never `h3` (AC 22, door 3)
Proof: `uv run pytest tests/test_events.py -k "publish_order_and_name"`

**C23** - With a raising handler between two recording ones, `publish` returns normally, both recording handlers are called, and one log line `event.handler_failed` carries `event_name`, `handler` and `error_type` (`"RuntimeError"`) and not the exception message (AC 23, door 3)
Proof: `uv run pytest tests/test_events.py -k "handler_failure_isolated"`

### S4 - Plaid's webhook triggers a sync, and only Plaid can trigger it · 6 files · 75 KB · ~19k

**C24** - `POST /v1/webhooks/plaid` with a valid body and (a) no `Plaid-Verification`, (b) `"not-a-jwt"`, (c) a JWT with `alg` `HS256`, (d) a JWT with `alg` `none` each returns `401` `application/problem+json` with `detail` exactly `"Invalid webhook signature."`, and the fake records 0 `sync_transactions` calls (AC 24, door 7)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "bad_header_rejected"`

**C25** - A JWT whose `kid` names the fake's key but that is signed with a different ES256 key returns `401` with the same detail and 0 sync calls (AC 25, door 7)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "wrong_key_rejected"`

**C26** - A JWT with `iat` 301 seconds before the request returns `401` with the same detail and 0 sync calls; one with `iat` 299 seconds before returns `200` (AC 26, door 7)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "stale_iat"`

**C27** - A JWT signed with the served key, but whose `request_body_sha256` is the hash of the body before one byte was changed returns `401` with the same detail and 0 sync calls (AC 27, door 7)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "body_hash_mismatch"`

**C28** - A key the fake returns with `expired_at` 1 second in the past returns `401` with the same detail and 0 sync calls; the same key with `expired_at` `null` returns `200` (AC 28, door 7)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "expired_key"`

**C29** - When the fake's `get_webhook_verification_key` raises `PlaidError`, the webhook returns `502` `application/problem+json` and the fake records 0 sync calls (AC 29)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "key_fetch_fails"`

**C30** - Two valid webhooks with the same `kid` make the fake record exactly 1 `get_webhook_verification_key` call (AC 30, door 7 cache)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "key_cached"`

**C31** - A valid webhook `{"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE", "item_id": <stored item>}` returns `200` with body exactly `{"status": "ok"}`, and afterwards the connection's transactions from the fake are stored and its cursor set (AC 31)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "sync_updates_available_syncs"`

**C32** - Valid webhooks with (a) `TRANSACTIONS` / `DEFAULT_UPDATE`, (b) `ITEM` / `ERROR`, (c) `TRANSACTIONS` / `SYNC_UPDATES_AVAILABLE` for an `item_id` that is not stored each return `200` `{"status": "ok"}` and the fake records 0 sync calls (AC 32)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "other_webhooks_ignored"`

**C33** - Bodies signed with the served key and a matching `request_body_sha256`: (a) `[]`, (b) `{"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE"}` (no `item_id`), (c) `item_id` `123` (not a string), (d) `"not json"` each return `422` `application/problem+json` and 0 sync calls (AC 33)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "malformed_body"`

**C34** - The only route under `/v1` that answers without an `Authorization` header is `POST /v1/webhooks/plaid`: the existing walk of every `/v1` route still gets `401` from every other route, and the list of `/v1` routes outside the authenticated router is exactly `["/v1/webhooks/plaid"]` (AC 34, door 6)
Proof: `uv run pytest tests/test_auth.py -k "every_v1_route_requires_token"`
Proof: `uv run pytest tests/test_plaid_webhook.py -k "only_public_v1_route"`

**C35** - When the sync started by a valid webhook raises `PlaidError` (`ITEM_LOGIN_REQUIRED`), the response is still `200` `{"status": "ok"}` and one log line `bank_sync.sync_failed` carries `connection_id`, `error_type`, `error_code` and `request_id` (AC 35)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "background_sync_failure_logged"`

### S5 - Connecting a bank starts the first sync · 4 files · 70 KB · ~18k

**C36** - `POST /v1/businesses/{business_id}/bank/connections` returns `201` and, by the time `TestClient` returns, the fake's transactions for the new connection are stored and its cursor is set (AC 36)
Proof: `uv run pytest tests/test_transaction_sync.py -k "connect_starts_sync"`

**C37** - When the fake's `sync_transactions` raises `PlaidError`, the connect still returns `201` with the connection JSON, the connection and accounts are stored, and one log line `bank_sync.sync_failed` is written (AC 37)
Proof: `uv run pytest tests/test_transaction_sync.py -k "connect_sync_failure"`

**C38** - With `PLAID_WEBHOOK_URL` set to `https://example.test/v1/webhooks/plaid`, the fake's recorded `LinkTokenRequest.webhook` is that URL; unset, it is `None`; and the real `PlaidClient` over a mocked `PlaidApi` puts `webhook` in `LinkTokenCreateRequest` only when it is not `None` (AC 38, door 8)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "link_token_webhook"`
Proof: `uv run pytest tests/test_plaid_client.py -k "link_token_webhook"`

### S6 - Real sandbox data comes in signed correctly · 2 files · 15 KB · ~4k

**C39** - Against the Plaid sandbox (`ins_42`, `user_good`), after the item's historical update is complete, every stored transaction's `amount_cents` equals `-to_cents` of the amount the real `PlaidClient` returned for its transaction ID, and the stored set holds at least 1 positive and 1 negative amount (AC 39, "Done when" 3)
Proof: `bash .specs/features/14-bank-transaction-sync/proofs.sh c39`

**C40** - In the same run, a second sync of the same item changes no `bank_transactions` row and publishes no `transactions.synced` event (AC 40, "Done when" 1)
Proof: `bash .specs/features/14-bank-transaction-sync/proofs.sh c39`

### S7 - Bank data stays private, and the schema holds · 6 files · 80 KB · ~20k

**C41** - Across a sync and a valid webhook with logs captured, no log line contains the access token, the `Plaid-Verification` value, the webhook body text, or any transaction's `name`, `merchant_name` or amount; the `bank_sync.synced` line carries `connection_id`, `added`, `modified`, `removed` (AC 41)
Proof: `uv run pytest tests/test_transaction_sync.py -k "no_secrets_logged"`

**C42** - Syncing business A's connection and then business B's connection, each with its own transactions, leaves every A transaction with A's `business_id` and every B transaction with B's, and A's sync writes 0 rows with B's `business_id` (AC 42)
Proof: `uv run pytest tests/test_transaction_sync.py -k "tenancy"`

**C43** - Every public function in `bank_sync/repository.py` that reads or writes `bank_transactions` takes a keyword `business_id` parameter, and the only repository function that queries `bank_connections` without `business_id` is the lookup by Plaid item ID (AC 43)
Proof: `uv run pytest tests/test_transaction_sync.py -k "repository_requires_business"`

**C44** - After `alembic upgrade head` on an empty database, `bank_transactions` has `id` uuid pk, `business_id` uuid not null, `account_id` uuid not null FK to `bank_accounts.id`, `plaid_transaction_id` text not null with unique `uq_bank_transactions_plaid_transaction_id`, `amount_cents` bigint not null, `currency` text not null, `date` date not null, `pending` boolean not null, `description` text not null, `counterparty`, `category`, `category_detailed` text null, `created_at` / `updated_at` timestamptz not null; `bank_connections.transactions_cursor` is text null; `alembic downgrade -1` drops both; `alembic check` reports no differences at head (doors 1, 2)
Proof: `uv run pytest tests/test_migrations.py -k "bank_transactions"`

**C45** - The real `PlaidClient` over a mocked `PlaidApi`: `sync_transactions(token, None)` sends `count` `500`, `options.include_personal_finance_category` `true` and no `cursor`; `sync_transactions(token, "c1")` sends `cursor` `"c1"`; the response's `added`, `modified`, `removed`, `accounts`, `next_cursor`, `has_more` map to plain dataclasses with each field of C2-C6; an `ApiException` with `error_code` `TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION` raises `PlaidError` with that code; `get_webhook_verification_key("k1")` returns the JWK as a `dict` with `expired_at` (door 5, door 7)
Proof: `uv run pytest tests/test_plaid_client.py -k "sync_transactions or webhook_verification_key"`

**C46** - `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` regenerate with no diff and contain `/v1/webhooks/plaid` (Impact: API contract)
Proof: `bash .specs/features/14-bank-transaction-sync/proofs.sh c46`

**C47** - Every AGENTS.md check for the API passes at `HEAD`: `ruff format --check`, `ruff check`, `mypy app`, `pytest`; and the web checks still pass with the regenerated types (`npm run lint && npm run typecheck && npm test && npm run build`)
Proof: `bash .specs/features/14-bank-transaction-sync/proofs.sh c47`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST /v1/webhooks/plaid` statuses (4) | 200 C26, C28, C31, C32, C35 · 401 C24, C25, C26, C27, C28 · 422 C33 · 502 C29 | - |
| one-way doors (8) | door 1 C12, C44 · door 2 C10, C44 · door 3 C22, C23 · door 4 C20 · door 5 C45, C17 · door 6 C34 · door 7 C24-C30, C45 · door 8 C38 | - |
| entities (2) | `bank_transactions` C44 · `bank_connections.transactions_cursor` C44, C10 | - |
| Plaid change kinds (3) | added C1, C12 · modified C13 · removed C14, C15 | - |
| transaction fields normalized (9) | amount C2 · currency C3, C4 · date C5 · pending C5 · description C6 · counterparty C6 · category C6 · account C7 · business C7, C42 | - |
| counterparty sources (3) | counterparties C6 · merchant_name C6 · none C6 | - |
| balance fields refreshed (2) | `balance_cents` C9 · `available_cents` C9 | - |
| sync failure kinds (4) | no currency C4 · mutation exhausted C18 · other Plaid error C18 · webhook background failure C35, connect background failure C37 | - |
| signature rejections (7) | missing C24 · not JWT C24 · wrong alg C24 · wrong key C25 · stale iat C26 · body hash C27 · expired key C28 | - |
| webhook dispatch (4) | SYNC_UPDATES_AVAILABLE C31 · other TRANSACTIONS code C32 · other type C32 · unknown item C32 | - |
| sync triggers (3) | connect C36 · webhook C31 · direct call (spec 15's entry) C1 | - |
| event outcomes (3) | changed transactions C20 · balance only C20 · nothing changed C11, C40 | - |
| startup config: `PLAID_WEBHOOK_URL` (2 assemblies) | fake used by unit tests C38 · real `PlaidClient` C38 | - |
| startup config: public webhook router (2 assemblies) | `app.main` route table C34 · `TestClient(app)` requests C31 | - |

- Claims naming a status code, route or response shape (C24-C35, C36, C37) are proven through `TestClient` at the HTTP boundary; S1-S3 claims assert at the service layer, where pages and errors can be scripted; C19 runs two threads against the database because two simultaneous syncs cannot be ordered through `TestClient`
- C39 and C40 are the only proofs on real provider data; every other proof uses the fake, and C45 proves the real client's mapping that the fake stands in for
- No other check claims more than the single case its proof exercises

## Swept

- validation: C33 (webhook body), C24-C28 (signature), C4 (transaction with no currency)
- failure modes: C4, C18 (sync rolls back whole), C29 (key fetch), C35, C37 (background failure leaves the response intact)
- idempotency: C11, C12, C40 (same sync twice, same transaction twice); duplicate webhook deliveries reduce to C11 through C31
- authorization: C24-C28 (only Plaid's signature), C34 (every other `/v1` route still needs a token), C42, C43 (tenancy)
- concurrency: C19 (two syncs of one connection serialize on the row lock)
- data lifecycle: C14, C16 (removed and replaced transactions are deleted); C44 (new table, no backfill: existing connections start with a null cursor and pull full history on their first sync, C1)
- dependency failure: C18, C29, C35, C37 (Plaid down or erroring); C17 (Plaid's mutation-during-pagination); C39 crosses the real sandbox
- state transitions: C16 (pending -> posted); C10 (cursor null -> set -> advanced)
- observability: C23 (`event.handler_failed`), C35, C37 (`bank_sync.sync_failed`), C41 (`bank_sync.synced` with counts, nothing sensitive)

## Handoff

- S1-S7 touch about 20 files: existing `bank_sync/{api,service,repository,models,plaid}.py` (32 KB), `app/main.py`, `app/settings.py` (5 KB), `test_bank_connect.py` (30 KB), `test_plaid_client.py`, `test_auth.py`, `test_migrations.py` (40 KB), `openapi.json` + `schema.d.ts` (60 KB) = ~170 KB; new `app/events.py`, `bank_sync/webhooks.py`, the migration, `test_transaction_sync.py`, `test_events.py`, `test_plaid_webhook.py`, `test_transaction_sync_sandbox.py`, `proofs.sh` = ~90 KB; 260 KB / 4 = ~65k tokens, under the 150k budget - one builder

- **Boundary:** C1-C38, C41-C47 closed at `ae4c0e2`; every proof green there (API 334 passed, web 185 passed, `proofs.sh c46`, `c47`). C39-C40 are written (`tests/test_transaction_sync_sandbox.py`, `proofs.sh c39`) and not yet run: this machine's `services/core/.env.local` holds no Plaid sandbox keys
- **Settled mid-build:** none asked of the user. Builder decisions: Plaid transaction IDs are globally unique (door 1), so the fake in `test_transaction_sync.py` suffixes each test's IDs; spec 13's migration test now targets its own revision `d546cee847e0` rather than head, its assertions unchanged (as spec 13 did for spec 12); spec 12's `FakePlaid` answers `sync_transactions` with an empty update, so spec 12 and 13 tests are unchanged; `PLAID_WEBHOOK_URL=` (empty, as copied from `.env.example`) means unset, with a third case in C38's test; spec 10's `/v1` route walk passes unchanged because the webhook answers `401` without a signature, and C34's new test tells the two `401`s apart by `detail`; `bank_sync/webhooks.py` holds the verification, `bank_sync/events.py` the event name
- **Abandoned:** finding public routes through `app.routes`: FastAPI 0.142 keeps included routes behind private `_IncludedRouter` objects, so C34 classifies routes by their unauthenticated response instead
