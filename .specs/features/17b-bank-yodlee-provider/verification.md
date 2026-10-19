# Yodlee as a second bank provider - verification report

**Verdict**: PASS
**Profile**: light
**Diff range**: ac281ac^..de55fc2 (HEAD); fix diff cde4be0..de55fc2 (c427ff8 code and tests, de55fc2 C4 wording)
**Round**: 3 - scoped
**Verifier**: independent sub-agent (author != verifier)

All 49 checks are proven at `de55fc2`, and every proof is green. The two round-2 failures are now PASS:

- **C4**: under its new wording, the second proof prints exactly the two route-count lines from `test_security_rules.py` and nothing else.
- **C18**: a new test captures real Sentry events through a fake transport after a stray 500. It asserts that the access token, the client secret, the admin login name and the business login name are absent from both the logs and the events.

N1 is fixed on every path round 2 named. That covers the same business through the institution check, another business on the shared sandbox user, and a retried request. A narrow residual window is recorded below as low.

Gap 8 is closed by the user's decision. With Yodlee off, a disconnect deletes the local rows and logs `bank_connection.orphaned`.

## Binding sources

carried from f25367b. No source is marked binding. The profile is `light`, so step 1 does not run, and the fix did not touch the interface.

## Checks

verified at de55fc2. Every proof was re-run at HEAD.

- **API, one batched call** (from `services/core`). The command was `uv run python -m pytest tests/test_bank_yodlee_migration.py tests/test_bank_connect_yodlee.py tests/test_yodlee_client.py tests/test_bank_sync_yodlee.py tests/test_log.py ../../.specs/features/34-launch-production/test_check_no_shared_credentials.py tests/test_bank_connect.py tests/test_bank_accounts.py tests/test_bank_connection_nightly.py tests/test_bank_connection_settings.py tests/test_plaid_webhook.py tests/test_plaid_item_webhooks.py tests/test_plaid_client.py -rA -p no:cacheprovider -k "<every proof name in checks.md, the round-2/3 tests, and the 7 C4 module names>"`.
  - Result: 230 passed, 0 failed, 35 deselected, exit 0, in 33.9 s.
  - The 230 split into 157 from the 7 C4 proof-1 files and 73 feature proofs.
  - Each test cited below printed `PASSED` individually. A per-name `grep -c "^PASSED.*<name>"` found at least one hit for every name, and no filter term matched zero tests.
- **C4 proof 2:** `git diff ac281ac^..HEAD -- services/core/tests | grep -E "^-\s+assert"` printed exactly `-    assert len(routes) == 28` and `-    assert len(routes) == 35`. Both sit under the `+++ b/services/core/tests/test_security_rules.py` header, and no other file has a removed assertion.
- **Web, one batched call** (from `frontend`): `npx vitest run tests/connect-bank.test.tsx tests/yodlee-connect.test.tsx tests/bank-settings-page.test.tsx tests/security-headers.test.ts tests/connect-yodlee-bank-action.test.ts -t "yodlee action|loading|error and retry|success posts provider account|sends the yodlee provider|close returns to start|copy from messages|yodlee reconnect|csp allows yodlee" --reporter=verbose` gave 10 passed, 25 skipped, 5 files. Each cited test printed `✓`.
- **C44:** `npx playwright test e2e/bank-yodlee.spec.ts --project=chromium --reporter=line` gave 3 passed in 16.9 s. The API on :8100 answered `{"status":"ok"}` on `/healthz/live`.

Citations in `tests/test_bank_connect_yodlee.py` and `tests/test_bank_sync_yodlee.py` were refreshed, because the fix added imports at the top of both. The other cited files (`test_yodlee_client.py`, `test_log.py`, `test_bank_yodlee_migration.py`, the spec 34 test and all frontend tests) are untouched by `cde4be0..HEAD`, so their citations carry from cde4be0.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | check accepts plaid, yodlee; rejects other | `test_provider_check_accepts_yodlee` PASSED | `tests/test_bank_yodlee_migration.py:21-24` - inserts plaid and yodlee, then `pytest.raises(IntegrityError, match="ck_bank_connections_provider")` for `provider="other"` | PASS |
| C2 | downgrade fails with a yodlee row, deletes nothing | `test_downgrade_refuses_with_yodlee_rows` PASSED | `tests/test_bank_yodlee_migration.py:31` `pytest.raises(AssertionError, match="ck_bank_connections_provider")`; `:36-41` `count(*) ... provider = 'yodlee'` `== 1` | PASS |
| C3 | downgrade restores `('plaid')` | `test_downgrade_restores_plaid_only` PASSED | `tests/test_bank_yodlee_migration.py:48-51` - after the downgrade, a yodlee insert raises `(IntegrityError, InternalError, ProgrammingError)` | PASS |
| C4 | Plaid suites pass; no assertion weakened or removed; the only edited assertions are the two route-count tripwires | proof 1: the 7 files, 157 PASSED inside the batched call. Proof 2: `git diff ac281ac^..HEAD -- services/core/tests` piped to `grep -E "^-\s+assert"` printed exactly the 2 named lines | proof 2 output: `-    assert len(routes) == 28` and `-    assert len(routes) == 35`, both under `+++ b/services/core/tests/test_security_rules.py`, nothing else. At HEAD they read `services/core/tests/test_security_rules.py:110` `assert len(routes) == 30` and `:147` `assert len(routes) == 37` (one per new route, a strengthening) | PASS |
| C5 | list shows provider per connection | `test_list_shows_provider` PASSED | `tests/test_bank_connect_yodlee.py:106` `sorted(i["provider"] for i in items) == ["plaid", "yodlee"]` (HTTP GET) | PASS |
| C6 | any of the 6 settings unset: providers omits yodlee, fastlink 404 (x6) | `test_off_when_any_setting_unset[...]` 6 params PASSED | `tests/test_bank_connect_yodlee.py:137` `providers.json() == {"providers": ["plaid"]}`; `:138` `launch(owner, business_id).status_code == 404`; parametrized over all 6 settings | PASS |
| C7 | a call over 15 s raises `YodleeError(http_status=None)` | `test_timeout_raises_yodlee_error` PASSED; `test_timeout_is_15_seconds` PASSED | `tests/test_yodlee_client.py:46` `raised.value.http_status is None`; `:187` `seen == [{"connect": 15.0, "read": 15.0, "write": 15.0, "pool": 15.0}]` | PASS |
| C8 | error carries status and code, no body | `test_error_carries_no_body` PASSED | `tests/test_yodlee_client.py:59` `(error.http_status, error.error_code) == (400, "Y301")`; `:60-61` `"SECRET-BODY-TEXT" not in str(error)` / `not in repr(vars(error))` | PASS |
| C9 | DEBIT 25 -> +25.0, CREDIT 25 -> -25.0 | `test_debit_credit_sign` PASSED | `tests/test_yodlee_client.py:94-97` `{...} == {"yodlee:1": 25.0, "yodlee:2": -25.0}` | PASS |
| C10 | only POSTED returned | `test_only_posted` PASSED | `tests/test_yodlee_client.py:110` `[t.transaction_id for t in found] == ["yodlee:1"]` | PASS |
| C11 | stored debit -2500, credit 2500 | `test_stored_amount_sign` PASSED | `tests/test_bank_sync_yodlee.py:159` `{t.description: t.amount_cents for t in transactions(c)} == {"Payment 1": -2500, "Payment 2": 2500}` | PASS |
| C12 | providers 200, `["plaid","yodlee"]` / `["plaid"]` | `test_providers_lists_yodlee` PASSED | `tests/test_bank_connect_yodlee.py:146-147` `status_code == 200`, `== {"providers": ["plaid", "yodlee"]}`; `:151` `== {"providers": ["plaid"]}` | PASS |
| C13 | registers `hr-<hex>` once; 200 with the 4 fields | `test_fastlink_registers_user` PASSED | `tests/test_bank_connect_yodlee.py:163` `== 200`; `:165-176` key set and `(FASTLINK_URL, CONFIG_NAME, 1800)`; `:178` `yodlee.registered == [login_name(business_id)]` | PASS |
| C14 | second call does not register again | `test_fastlink_does_not_register_twice` PASSED | `tests/test_bank_connect_yodlee.py:190` `yodlee.registered == [login_name(business_id)]` | PASS |
| C15 | edit-mode parameters for that provider account | `test_fastlink_edit_mode` PASSED | `tests/test_bank_connect_yodlee.py:203` `response.json()["provider_account_id"] == pa`; `:204` `yodlee.launches[-1] == (login_name(business_id), pa)` | PASS |
| C16 | Plaid connection_id -> 409 | `test_fastlink_plaid_connection_409` PASSED | `tests/test_bank_connect_yodlee.py:215-216` `== 409`, `content-type == "application/problem+json"` | PASS |
| C17 | Yodlee failure -> 503 problem+json, no detail | `test_fastlink_yodlee_failure_503` PASSED | `tests/test_bank_connect_yodlee.py:227-230` `== 503`, problem+json, `detail == PROVIDER_UNAVAILABLE`, `"Y902" not in response.text` | PASS |
| C18 | after a fastlink call, logs and Sentry events hold none of: access token, client secret, admin login name | `test_fastlink_secrets_not_logged` PASSED; `test_no_yodlee_secret_in_logs_or_sentry` PASSED (new); `test_yodlee_secrets_are_redacted` PASSED; `test_yodlee_login_names_are_redacted` PASSED | `tests/test_bank_connect_yodlee.py:665` `assert transport.events, "the stray 500 reports to Sentry"`; `:666` `leaks = [ACCESS_TOKEN, secret, admin, login_name(business_id)]`; `:667` `[v for v in leaks if v in logs] == []`; `:668` `[v for v in leaks if v in events] == []`. The test sets `YODLEE_CLIENT_SECRET` and `YODLEE_ADMIN_LOGIN_NAME` to known values, and it captures real events through `sentry_sdk.init(transport=FakeTransport)` with the app's own `before_send` (`app/monitoring.py:21` `redact(event)`). It runs fastlink, connect, a `YodleeError`, and a stray `RuntimeError`, which yields a 500 that Sentry captures with frame locals. All three round-2 objections are answered: the admin login name is asserted, Sentry is captured and asserted, and the client secret is set, so its assertion now runs. Discrimination note: see "New risks" item 3 | PASS |
| C19 | user token uses the `hr-` loginName, never the admin's | `test_user_token_never_admin` PASSED | `tests/test_yodlee_client.py:126` `logins and set(logins) == {USER}` | PASS |
| C20 | 201; item ID, encrypted loginName, audit entry, first sync | `test_connect_stores_connection` PASSED | `tests/test_bank_connect_yodlee.py:261` `== 201`; `:270` `provider_item_id == pa`; `:272` `decrypt_access_token(...) == login_name(business_id)`; `:277-278` `entry.target_id == str(connection.id)`, `entry.details == {"institution_id": "16441", "account_count": 2}`; `:280-281` `"transactions" in yodlee.calls`, `last_synced_at is not None` | PASS |
| C21 | only checking CAD included, of 4 kinds | `test_connect_includes_checking_cad_only` PASSED | `tests/test_bank_connect_yodlee.py:299` `{r.name: r.included for r in rows} == {"Chequing CAD": True, "Savings CAD": False, "Chequing USD": False, "Visa": False}` | PASS |
| C22 | same institution twice -> 409, no second row | `test_connect_duplicate_409` PASSED | `tests/test_bank_connect_yodlee.py:316` `second.status_code == 409`; `:318` `len(connections) == 1` | PASS |
| C23 | 3 field mismatches -> 422 | `test_connect_field_mismatch_422[...]` 3 params PASSED | `tests/test_bank_connect_yodlee.py:340-341` `== 422`, `stored(business_id) == ([], [])` | PASS |
| C24 | no accounts -> nothing stored, deleted at Yodlee, 503 | `test_connect_failure_cleans_up` PASSED | `tests/test_bank_connect_yodlee.py:353-355` `== 503`, `stored(...) == ([], [])`, `yodlee.deleted == [(login_name(business_id), pa)]` | PASS |
| C25 | ID 123 -> `yodlee:123` | `test_transaction_id_prefixed` PASSED | `tests/test_bank_sync_yodlee.py:246` `[t.provider_transaction_id for t in transactions(c)] == ["yodlee:123"]` | PASS |
| C26 | 3 POSTED -> 3 rows, one event added=3 | `test_sync_upserts_and_publishes` PASSED | `tests/test_bank_sync_yodlee.py:258-260` `result.added == 3`, `len(transactions(c)) == 3`, `[e.payload["added"] for e in seen] == [3]` | PASS |
| C27 | second sync 0/0/0, no event | `test_sync_twice_changes_nothing` PASSED | `tests/test_bank_sync_yodlee.py:273` `(0, 0, 0)`; `:275` `len(seen) == published` | PASS |
| C28 | 730 days, then 90 | `test_sync_window_first_and_later` PASSED | `tests/test_bank_sync_yodlee.py:284` `fake.transaction_from_dates == [NOW.date() - 730d, (NOW+1h).date() - 90d]` | PASS |
| C29 | `last_synced_at` = min(now, refresh) | `test_last_synced_at_is_earlier_of` PASSED | `tests/test_bank_sync_yodlee.py:295` `== NOW - timedelta(hours=10)`; `:299` `== NOW + timedelta(minutes=1)` | PASS |
| C30 | needs login -> `login_required` | `test_login_required_status` PASSED | `tests/test_bank_sync_yodlee.py:309` `login_required is True`; `:312` `view.status == "login_required"` | PASS |
| C31 | nightly syncs, retries after 1 h, fourth failure ends the night | `test_nightly_syncs_due_yodlee`, `test_nightly_syncs_due_yodlee_retries_then_ends_night` PASSED | `tests/test_bank_sync_yodlee.py:358` `dict(summary[JOB])["synced"] == 1`; `:374` `next_nightly_attempt_at == utc(2026, 10, 6, 7)`; `:381` `failed_nights == 1` | PASS |
| C32 | a failure mid-sync changes nothing | `test_sync_failure_rolls_back` PASSED | `tests/test_bank_sync_yodlee.py:330-332` `transactions(c) == []`, `balance(c) == 10000`, `last_synced_at is None` | PASS |
| C33 | delete at Yodlee first, then locally | `test_disconnect_deletes_remote_first` PASSED | `tests/test_bank_sync_yodlee.py:413-414` `still_stored_at_delete == [True]`, `fake.deleted == [(LOGIN, c.provider_account_id)]` | PASS |
| C34 | a failed delete makes the route return 503 and keeps the rows | `test_disconnect_remote_failure` PASSED; `test_repair_and_disconnect_over_http` PASSED | `tests/test_bank_connect_yodlee.py:564-566` `failed.status_code == 503`, problem+json, `len(stored(business_id)[0]) == 1` (HTTP DELETE); `tests/test_bank_sync_yodlee.py:437-439` row, balance and transaction kept | PASS |
| C35 | provider account not found -> disconnect succeeds | `test_disconnect_remote_not_found` PASSED | `tests/test_bank_sync_yodlee.py:470` `not any(method == "DELETE" for method, _ in sent)`; `:472` `session.get(BankConnection, ...) is None` | PASS |
| C36 | link-token for Yodlee -> 409 | `test_link_token_409` PASSED | `tests/test_bank_connect_yodlee.py:369-370` `== 409`, `detail == "Use the Yodlee window to reconnect this bank."` | PASS |
| C37 | Yodlee action shown only when offered | vitest `yodlee action shows only where the API offers Yodlee` ✓ | `frontend/tests/connect-bank.test.tsx:137-138` one button, no `yodleeConnect`; `:142` `[BANK.connect, BANK.yodleeConnect]` | PASS |
| C38 | disabled and announced loading while opening | vitest `loading` ✓ | `frontend/tests/yodlee-connect.test.tsx:63-65` `textContent == BANK.yodleeOpening`, `disabled == true`, `aria-busy == 'true'` | PASS |
| C39 | route failure: en.json error, then retry | vitest `error and retry` ✓ | `frontend/tests/yodlee-connect.test.tsx:74-75` `alert().textContent == BANK.errors.launchFailed`; `:79-81` second launch opens FastLink | PASS |
| C40 | onSuccess 42 -> connect action with `provider = yodlee`, `provider_account_id = "42"` | vitest `success posts provider account` ✓; `sends the yodlee provider and the provider account, then redirects` ✓ | `frontend/tests/yodlee-connect.test.tsx:98` `expect(connectYodleeBank).toHaveBeenCalledWith(BUSINESS, '42')`; `frontend/tests/connect-yodlee-bank-action.test.ts:42-46` `api.POST` called with `body: { provider: 'yodlee', provider_account_id: '4242' }` | PASS |
| C41 | close -> initial state, no connect | vitest `close returns to start` ✓ | `frontend/tests/yodlee-connect.test.tsx:110` `connectYodleeBank` not called; `:111-114` container gone, enabled, label `yodleeConnect` | PASS |
| C42 | new strings come from en.json | vitest `copy from messages` ✓ | `frontend/tests/yodlee-connect.test.tsx:120-122` `yodleeHint`, `yodleeConnect`, `yodleeProvider` | PASS |
| C43 | settings reconnect: FastLink edit mode, then repair | vitest `yodlee reconnect opens fastlink in edit mode, then repairs` ✓ | `frontend/tests/bank-settings-page.test.tsx:413` `launchFastLink` with `(BUSINESS, rbc.id)`; `:415` `{ configName, flow: 'edit', providerAccountId: 4242 }`; `:418` `repairConnection` with `(BUSINESS, rbc.id)` | PASS |
| C44 | 375 px, axe clean, 44 px controls, keyboard alone | Playwright `e2e/bank-yodlee.spec.ts` chromium: 3 passed (16.9 s) | `frontend/e2e/bank-yodlee.spec.ts:16` `scrollWidth <= 375`; `:19` `box.height >= 44`; `:22` `axe.violations == []`; `:25-27` `tabTo` + Enter, then `#container-fastlink` visible | PASS |
| C45 | CSP script-src and frame-src allow Yodlee | vitest `csp allows yodlee's fastlink script and frame` ✓ | `frontend/tests/security-headers.test.ts:37-38` `toContain("script-src 'self' https://cdn.yodlee.com")`, `toContain("frame-src 'self' https://*.yodlee.com")` | PASS |
| C46 | another business -> 404 on 3 routes | `test_other_business_denied[...]` 3 PASSED | `tests/test_bank_connect_yodlee.py:403-404` `== 404`, `yodlee.calls == []` | PASS |
| C47 | non-owner -> 403 on 3 routes | `test_non_owner_denied[...]` 3 PASSED | `tests/test_bank_connect_yodlee.py:417-418` `== 403`, `yodlee.calls == []` | PASS |
| C48 | unknown business -> 404 on 3 routes | `test_unknown_business_404[...]` 3 PASSED | `tests/test_bank_connect_yodlee.py:430-431` `== 404`, `yodlee.calls == []` | PASS |
| C49 | deploy check fails on a shared Yodlee ID or secret, prints no value | `test_shared_yodlee_credential_fails[...]` 3 PASSED, `test_yodlee_config_name_may_match` PASSED | `.specs/features/34-launch-production/test_check_no_shared_credentials.py:153` `code == 1`; `:155` `"yodlee-same-value-7" not in output` | PASS |

Named tests confirmed: every cited name appears as `PASSED` (pytest `-rA`) or `✓` (vitest verbose) in this round's output.

## Coverage

verified at de55fc2 for the rows the fix touched: connect statuses, secrets, parse paths and the Yodlee-off disconnect. The other rows (`YODLEE_*` settings, entities, account kinds, field combinations, client assemblies, roles) are carried from f25367b. The profile is `light`, so this join is optional. It is recomputed because the earlier gaps lived here.

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| `GET .../bank/providers` statuses (3) | plan Surface | 200 C12 · 403 C47 · 404 C46, C48 | - |
| `POST .../yodlee/fastlink` statuses (5) | plan Surface; `api.py` `create_fastlink` | 200 C13 · 403 C47 · 404 business C46/C48 · 404 not configured C6 · 404 another business's `connection_id` `tests/test_bank_connect_yodlee.py:449-450` · 409 C16 · 503 C17 | - |
| `POST .../bank/connections` statuses and causes | plan Surface; `service.connect_yodlee_bank` | 201 C20 · 403 C47 · 404 C46/C48 · 404 Yodlee off `tests/test_bank_connect_yodlee.py:605-606` (new) · 409 institution C22 · 409 same provider account `:476-478` · 409 race through the institution check, nothing deleted `:503-504` (now reaches the real `has_institution`) · 409 another business's provider account `:521-523` · 409 shared sandbox user through the institution check, nothing deleted `:593-594` (new) · 422 C23 · 503 no accounts C24 · 503 Yodlee failure `:461-464` | - |
| changed routes `.../repair` and `DELETE .../connections/{id}` for Yodlee | code `api.py` | repair 200 `tests/test_bank_connect_yodlee.py:554-555` · repair 409 `:559` · delete 503 `:564-566` · delete 204 `:570-571` | - |
| `disconnect_bank` Yodlee branches (3) | code `service.py:1436-1449` | Yodlee on, deleted first C33 · not found C35 · Yodlee off, local delete plus `bank_connection.orphaned` log `tests/test_bank_sync_yodlee.py:492-496` (new, service level; the route passes the same `None` dependency) | - |
| one-way doors (8, including 2a) | plan Landing | 1 C1, C3 · 2 C13, C20 · 2a `tests/test_bank_connect_yodlee.py:540-543` · 3 C7, C8 · 4 C26, C31 · 5 C25 · 6 C29 · 7 C13, C18 | - |
| secrets named by AC 15 (3) and destinations (logs, Sentry) | AC 15 | access token, client secret and admin login name, in both logs and Sentry: `tests/test_bank_connect_yodlee.py:665-668`; plus the key redaction `tests/test_log.py:189-190,202-206` | - |
| malformed-answer parse paths in `yodlee.py` | code | `accounts` `tests/test_yodlee_client.py:207` · transaction date `:218` · `institution_name` and the page count are now inside `_parsing()` (`yodlee.py:333-341`, `:376-380`; no test of their own, low) · `_token` and `provider_account` check `isinstance` before indexing (`yodlee.py:253-256`, `:309-311`) | - |

### Swept rows that say `existing`

carried from f25367b. The sync concurrency constraints are in the code (`repository.py:128,159,309`). Connect still takes no lock. Its race now resolves through the unique index, the institution check and `_is_ours_to_delete`, and the one narrow residual is in "New risks" item 1.

## Faults injected and test policy rows

Neither step ran, because the profile is `light`.

## Round-2 findings, re-judged at de55fc2

1. **C18: fixed.** See the row above.
2. **N1: fixed on every named path.**
   - The cleanup now runs only when `_is_ours_to_delete` returns true (`app/modules/bank_sync/service.py:487-507`, used at `:584`). It returns false in three cases:
     - for `_ProviderAccountStoredError`;
     - whenever `YODLEE_TEST_LOGIN_NAME` is set;
     - when this business already stores the provider account (`repository.has_provider_item`, read after the rollback).
   - **Same business, racing connect:** once the first connect commits, the second reaches `has_institution`, which raises `DuplicateBankError`. The re-query after the rollback opens a new transaction, which at READ COMMITTED sees the committed row, so nothing is deleted. Proof: `tests/test_bank_connect_yodlee.py:503-504`. Unlike round 2, the test now misses only the pre-check (`miss_once`, `:491-499`) and lets the real `has_institution` and index run.
   - **Another business on the shared sandbox user:** never deletes. Proof: `:593-594`.
   - **Retried request after success:** the pre-check raises `_ProviderAccountStoredError` before the `try` (`service.py:526-532`), so nothing is deleted. Proof: `:476-478`.
   - **Another business in production:** the provider account belongs to a different Yodlee user, so the calls made with this business's loginName fail. The cleanup's delete is then refused, so another user's account cannot be deleted.
3. **Gap 8: closed by user decision.**
   - `disconnect_bank` with `yodlee is None` now logs `bank_connection.orphaned` (`service.py:1438-1444`) and deletes the local rows. Proof: `tests/test_bank_sync_yodlee.py:492-496`.
   - Out of scope, as briefed: while Yodlee is off, the nightly job still fails each Yodlee connection every night.
   - The decision is in the commit message of c427ff8 but not yet in `.specs/STATE.md`'s decision log (low).
4. **C4: fixed by the approved rewording** (de55fc2). Proof 2 matches the new text exactly.
5. **Low items from round 2:**
   - Connect 404 when Yodlee is off now has a test: `tests/test_bank_connect_yodlee.py:605-606`.
   - `institution_name` and the page count are now inside `_parsing()` (`yodlee.py:333-341`, `:376-380`). They have no malformed-answer test of their own.
   - The Proof lines of C7, C34, C40 and now C18 in `checks.md` still name only the original tests. The evidence lives in `test_timeout_is_15_seconds`, `test_repair_and_disconnect_over_http`, `connect-yodlee-bank-action.test.ts` and `test_no_yodlee_secret_in_logs_or_sentry` (precision, low).

## New risks from the fix diff (`git diff cde4be0..HEAD -- services/core/app`)

1. **Residual race window (low).** Two connects of one provider account for one business can both be in flight with neither committed. If the second then fails for another reason, for example a Yodlee timeout in `accounts()`, `has_provider_item` still sees nothing (`service.py:502-507`), so it deletes the provider account the first connect is about to store. The first may then commit a connection whose provider account is gone, and the next sync answers not-found or `login_required`. This takes a double submit plus a transient Yodlee failure in the overlap. No check claims it.
2. **Re-query inside `except` (low).**
   - The `has_provider_item` call after `session.rollback()` behaves normally: SQLAlchemy autobegins a new transaction, and the request's session is closed afterwards.
   - The exception is a lost database connection (`OperationalError`). There the re-query itself raises, which replaces the original exception (chained as `__context__`). The cleanup is skipped with no `bank_connection.orphaned` log, so a new provider account can be left at Yodlee silently. The route answers 500 in either case.
   - `get_settings()` in the service is the cached settings, the same one `login_name_for` reads. Tests that change `YODLEE_TEST_LOGIN_NAME` call `get_settings.cache_clear()` (`tests/test_bank_connect_yodlee.py:583`), and the `yodlee` fixture depends on `no_test_login`. No test ordering issue was observed.
3. **C18 discrimination (low, would need fault injection to settle).**
   - In the new test, the business login name and the access token travel through frames the stray 500 serializes: service and fake locals named `login_name`. Removing the key redaction would make `:668` fail, so that half of the assertion discriminates.
   - The client secret and admin login name live only in `Settings` and in `HttpxYodleeClient`. The API test replaces the client with `FakeYodlee`, so neither value enters a captured frame, and `:667-668` would stay green even if the real client leaked them.
   - On the real-client path, the secret travels as `data={"secret": ...}` and the login as the `loginName` header (`yodlee.py:213-216,247-251`). Both keys match `SECRET_KEY_FRAGMENTS` (`app/log.py:13,23-24`), and `tests/test_log.py:189,202-206` proves that redaction.
   - One theoretical path remains: a frame holding a `Settings` local, in `HttpxYodleeClient.__init__` (`yodlee.py:195-198`) or `get_yodlee_client` (`:408-409`). Pydantic's repr would print `yodlee_client_secret` in plain text if a stray exception surfaced there. It is not reachable in normal operation.
4. **Sandbox trade-off (low).** With `YODLEE_TEST_LOGIN_NAME` set, a failed connect never deletes the provider account, even a genuinely new one, and logs nothing. Sandbox and staging may collect stray provider accounts on the shared test user. C24 runs without the test login, so it is unaffected. This is a documented trade-off (docstring `service.py:493-496`).
5. **Scope:** the four touched files (`service.py`, `yodlee.py`, two test files) and `checks.md` are within the plan's scope.

## Ranked remaining gaps

None blocks the verdict. In order of risk:

1. Residual race window: concurrent uncommitted connects where the second fails on a Yodlee error. `services/core/app/modules/bank_sync/service.py:502-507,582-587`.
2. C18 discrimination: the client secret and admin login never enter the faked stack. `services/core/tests/test_bank_connect_yodlee.py:667-668`. The real-client redaction is proven only at key level, in `services/core/tests/test_log.py:189,202-206`.
3. The re-query in the `except` can mask a database-loss error and skip the orphaned log. `services/core/app/modules/bank_sync/service.py:502-507`.
4. The Yodlee-off nightly job fails every night (out of scope). The Yodlee-off disconnect decision is not in `.specs/STATE.md`.
5. The Proof lines of C7, C18, C34 and C40 in `checks.md` do not name the tests that carry their evidence.

## Gate

verified at de55fc2:

- `uv run python -m pytest <6 feature proof files + 7 C4 files> -rA -p no:cacheprovider -k "<proof names + 7 C4 module names>"` (services/core): 230 passed, 0 failed, 35 deselected (157 of them C4 proof 1)
- `git diff ac281ac^..HEAD -- services/core/tests | grep -E "^-\s+assert"` (C4 proof 2): exactly the 2 expected lines, both in `test_security_rules.py`
- `npx vitest run tests/connect-bank.test.tsx tests/yodlee-connect.test.tsx tests/bank-settings-page.test.tsx tests/security-headers.test.ts tests/connect-yodlee-bank-action.test.ts -t "<alternation>" --reporter=verbose` (frontend): 10 passed, 0 failed, 25 skipped
- `npx playwright test e2e/bank-yodlee.spec.ts --project=chromium --reporter=line` (frontend): 3 passed, 0 failed
- `uv run python -m pytest` (services/core, full): not re-run by the Verifier. The parent reports 1197 passed, 5 deselected at c427ff8, the same count as the fix commit's message. de55fc2 changes only `checks.md`. This is a reported result, not an observed one.
- `npx vitest run` (frontend, full): carried from cde4be0 (425 passed). No frontend file changed in cde4be0..HEAD.
