# 14 - Transaction sync verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: cb8a360..3c686ba
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

The FAIL rests on one gap: C39 and C40, the only proofs that use real Plaid data, could not run. `services/core/.env.local` on this machine has no Plaid sandbox keys. This is blocked on credentials, not a code defect. C1-C38 and C41-C47 all PASS at HEAD with located assertions. Spec "Done when" 3 ("money out is negative and money in is positive for all sandbox data") has no executed proof until `proofs.sh c39` runs with sandbox keys.

## Binding sources

Profile `light`: step 1 does not run. For reference, these binding sources were read: `context/specs/14-bank-transaction-sync.md` (Build list and 4 "Done when" items) and `AGENTS.md` (sign rule, money in cents with a currency code, the webhook signature checked before any work, no raw provider data or tokens in logs, tenancy). Neither contradicts a check. The code was also read against Landing doors 1-8. See the observations below.

## Checks

Batch proof run at HEAD 3c686ba, from `services/core`: `uv run pytest tests/test_transaction_sync.py tests/test_events.py tests/test_plaid_webhook.py tests/test_auth.py tests/test_plaid_client.py tests/test_migrations.py -v -p no:logging -k "<every -k selector from checks.md>"`. Result: 58 passed, 45 deselected, exit 0. Each test below appeared in that output individually as PASSED.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | First sync uses cursor None, then c1, stops at has_more false, and stores 5 rows | `test_first_sync_all_pages` PASSED | `services/core/tests/test_transaction_sync.py:321` - `assert fake.cursors == [None, "c1"]`; `:323` - `sorted(rows(...)) == ["t1","t2","t3","t4","t5"]` | PASS |
| C2 | amount_cents = -to_cents, half-even, 5 cases | `test_amount_sign[...]` x5 PASSED | `services/core/tests/test_transaction_sync.py:342` - `assert rows(c.business_id)["t1"].amount_cents == cents` (table at :329-333: 12.34->-1234, -500.0->50000, 0.0->0, 1234.565->-123456, -0.015->2) | PASS |
| C3 | currency is the ISO code (CAD), else the unofficial code (BTC) | `test_currency_source` PASSED | `services/core/tests/test_transaction_sync.py:360` - `stored["iso"].currency == "CAD"`; `:361` - `stored["unofficial"].currency == "BTC"` | PASS |
| C4 | no currency gives PlaidError INVALID_RESPONSE/NO_CURRENCY; nothing stored, cursor null | `test_no_currency_fails` PASSED | `services/core/tests/test_transaction_sync.py:378-379` - `error_type == "INVALID_RESPONSE"`, `error_code == "NO_CURRENCY"`; `:381` - `snapshot(...) == before`; `:382` - `cursor_of(c) is None` | PASS |
| C5 | date stored as `date(2026,9,30)`; pending flags kept | `test_date_and_pending` PASSED | `services/core/tests/test_transaction_sync.py:400-403` - `.date == date(2026, 9, 30)`, `type(...) is date`, `.pending is True`, `stored["posted"].pending is False` | PASS |
| C6 | description, counterparty (counterparties > merchant > null), category/detailed | `test_text_fields[...]` x3 PASSED | `services/core/tests/test_transaction_sync.py:445` - `stored["t1"].counterparty == counterparty` (params: Coastal Supply Co / Birch & Co / None); `:444` description; `:446-450` categories and nulls | PASS |
| C7 | account_id is the matched stored account; business_id is that account's business (2 accounts) | `test_account_and_business` PASSED | `services/core/tests/test_transaction_sync.py:461-463` - `stored["on-chq"].account_id == accounts[chq.account_id].id`, same for loc, `{r.business_id ...} == {c.business_id}` | PASS |
| C8 | an unknown account is added with included false and primary false, then gets its transactions | `test_new_account_added` PASSED | `services/core/tests/test_transaction_sync.py:477` - `(new.type, new.currency, new.included, new.is_primary) == ("savings","CAD",False,False)`; `:483` - `account_id == new.id` | PASS |
| C9 | balances from the last page: 800000/790050 and 50000/1950000 | `test_balances_refreshed` PASSED | `services/core/tests/test_transaction_sync.py:513-517` - `balance_cents == 800000`, `available_cents == 790050`, LOC `50000` / `1950000` | PASS |
| C10 | cursor = page 2's next_cursor; the next sync sends it | `test_cursor_stored` PASSED | `services/core/tests/test_transaction_sync.py:528` - `cursor_of(c) == "c2"`; `:531` - `fake.cursors == [None, "c1", "c2"]` | PASS |
| C11 | a no-op second sync changes no column (updated_at included), balance or cursor, and publishes nothing | `test_second_sync_changes_nothing` PASSED | `services/core/tests/test_transaction_sync.py:555` - `snapshot(c.business_id) == before` (all mapped columns, `:220`); `:556` - `published == []` | PASS |
| C12 | the same ID added twice leaves 1 row holding -2000 | `test_added_twice_one_row` PASSED | `services/core/tests/test_transaction_sync.py:575-576` - `len(found) == 1`, `found[0].amount_cents == -2000` | PASS |
| C13 | a modified transaction updates amount, date and name and keeps its id | `test_modified_updates_in_place` PASSED | `services/core/tests/test_transaction_sync.py:595` - `row.id == first_id`; `:596` - `(amount_cents, date, description) == (-1550, date(2026,10,1), "New")` | PASS |
| C14 | removed deletes that row; the other rows stay | `test_removed_is_deleted` PASSED | `services/core/tests/test_transaction_sync.py:616` - `sorted(rows(c.business_id)) == ["b"]` | PASS |
| C15 | an unknown removed ID is ignored; the rest of the page and the cursor are stored | `test_unknown_removed_ignored` PASSED | `services/core/tests/test_transaction_sync.py:627-628` - `== ["c"]`, `cursor_of(c) == "c9"` | PASS |
| C16 | pending p1 is replaced by posted t1, with or without removal in the same page | `test_pending_posts_once[False/True]` PASSED | `services/core/tests/test_transaction_sync.py:651-652` - `sorted(stored) == ["t1"]`, `stored["t1"].pending is False` | PASS |
| C17 | a mutation restarts from the stored cursor (None,c1,None,c1); first-attempt-only rows are dropped | `test_mutation_restarts` PASSED | `services/core/tests/test_transaction_sync.py:667-668` - `fake.cursors == [None, "c1", None, "c1"]`, `sorted(rows(...)) == ["x", "y"]` | PASS |
| C18 | a mutation on every attempt raises after exactly 3 attempts; ITEM_LOGIN_REQUIRED raises; both roll back | `test_failed_sync_rolls_back[mutation_exhausted/item_login_required]` PASSED | `services/core/tests/test_transaction_sync.py:706` - `fake.cursors.count("c0") == 3`; `:709` - `error_code == "ITEM_LOGIN_REQUIRED"`; `:710` - `snapshot(c.business_id) == before` | PASS |
| C19 | two threads serialize; the second starts after the commit with the stored cursor | `test_concurrent_syncs_serialize` PASSED | `services/core/tests/test_transaction_sync.py:732` - `fake.cursors == [None]` while the first is held; `:738-739` - `fake.cursors == [None, "cA"]`, `== ["a"]` | PASS |
| C20 | one event with payload 2/1/1; a balance-only sync gives 0/0/0 with balances_changed true | `test_event_published` PASSED | `services/core/tests/test_transaction_sync.py:765` - `published == [Event(name="transactions.synced", business_id=..., payload={... "added": 2, "modified": 1, "removed": 1, "balances_changed": False})]`; `:782` - 0/0/0, `True` | PASS |
| C21 | the handler sees committed rows through a new session | `test_event_after_commit` PASSED | `services/core/tests/test_transaction_sync.py:820` - `assert seen == [2]` | PASS |
| C22 | h1 then h2 are called, never h3 | `test_publish_order_and_name` PASSED | `services/core/tests/test_events.py:49` - `assert calls == [("h1", event), ("h2", event)]` | PASS |
| C23 | a raising handler is isolated and logged with event_name, handler and error_type, without the message | `test_handler_failure_isolated` PASSED | `services/core/tests/test_events.py:74` - `calls == ["before", "after"]`; `:78-82` - one line, `error_type == "RuntimeError"`, `"secret detail 4471" not in out` | PASS |
| C24 | missing, not-a-JWT, HS256 and none give 401 problem+json with the exact detail and 0 syncs | `test_bad_header_rejected` PASSED | `services/core/tests/test_plaid_webhook.py:71-74` (assert_invalid) - `status_code == 401`, `content-type == "application/problem+json"`, `detail == INVALID`, `fake.cursors == []`; header loop at `:93-103` | PASS |
| C25 | wrong ES256 key gives 401 | `test_wrong_key_rejected` PASSED | `services/core/tests/test_plaid_webhook.py:111` - `assert_invalid(response, fake)` with `key=signing.OTHER_KEY` (`:109`) | PASS |
| C26 | iat 301s ago gives 401; 299s ago gives 200 | `test_stale_iat` PASSED | `services/core/tests/test_plaid_webhook.py:118` - `assert_invalid(post(..., iat=now - 301))`; `:120` - `status_code == 200` for `now - 299` | PASS |
| C27 | a body changed by one byte gives 401 | `test_body_hash_mismatch` PASSED | `services/core/tests/test_plaid_webhook.py:128` - `assert_invalid(post(tampered, headers), fake)` | PASS |
| C28 | a key expired 1s ago gives 401; expired_at null gives 200 | `test_expired_key` PASSED | `services/core/tests/test_plaid_webhook.py:135` - assert_invalid; `:139` - `status_code == 200` | PASS |
| C29 | a failed key fetch gives 502 problem+json and 0 syncs | `test_key_fetch_fails` PASSED | `services/core/tests/test_plaid_webhook.py:150-152` - `== 502`, `application/problem+json`, `fake.cursors == []` | PASS |
| C30 | the same kid twice fetches the key once | `test_key_cached` PASSED | `services/core/tests/test_plaid_webhook.py:161` - `assert fake.key_calls == [signing.KID]` | PASS |
| C31 | SYNC_UPDATES_AVAILABLE gives 200 `{"status":"ok"}`, then rows stored and the cursor set | `test_sync_updates_available_syncs` PASSED | `services/core/tests/test_plaid_webhook.py:175` - `response.json() == {"status": "ok"}`; `:176` - `stored_count(c) == 2`; `:183` - `cursor == "cw"` | PASS |
| C32 | DEFAULT_UPDATE, ITEM/ERROR and an unknown item give 200 ok and 0 syncs | `test_other_webhooks_ignored` PASSED | `services/core/tests/test_plaid_webhook.py:197-199` - `== 200`, `== {"status": "ok"}`, `fake.cursors == []` | PASS |
| C33 | malformed signed bodies give 422 problem+json and 0 syncs | `test_malformed_body` PASSED | `services/core/tests/test_plaid_webhook.py:219-221` - `status_code == 422`, `application/problem+json`, `fake.cursors == []` | PASS |
| C34 | every other /v1 route answers 401; the only public /v1 route is the webhook | `test_every_v1_route_requires_token` PASSED, `test_only_public_v1_route` PASSED | `services/core/tests/test_auth.py:206` - `assert response.status_code == 401, (method, path)`; `services/core/tests/test_plaid_webhook.py:240` - `assert public == [("post", URL)]` | PASS |
| C35 | a failed background sync still returns 200 ok and logs sync_failed with 4 fields | `test_background_sync_failure_logged` PASSED | `services/core/tests/test_plaid_webhook.py:257-265` - `== 200`, `{"status": "ok"}`, `len(failed) == 1`, `connection_id`, `error_type == "ITEM_ERROR"`, `error_code`, `request_id == "r-7"` | PASS |
| C36 | connect returns 201; rows and cursor are stored by the time TestClient returns | `test_connect_starts_sync` PASSED | `services/core/tests/test_transaction_sync.py:834` - `== 201`; `:836` - `sorted(stored) == ["first", "second"]`; `:843` - `cursor == "c1"` | PASS |
| C37 | a failed first sync still returns 201 with accounts stored and one sync_failed line | `test_connect_sync_failure` PASSED | `services/core/tests/test_transaction_sync.py:864-871` - `== 201`, `len(accounts) == 2` (response and DB), `len(failed) == 1`, `error_code == "ITEM_LOGIN_REQUIRED"` | PASS |
| C38 | PLAID_WEBHOOK_URL is passed through the fake when set, None when unset or empty; the real client sends webhook only when not None | `test_plaid_webhook.py::test_link_token_webhook` x3, `test_plaid_client.py::test_link_token_webhook` x2 PASSED | `services/core/tests/test_plaid_webhook.py:303` - `fake.link_requests[-1].webhook == url`; `services/core/tests/test_plaid_client.py:171` - `request.get("webhook") == webhook` | PASS |
| C39 | real sandbox: every amount_cents = -to_cents(Plaid amount); at least one positive and one negative | `bash .specs/features/14-bank-transaction-sync/proofs.sh c39` - FAILED at the credentials guard: `AssertionError: export services/core/.env.local first` (`plaid_client_id == 'test-client-id'`); `.env.local` has no PLAID_* keys | would settle: `services/core/tests/test_transaction_sync_sandbox.py:102` - `set(stored) == set(plaid_amounts)`; `:104` - `cents == -(service.to_cents(plaid_amounts[transaction_id]) or 0)`; `:107-108` - `any(cents > 0)`, `any(cents < 0)` | NOT RUN - sandbox keys missing |
| C40 | real sandbox: a second sync changes no row and publishes no event | same run as C39 - not reached | would settle: `services/core/tests/test_transaction_sync_sandbox.py:118-120` - `not again.changed`, `seen == []`, `snapshot(business_id) == before` | NOT RUN - sandbox keys missing |
| C41 | no token, header, body, name, merchant or amount in the logs; synced line carries the counts | `test_no_secrets_logged` PASSED | `services/core/tests/test_transaction_sync.py:929` - `assert [v for v in leaks if v in logs] == []` (leaks at `:920-928`: ACCESS_TOKEN, Plaid-Verification, body, name, "Birch & Co", "1234.56", "123456"); `:916` - the synced line has `connection_id, added, modified, removed` | PASS |
| C42 | A's sync writes no row with B's business_id, and each business's rows carry its own ID | `test_tenancy` PASSED | `services/core/tests/test_transaction_sync.py:941` - `rows(b.business_id) == {}` after A's sync; `:946`, `:948` - business_id sets equal their own business | PASS |
| C43 | transaction repository functions require keyword business_id; the only unscoped connection query is connection_for_item | `test_repository_requires_business` PASSED | `services/core/tests/test_transaction_sync.py:967` - `assert scoped, name`; `:972` - `unscoped_connection_queries == ["connection_for_item"]` | PASS |
| C44 | schema after upgrade; downgrade drops both; check is clean | `test_bank_transactions_upgrade_downgrade_and_check` PASSED | `services/core/tests/test_migrations.py:504-519` - full `(column, type, nullable)` set; `:520` - `cursor == ("text","YES")`; `:522-531` - uq, pk and fk constraints; `:541-542` - dropped after downgrade; `:546` - `check` returncode 0 | PASS |
| C45 | real client: count 500, PFC option, no cursor then "c1", dataclass mapping, mutation error code, JWK dict | `test_sync_transactions_request_and_mapping`, `test_sync_transactions_mutation_error`, `test_webhook_verification_key` PASSED | `services/core/tests/test_plaid_client.py:234-237` - `count == 500`, `include_personal_finance_category is True`, `get("cursor") is None`, `second.cursor == "c1"`; `:241` - `result == SyncPage(...)`; `:310` - `error_code == "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"`; `:333-335` - `result == key`, `isinstance(result, dict)`, `"expired_at" in result` | PASS |
| C46 | the generated files regenerate with no diff and contain the route | `bash proofs.sh c46` - `PASS c46`, exit 0; `git status --porcelain` empty afterwards | `.specs/features/14-bank-transaction-sync/proofs.sh:27` - `git diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts`; `:29`, `:31` - `grep -qF '"/v1/webhooks/plaid"'` | PASS |
| C47 | every AGENTS.md check passes | `bash proofs.sh c47` - ruff format (59 files already formatted), ruff check (all passed), mypy (no issues, 27 files), pytest 334 passed / 3 deselected; eslint, typecheck, vitest 185 passed (25 files), next build OK; `PASS c47`, exit 0 | `.specs/features/14-bank-transaction-sync/proofs.sh:37-40` - the chained `&&` command, with `fail c47` on any non-zero exit | PASS |

### Precision and level observations (not failing)

- C33: the claim's case (d) is the JSON string `"not json"`. The test sends `b'"not json'` (`services/core/tests/test_plaid_webhook.py:215`), which is not valid JSON at all. A well-formed JSON scalar that is not an object is only covered by `[]` (case a). The 422 still holds, but the literal differs from the claim.
- C43: the proof reads the source text. It checks for a keyword-only `business_id` parameter and does not check that the query filters on it. When the code was read, every new repository function did filter: `services/core/app/modules/bank_sync/repository.py` `transactions_by_plaid_id`, `delete_transactions`, `lock_connection` and `connection_accounts` all have `.where(... business_id == business_id ...)`, and `insert_transaction` raises on a mismatch. A function that takes the parameter and ignores it would still pass the test.
- C34: it sorts routes by the Clerk `detail` string ("Authentication required."), so it depends on that copy staying the same. That is acceptable, and the Handoff records it.
- C40: in the test, the "second sync" is the sync that follows the wait-for-ready loop, which can itself run the sync several times. That still matches the claim, which is no new activity after the history has settled.
- Level: every claim that names a status code, route or response body (C24-C37) is proven through `TestClient` at the HTTP boundary. Event and sync claims (C1-C23) are asserted at the service layer and name no HTTP shape. No level gaps.
- Sampling: the table-driven checks (C2 with 5 cases, C6 with 3, C24 with 4, C32 with 3, C33 with 4, C38 with 3+2) each exercise every case their claim lists. No sampling gaps.

### Code against Landing doors and AGENTS.md (observations)

- Doors 1-8 match the code. Door 1 is the model and migration. Door 2 is `transactions_cursor`, written in the same transaction as the changes in `_apply`/`sync_connection`. Door 3 is `app/events.py`, which adds an `unsubscribe` helper the door does not list, used by tests. Door 4 is the `service.py` publish after `session.commit()`. Door 5 is `plaid.py` `sync_transactions`/`SyncPage`. Door 6 is `app/main.py`, `APIRouter(prefix="/v1/webhooks")`. Door 7 is `bank_sync/webhooks.py`, which checks ES256, kid, expired_at, `algorithms=["ES256"]`, iat <= 300 and `hmac.compare_digest`. Door 8 is the `settings.py` setting with empty treated as None.
- The sign flip happens only in `bank_sync/service.py` `_values` (`"amount_cents": -cents`). The webhook signature is verified before the body is parsed and before any DB query. The only dependency built before verification is a session that has not been used yet.
- Minor, outside any check: `service.sync_in_background` catches only `PlaidError`. A `ConnectionNotFoundError` or a database error, such as an `IntegrityError` from the global unique constraint, would escape the background task as an unhandled exception. SQLAlchemy's `IntegrityError` text includes the bound parameters (description, amount), which could reach the server error log or Sentry. That conflicts with AGENTS.md's "no raw provider data in logs" on an error path no check exercises. Not counted as a failure here, but worth a follow-up.
- Minor: `plaid.webhook_unknown_item` logs `plaid_item_id`, a field from the webhook body. It is an identifier, not a secret, so it fits AC 41's "IDs only".

## Coverage

Profile `light`: the author's table is read, not recomputed. For each member, the proof the author named was found and ran above.

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| webhook statuses (4) | author's table (read) | 200 C26/C28/C31/C32/C35 · 401 C24-C28 · 422 C33 · 502 C29 - all located and PASS | - |
| one-way doors (8) | author's table (read) | door 1 C12/C44 · 2 C10/C44 · 3 C22/C23 · 4 C20 · 5 C45/C17 · 6 C34 · 7 C24-C30/C45 · 8 C38 - all located | - |
| entities (2) | author's table (read) | C44, C10 | - |
| Plaid change kinds (3) | author's table (read) | C1/C12, C13, C14/C15 | - |
| transaction fields (9) | author's table (read) | C2-C7, C42 | - |
| counterparty sources (3) | author's table (read) | C6 params x3 | - |
| balance fields (2) | author's table (read) | C9 | - |
| sync failure kinds (4) | author's table (read) | C4, C18 x2, C35/C37 | - |
| signature rejections (7) | author's table (read) | C24 x3 (missing, not JWT, wrong alg incl. none), C25, C26, C27, C28 | - |
| webhook dispatch (4) | author's table (read) | C31, C32 x3 | - |
| sync triggers (3) | author's table (read) | C36, C31, C1 | - |
| event outcomes (3) | author's table (read) | C20 x2, C11 (C40 not run) | - |
| startup config PLAID_WEBHOOK_URL (2) | author's table (read) | C38 fake + real client | - |
| startup config public router (2) | author's table (read) | `services/core/app/main.py` builds `webhooks = APIRouter(prefix="/v1/webhooks")` and includes it in `app`; C34, C31 | - |
| spec "Done when" items (4) - not in the author's table | `context/specs/14-bank-transaction-sync.md` | 1 C11 (C40 not run) · 2 C14/C16 · 3 C39 only · 4 C24-C28 | Done when 3 (money out negative / money in positive for all sandbox data): its only proof C39 was not run, because the sandbox keys are missing |

## Swept

There are no Swept rows that resolve to "existing" in `checks.md`. The one "existing" decision is in the plan's Observable table: versioning, "under `/v1` like every route". In the code, the route is `/v1/webhooks/plaid` (`services/core/app/main.py`, `APIRouter(prefix="/v1/webhooks")`, plus `@webhook_router.post("/plaid")` in `bank_sync/api.py`), so that holds.

## Faults injected

None: fault injection does not run at profile `light`.

## Gate

- Targeted batch: `uv run pytest ... -k "<all selectors>" -v -p no:logging` - 58 passed, 0 failed
- `bash .specs/features/14-bank-transaction-sync/proofs.sh c46 c47` - PASS c46, PASS c47 (API 334 passed / 0 failed / 3 deselected; web 185 passed / 0 failed; build OK)
- `bash .specs/features/14-bank-transaction-sync/proofs.sh c39` - 1 failed at the credentials guard (`tests/test_transaction_sync_sandbox.py:47`); no sandbox keys
- Real tree `git status --porcelain` was empty before and after

## Ranked gaps

1. C39, C40 - NOT RUN, blocked on credentials, not a code defect. `services/core/.env.local` has no `PLAID_CLIENT_ID`/`PLAID_SECRET`, so `proofs.sh c39` stops at `services/core/tests/test_transaction_sync_sandbox.py:47`. The test asserts what C39 and C40 claim (`:102`, `:104`, `:107-108`, `:118-120`). To close: add the sandbox keys and run `bash .specs/features/14-bank-transaction-sync/proofs.sh c39`. Spec "Done when" 3 stays unproven until then.
2. Precision (non-failing): C33 case (d) sends invalid JSON `'"not json'`, not the JSON string `"not json"` the claim names. See `services/core/tests/test_plaid_webhook.py:215`.
3. Precision (non-failing): C43 checks the parameter signature through the source text, not the query filter. See `services/core/tests/test_transaction_sync.py:952-972`.
4. Observation (non-failing): `sync_in_background` lets non-`PlaidError` exceptions escape, and a SQLAlchemy `IntegrityError` message there would carry transaction values into error logs. See `services/core/app/modules/bank_sync/service.py` `sync_in_background`.
