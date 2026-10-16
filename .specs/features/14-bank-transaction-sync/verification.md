# 14 - Transaction sync verification

**Verdict**: PASS
**Profile**: light
**Diff range**: cb8a360..d7b56f9
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

Round 1 (at `3c686ba`) was FAIL on one gap: C39 and C40 had not run, because there were no Plaid sandbox keys. The keys are now in `services/core/.env.local`, and `proofs.sh c39` passes at `d7b56f9`. The real sandbox item synced, every stored amount equals the negated Plaid amount, both signs are present, and a second sync changed nothing. Round 1's C33 precision gap is closed by `4dd73cd`. Re-checked against `d7b56f9`, C38 proves both the "set" case and a truly "unset" case, even with a developer's `.env.local` holding a URL. All 47 checks PASS.

Scope of this round: `3c686ba..d7b56f9` touches only `services/core/tests/conftest.py` (+3 lines), `services/core/tests/test_plaid_webhook.py` (+5/-1), `.specs/STATE.md`, and this report. No application code changed. Every proof was re-run in full at `d7b56f9`. Citations in the two touched test files were refreshed. The other evidence cells are carried from `3c686ba`, because their files are byte-identical in that range.

## Binding sources

Carried from 3c686ba. Profile `light`: step 1 does not run. The fixes touched no interface.

## Checks

Verified at d7b56f9. Batch proof run from `services/core`: `uv run pytest tests/test_transaction_sync.py tests/test_events.py tests/test_plaid_webhook.py tests/test_auth.py tests/test_plaid_client.py tests/test_migrations.py -v -p no:logging -k "<every -k selector from checks.md, C1-C45 except C39/C40>"`. Result: 58 passed, 45 deselected, exit 0. Each test below appeared in that output individually as PASSED. `bash .specs/features/14-bank-transaction-sync/proofs.sh c39 c46 c47` gave `PASS c39`, `PASS c46` and `PASS c47`, exit 0.

The "Evidence" column marks where each citation comes from. **Re-verified at d7b56f9** means it was refreshed or newly settled in this round. **Carried from 3c686ba** means the test file is unchanged in the fix range, so the round 1 line numbers still hold. The proofs for those rows still re-ran green at d7b56f9.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | First sync uses cursor None, then c1, stops at has_more false, and stores 5 rows | `test_first_sync_all_pages` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:321` - `assert fake.cursors == [None, "c1"]`; `:323` - 5 rows t1-t5 | PASS |
| C2 | amount_cents = -to_cents, half-even, 5 cases | `test_amount_sign[...]` x5 PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:342` - `rows(c.business_id)["t1"].amount_cents == cents` (table at :329-333) | PASS |
| C3 | currency is ISO (CAD), else unofficial (BTC) | `test_currency_source` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:360-361` | PASS |
| C4 | no currency gives INVALID_RESPONSE/NO_CURRENCY; nothing stored, cursor null | `test_no_currency_fails` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:378-382` | PASS |
| C5 | date `date(2026,9,30)`; pending kept | `test_date_and_pending` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:400-403` | PASS |
| C6 | description, counterparty precedence, categories | `test_text_fields[...]` x3 PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:444-450` | PASS |
| C7 | account_id and business_id from the matched account (2 accounts) | `test_account_and_business` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:461-463` | PASS |
| C8 | unknown account added with included/primary false | `test_new_account_added` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:477`, `:483` | PASS |
| C9 | balances 800000/790050 and 50000/1950000 | `test_balances_refreshed` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:513-517` | PASS |
| C10 | cursor = page 2 next_cursor; resent next sync | `test_cursor_stored` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:528`, `:531` | PASS |
| C11 | no-op second sync changes nothing, publishes nothing | `test_second_sync_changes_nothing` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:555-556` | PASS |
| C12 | same ID added twice: 1 row, -2000 | `test_added_twice_one_row` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:575-576` | PASS |
| C13 | modified updates in place, keeps id | `test_modified_updates_in_place` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:595-596` | PASS |
| C14 | removed deletes that row only | `test_removed_is_deleted` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:616` | PASS |
| C15 | unknown removed ID ignored; rest and cursor stored | `test_unknown_removed_ignored` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:627-628` | PASS |
| C16 | pending p1 replaced by posted t1, both variants | `test_pending_posts_once[False/True]` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:651-652` | PASS |
| C17 | mutation restarts from stored cursor; first-attempt rows dropped | `test_mutation_restarts` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:667-668` | PASS |
| C18 | 3 attempts then raise; ITEM_LOGIN_REQUIRED raises; both roll back | `test_failed_sync_rolls_back[...]` x2 PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:706`, `:709`, `:710` | PASS |
| C19 | concurrent syncs serialize on the row lock | `test_concurrent_syncs_serialize` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:732`, `:738-739` | PASS |
| C20 | one event 2/1/1; balance-only 0/0/0 with balances_changed true | `test_event_published` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:765`, `:782` | PASS |
| C21 | handler sees committed rows | `test_event_after_commit` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:820` - `assert seen == [2]` | PASS |
| C22 | h1 then h2, never h3 | `test_publish_order_and_name` PASSED | carried from 3c686ba: `services/core/tests/test_events.py:49` | PASS |
| C23 | raising handler isolated, logged without the message | `test_handler_failure_isolated` PASSED | carried from 3c686ba: `services/core/tests/test_events.py:74`, `:78-82` | PASS |
| C24 | missing / not-JWT / HS256 / none give 401 problem+json, exact detail, 0 syncs | `test_bad_header_rejected` PASSED | re-verified at d7b56f9 (lines above :212 unchanged): `services/core/tests/test_plaid_webhook.py:71-74` (assert_invalid), header loop `:93-103` | PASS |
| C25 | wrong ES256 key gives 401 | `test_wrong_key_rejected` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:111` | PASS |
| C26 | iat 301s gives 401; 299s gives 200 | `test_stale_iat` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:118`, `:120` | PASS |
| C27 | body changed by one byte gives 401 | `test_body_hash_mismatch` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:128` | PASS |
| C28 | expired 1s ago gives 401; null gives 200 | `test_expired_key` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:135`, `:139` | PASS |
| C29 | key fetch failure gives 502 problem+json, 0 syncs | `test_key_fetch_fails` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:150-152` | PASS |
| C30 | same kid fetches once | `test_key_cached` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:161` - `fake.key_calls == [signing.KID]` | PASS |
| C31 | SYNC_UPDATES_AVAILABLE gives 200 ok, rows and cursor stored | `test_sync_updates_available_syncs` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:175`, `:176`, `:183` | PASS |
| C32 | other codes / types / unknown item give 200 ok, 0 syncs | `test_other_webhooks_ignored` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:197-199` | PASS |
| C33 | `[]`, no item_id, item_id 123, JSON string `"not json"` give 422 problem+json, 0 syncs | `test_malformed_body` PASSED | re-verified at d7b56f9: bodies `services/core/tests/test_plaid_webhook.py:204` `b"[]"`, `:205-207` no item_id, `:208-214` `"item_id": 123`, `:216` `b'"not json"'` (case d, now the literal the claim names), `:218` `b'"not json'` (extra, invalid JSON); `:222` - `assert response.status_code == 422, content`; `:223` - `content-type == "application/problem+json"`; `:224` - `fake.cursors == []` | PASS |
| C34 | every other /v1 route gives 401; the only public one is the webhook | `test_every_v1_route_requires_token` PASSED, `test_only_public_v1_route` PASSED | carried from 3c686ba: `services/core/tests/test_auth.py:206`; re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:243` - `assert public == [("post", URL)]` | PASS |
| C35 | background sync failure still 200 ok; sync_failed with 4 fields | `test_background_sync_failure_logged` PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:260-261` - `== 200`, `{"status": "ok"}`; `:264-268` - `len(failed) == 1`, `connection_id`, `error_type == "ITEM_ERROR"`, `error_code == "ITEM_LOGIN_REQUIRED"`, `request_id == "r-7"` | PASS |
| C36 | connect gives 201; rows and cursor stored | `test_connect_starts_sync` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:834`, `:836`, `:843` | PASS |
| C37 | failed first sync still 201, accounts stored, one sync_failed | `test_connect_sync_failure` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:864-871` | PASS |
| C38 | URL set gives that URL; unset or empty gives None; real client sends webhook only when not None | `test_plaid_webhook.py::test_link_token_webhook` x3 (`[url-url]`, `[None-None]`, `[-None]`), `test_plaid_client.py::test_link_token_webhook` x2 PASSED | re-verified at d7b56f9: `services/core/tests/test_plaid_webhook.py:295-296` - unset case `monkeypatch.delenv("PLAID_WEBHOOK_URL")` and `monkeypatch.setitem(Settings.model_config, "env_file", None)`; `:298` - set case `monkeypatch.setenv(...)`; `:308` - `assert fake.link_requests[-1].webhook == url`; `services/core/tests/conftest.py:29` - `os.environ["PLAID_WEBHOOK_URL"] = ""`; carried from 3c686ba: `services/core/tests/test_plaid_client.py:171` - `request.get("webhook") == webhook` | PASS |
| C39 | real sandbox: every amount_cents = -to_cents(Plaid amount); at least 1 positive and 1 negative | `bash proofs.sh c39` - `1 passed ... in 23.87s`, `PASS c39` (the file's only test, `test_sandbox_sync_signs_amounts_and_repeats_cleanly`) | verified at d7b56f9: `services/core/tests/test_transaction_sync_sandbox.py:47` - the key guard `plaid_client_id != "test-client-id"` passed, so real keys were used; `:102` - `assert set(stored) == set(plaid_amounts)`; `:104` - `assert cents == -(service.to_cents(plaid_amounts[transaction_id]) or 0)`; `:107` - `any(cents > 0 ...)`; `:108` - `any(cents < 0 ...)` | PASS |
| C40 | real sandbox: a second sync changes no row and publishes no event | same run as C39, PASSED | verified at d7b56f9: `services/core/tests/test_transaction_sync_sandbox.py:118` - `assert not again.changed`; `:119` - `assert seen == []` (subscribed to `transactions.synced` at `:113`); `:120` - `assert snapshot(business_id) == before` | PASS |
| C41 | no secrets or transaction values in logs; synced line has counts | `test_no_secrets_logged` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:929`, `:916` | PASS |
| C42 | A's sync writes nothing for B; each business's rows carry its own ID | `test_tenancy` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:941`, `:946`, `:948` | PASS |
| C43 | repository functions take keyword business_id; only unscoped connection query is connection_for_item | `test_repository_requires_business` PASSED | carried from 3c686ba: `services/core/tests/test_transaction_sync.py:967`, `:972` | PASS |
| C44 | schema after upgrade; downgrade drops both; check clean | `test_bank_transactions_upgrade_downgrade_and_check` PASSED | carried from 3c686ba: `services/core/tests/test_migrations.py:504-531`, `:541-542`, `:546` | PASS |
| C45 | real client: request shape, mapping, mutation error, JWK dict | 3 tests PASSED | carried from 3c686ba: `services/core/tests/test_plaid_client.py:234-237`, `:241`, `:310`, `:333-335` | PASS |
| C46 | generated files regenerate with no diff and carry the route | `bash proofs.sh c46` - `PASS c46`; `git status --porcelain` empty afterwards | verified at d7b56f9: `.specs/features/14-bank-transaction-sync/proofs.sh:27` - `git diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts`; `:29`, `:31` - route grep | PASS |
| C47 | every AGENTS.md check passes | `bash proofs.sh c47` - ruff format (59 files already formatted), ruff check (All checks passed), mypy (no issues, 27 files), pytest 334 passed / 3 deselected; vitest 25 files / 185 tests passed; next build compiled; `PASS c47` | verified at d7b56f9: `.specs/features/14-bank-transaction-sync/proofs.sh:37-40` | PASS |

### C38 re-check against d7b56f9

Verified at d7b56f9.

- **Set:** `monkeypatch.setenv("PLAID_WEBHOOK_URL", "https://example.test/v1/webhooks/plaid")` (`test_plaid_webhook.py:298`). Process env takes priority over `env_file` in pydantic-settings, so the developer's file cannot override this value. `:308` asserts the fake recorded exactly that URL.
- **Unset:** `:295` removes the process variable, including conftest's forced `""`, and `:296` sets `Settings.model_config["env_file"]` to `None`, so `.env.local` is not read. `get_settings.cache_clear()` (`:299`) makes the next request build a new `Settings`. `monkeypatch.undo()` (`:304`) restores both. `:308` asserts `None`.
- **Shown on this machine.** `services/core/.env.local` has a non-empty `PLAID_WEBHOOK_URL` (57 characters; the value was not printed). Read-only, from `services/core`: with the process variable removed and the default `env_file`, `Settings().plaid_webhook_url is None` is **False**, so the file's URL would leak into the "unset" case. With `env_file` set to `None` and the other settings supplied through the environment, it is **True**. The `[None-None]` case passed on this machine with that file in place. Before `d7b56f9`, the same case would have seen the file's URL, so the test now proves a truly unset value.
- **Empty:** the `("", None)` case (`:283`) still exercises the `empty_webhook_url_is_unset` validator (`services/core/app/settings.py:41-47`).
- **Real client half:** `test_plaid_client.py:171` is unchanged. The conftest line (`conftest.py:29`) assigns unconditionally, so it also overrides the URL that `proofs.sh c39` exports from `.env.local`. The sandbox test does not create link tokens, so C39 and C40 are unaffected.

### C33 precision gap (round 1): closed

Verified at d7b56f9. Case (d) now sends `b'"not json"'` (`test_plaid_webhook.py:216`). That is valid JSON that decodes to a string, not an object, which is exactly the claim's literal. The 422 assertion sits in the loop at `:222`, with `content` as the failure label, so each body is asserted on its own. The earlier invalid-JSON body is kept as an extra case (`:218`).

### Precision and level observations (not failing)

These are carried from 3c686ba, and each still holds at d7b56f9. No application file changed in `3c686ba..d7b56f9`.

- C43: the proof reads the source text. It checks for a keyword-only `business_id` parameter and does not check that the query filters on it. Every current repository function does filter. A function that takes the parameter and ignores it would still pass.
- C34: it sorts routes by the Clerk `detail` string, so it depends on that copy staying the same. That is acceptable, and the Handoff records it.
- C40: the "second sync" is the one that follows the wait-for-ready loop (`test_transaction_sync_sandbox.py:81-87`). That loop breaks only after a sync that reports no change, so C40 asserts that the settled state stays settled. This matches the claim.
- C39 and C40 are one test in one `-q` run. "1 passed" names no test, but `tests/test_transaction_sync_sandbox.py` contains exactly one test function (`:44`), and the marker filter (`-m plaid_sandbox`, `pyproject.toml:42-43`) selects it.
- Level and sampling: unchanged from round 1. There are no level or sampling gaps. C33 now exercises all 4 listed cases plus 1 extra.

### Code against Landing doors and AGENTS.md (observations)

These are carried from 3c686ba, and both still hold at d7b56f9 (`service.py` is unchanged).

- Minor, outside any check: `sync_in_background` (`services/core/app/modules/bank_sync/service.py:603`) catches only `PlaidError` (`:616`). A database error, such as an `IntegrityError` whose message carries bound transaction values, would escape to the server error log or Sentry. This is a follow-up, not a check failure.
- Minor: `plaid.webhook_unknown_item` logs `plaid_item_id`, which is an identifier and not a secret.

## Coverage

Carried from 3c686ba, with the rows the fixes affect re-verified at d7b56f9. Profile `light`: the author's table is read, not recomputed.

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| webhook statuses (4) | author's table (read) | 200 C26/C28/C31/C32/C35 · 401 C24-C28 · 422 C33 · 502 C29 | - |
| one-way doors (8) | author's table (read) | door 1 C12/C44 · 2 C10/C44 · 3 C22/C23 · 4 C20 · 5 C45/C17 · 6 C34 · 7 C24-C30/C45 · 8 C38 | - |
| entities (2) | author's table (read) | C44, C10 | - |
| Plaid change kinds (3) | author's table (read) | C1/C12, C13, C14/C15 | - |
| transaction fields (9) | author's table (read) | C2-C7, C42 | - |
| counterparty sources (3) | author's table (read) | C6 x3 | - |
| balance fields (2) | author's table (read) | C9 | - |
| sync failure kinds (4) | author's table (read) | C4, C18 x2, C35/C37 | - |
| signature rejections (7) | author's table (read) | C24 x3, C25, C26, C27, C28 | - |
| webhook dispatch (4) | author's table (read) | C31, C32 x3 | - |
| sync triggers (3) | author's table (read) | C36, C31, C1 | - |
| event outcomes (3) - verified at d7b56f9 | author's table (read) | C20 x2, C11, C40 (now run) | - |
| startup config PLAID_WEBHOOK_URL (2) - verified at d7b56f9 | author's table (read) | C38 fake (set / truly unset / empty) + real client | - |
| startup config public router (2) | author's table (read) | `services/core/app/main.py` `APIRouter(prefix="/v1/webhooks")`; C34, C31 | - |
| spec "Done when" items (4) - verified at d7b56f9 | `context/specs/14-bank-transaction-sync.md` | 1 C11, C40 · 2 C14/C16 · 3 C39 · 4 C24-C28 | - |

## Swept

Carried from 3c686ba. There are no Swept rows that resolve to "existing". The plan's one "existing" decision (`/v1` versioning) holds: the route is `/v1/webhooks/plaid`.

## Faults injected

None: fault injection does not run at profile `light`.

## Gate

Verified at d7b56f9.

- Targeted batch (C1-C45 except C39/C40): `uv run pytest ... -v -p no:logging -k "<all selectors>"` - 58 passed, 0 failed, 45 deselected
- `bash .specs/features/14-bank-transaction-sync/proofs.sh c39 c46 c47` - exit 0
  - c39: 1 passed, 0 failed, run with the real sandbox keys
  - c46: PASS
  - c47: API 334 passed / 0 failed / 3 deselected; web 185 passed / 0 failed; build OK
- Real tree `git status --porcelain` was empty before and after

## Ranked gaps

None that fail the feature. Non-failing follow-ups:

1. Precision: C43 checks the parameter signature through the source text, not the query filter. See `services/core/tests/test_transaction_sync.py:952-972`.
2. Observation: `sync_in_background` lets exceptions other than `PlaidError` escape. A SQLAlchemy `IntegrityError` message there could carry transaction values into error logs. See `services/core/app/modules/bank_sync/service.py:603-616`.
