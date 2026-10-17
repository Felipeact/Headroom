# Flinks as a second bank provider verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: d49f5fd..93fb8fbfe329e9f854000d852ac544436cc70837
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

At `93fb8fb`, 35 of 37 checks are proven with located evidence. 2 are BLOCKED: C32, and the Flinks-on half of C37. None FAIL. Both blocked rows wait on open question 1, the missing Flinks sandbox credentials. `services/core/.env.local` holds no `FLINKS_*` value, and real Flinks was not called. A BLOCKED row is not a PASS, so the verdict is FAIL.

Round 1 found F1, F2, F4, G2, G3 and G4. All six are fixed and proven. F3 is recorded as an accepted plan-level item, because it matches AC 28 as approved. One new Low residual, F5, is a Sentry frame local that the redactor still misses. It is outside every check.

What this round re-ran and re-read:

- **Proofs:** every proof was re-run in full at `93fb8fb`.
- **Citations:** the citations in the files the fix touched were refreshed. Those files are `services/core/app/log.py`, `services/core/app/modules/bank_sync/flinks.py`, `services/core/tests/test_flinks_client.py`, `frontend/e2e/bank-connect.spec.ts` and `frontend/tests/choose-accounts.test.tsx`.
- **Carried forward:** everything else is carried from `0490b60` and marked as such. The fix diff (`git diff 0490b60..93fb8fb`) touches no model, migration, route, `service.py`, `api.py` or component source.

## Checks

*Proof runs verified at `93fb8fb`. A cited line in a file the fix did not touch is carried from `0490b60`. In `test_flinks_client.py`, `bank-connect.spec.ts` and `choose-accounts.test.tsx` the fix only appended (hunks at `:266`, `:79` and `:322`), so the earlier cited lines there still hold. Each was re-read.*

What was run at HEAD:

- **API:** one pytest call over `test_bank_provider_migration.py`, `test_bank_connect_flinks.py`, `test_flinks_client.py`, `test_bank_sync_flinks.py` and `test_bank_flinks_sandbox.py`. It used the full `-k` alternation of every named proof plus the 3 new round-1 tests and `flinks_connect_url_failure_is_503`, with `-p no:cacheprovider -rA`. Result: **62 passed, 2 deselected**. Every named test showed individually as PASSED.
- **C5 suites, run whole:** **181 passed**.
- **Web:** one `npx vitest run` over 6 files (the 5 from round 1 plus `choose-accounts.test.tsx`), `--reporter=verbose`. Result: **61 passed**.
- **Playwright:** `-g "C43|flinks layout keyboard and axe"`. Result: **3 passed, 1 skipped** (2 setup, C43, and the Flinks test skipped).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | existing rows become `plaid`, columns renamed | `test_existing_rows_become_plaid` PASSED | `services/core/tests/test_bank_provider_migration.py:132` - `assert tuple(row) == ("plaid", "item-1", "ins_1")`; `:148`, `:151-152` (carried from 0490b60) | PASS |
| C2 | downgrade restores `plaid_*`, drops `provider`, rows intact | `test_downgrade_restores_plaid_names` PASSED | `services/core/tests/test_bank_provider_migration.py:162`, `:165`, `:169-178` (carried) | PASS |
| C3 | `other` rejected by `ck_bank_connections_provider` | `test_provider_check_constraint` PASSED | `services/core/tests/test_bank_provider_migration.py:186` - `match="ck_bank_connections_provider"` (carried) | PASS |
| C4 | both uniques; other provider inserts | `test_provider_uniques` PASSED | `services/core/tests/test_bank_provider_migration.py:209`, `:215`; twin at `:201-207` (carried) | PASS |
| C5 | Plaid suites pass with only renames | 8 suites: **181 passed**. The corrected grep `git diff d49f5fd -- services/core/tests \| grep -E "^-\s+assert" \| grep -vE "plaid_(item\|account\|transaction\|institution)_id\|len\(routes\) =="` **printed nothing** (exit 1) | `services/core/tests/test_security_rules.py:110` `== 29`, `:147` `== 36`: the route-count tripwires the corrected proof now excludes (carried) | PASS |
| C6 | list shows `provider` | `test_list_shows_provider` PASSED | `services/core/tests/test_bank_connect_flinks.py:391` (carried) | PASS |
| C7 | sandbox connect URL, query, origin | `test_connect_url[connect_url_sandbox]`, `test_connect_url_sandbox` PASSED | `services/core/tests/test_bank_connect_flinks.py:135-142`, `:152` (carried) | PASS |
| C8 | `acme` instance, no `demo` | `test_connect_url[connect_url_production_has_no_demo]` PASSED | `services/core/tests/test_bank_connect_flinks.py:142` with `demo=None` at `:116` (carried) | PASS |
| C9 | 4 unset settings give 404 problem+json | `test_connect_url_not_configured[x4]` PASSED | `services/core/tests/test_bank_connect_flinks.py:174-175` (carried) | PASS |
| C10 | bookkeeper 403, stranger 404 | `test_connect_url_denied`, `test_flinks_connect_denied` PASSED | `services/core/tests/test_bank_connect_flinks.py:185-190`, `:201-202` (carried) | PASS |
| C11 | 201, sha256 item, decryptable loginId, mask, audit | `test_flinks_connect_stores_connection` PASSED | `services/core/tests/test_bank_connect_flinks.py:220`, `:222`, `:225`, `:233` (carried) | PASS |
| C12 | 5-way `Type` mapping | `test_account_type_mapping[x5]` PASSED | `services/core/tests/test_flinks_client.py:136` - `assert account_type(flinks_type) == ours`, table `:127-131` (re-read at 93fb8fb, unchanged) | PASS |
| C13 | first sync queued once | `test_flinks_connect_queues_first_sync` PASSED | `services/core/tests/test_bank_connect_flinks.py:258-259` (carried) | PASS |
| C14 | `SetScheduledRefresh` body | `test_enable_nightly_refresh_body`, `test_flinks_connect_enables_refresh` PASSED | `services/core/tests/test_flinks_client.py:148` (re-read, unchanged); `services/core/tests/test_bank_connect_flinks.py:268` (carried); sent at `services/core/app/modules/bank_sync/flinks.py:288` (refreshed) | PASS |
| C15 | 5 bad bodies 422; Plaid default 201 | `test_connect_body_validation[x5]`, `..._plaid_default` PASSED | `services/core/tests/test_bank_connect_flinks.py:294`, `:312-313` (carried) | PASS |
| C16 | duplicate institution 409 | `test_flinks_duplicate_institution_is_409` PASSED | `services/core/tests/test_bank_connect_flinks.py:324-326` (carried) | PASS |
| C17 | still preparing 503, nothing stored, no DeleteCard; retry 201 | `test_flinks_connect_still_preparing` PASSED | `services/core/tests/test_bank_connect_flinks.py:336-340`, `:345` (carried) | PASS |
| C18 | 10 s poll, budget 3/30 | `test_async_poll_budget_*` PASSED (3 tests) | `services/core/tests/test_flinks_client.py:177-178` (re-read, unchanged); loop at `services/core/app/modules/bank_sync/flinks.py:265-273` (refreshed) | PASS |
| C19 | `FlinksError(status, code)` only; 503; timeout 15 | `test_errors_carry_only_code`, `..._on_timeout`, `test_timeout_is_15s`, `test_flinks_failure_is_503[x2]` PASSED | `services/core/tests/test_flinks_client.py:196`, `:214`, `:225` (re-read, unchanged); `services/core/tests/test_bank_connect_flinks.py:357` (carried). The new malformed-answer path also maps to `FlinksError(INVALID_RESPONSE)` at `services/core/app/modules/bank_sync/flinks.py:274-281` (refreshed) | PASS |
| C20 | no loginId, AccountNumber or holder in logs/responses | `test_no_secrets_in_logs_or_responses` PASSED, plus the new `test_sentry_event_carries_no_flinks_secrets` PASSED | `services/core/tests/test_bank_connect_flinks.py:435`, `:437` (carried); Sentry: `services/core/tests/test_flinks_client.py:339` `len(events) == 2`, `:341` `'"vars"' in serialized`, `:350` `secret not in serialized` (new at 93fb8fb) | PASS |
| C21 | identity flags false; AccountNumber not kept | `test_accounts_detail_body_excludes_identity` PASSED | `services/core/tests/test_flinks_client.py:236`, `:245` (re-read, unchanged); body literal at `services/core/app/modules/bank_sync/flinks.py:257-263` (refreshed) | PASS |
| C22 | Days365 then Days90 | `test_first_sync_days365_then_days90` PASSED | `services/core/tests/test_bank_sync_flinks.py:147` (carried) | PASS |
| C23 | half-even sign and values | `test_transaction_values_and_sign` PASSED | `services/core/tests/test_bank_sync_flinks.py:172-178` (carried) | PASS |
| C24 | resync 0/0/0; modified 1 | `test_resync_is_idempotent_and_modifies` PASSED | `services/core/tests/test_bank_sync_flinks.py:200-203` (carried) | PASS |
| C25 | absent transaction kept | `test_absent_transaction_is_kept` PASSED | `services/core/tests/test_bank_sync_flinks.py:220-221` (carried) | PASS |
| C26 | `last_synced_at = min(now, LastRefresh)` | `test_last_synced_at_follows_last_refresh[x3]` PASSED | `services/core/tests/test_bank_sync_flinks.py:242` (carried); the parser changed at `services/core/app/modules/bank_sync/flinks.py:116-121` (refreshed), and ISO input still passes all 3 cases | PASS |
| C27 | balances, relabel, one event | `test_balances_relabel_and_event` PASSED | `services/core/tests/test_bank_sync_flinks.py:267-276` (carried) | PASS |
| C28 | nightly via cached Authorize; 1/2/4 h retries | `test_nightly_syncs_flinks`, `test_nightly_flinks_retries`, `test_authorize_cached_body` PASSED | `services/core/tests/test_bank_sync_flinks.py:296-297`, `:312-313` (carried); `services/core/tests/test_flinks_client.py:262` (re-read, unchanged) | PASS |
| C29 | login codes set `login_required` | `test_login_codes_set_login_required[x3]` PASSED | `services/core/tests/test_bank_sync_flinks.py:332`, `:335` (carried) | PASS |
| C30 | DeleteCard 204; failure deletes locally plus orphan log | `test_disconnect_flinks`, `..._when_delete_card_fails` PASSED | `services/core/tests/test_bank_sync_flinks.py:360`, `:384`, `:387-389` (carried) | PASS |
| C31 | Flinks link-token 409 | `test_flinks_link_token_is_409` PASSED | `services/core/tests/test_bank_sync_flinks.py:401-402` (carried) | PASS |
| C32 | sandbox transaction IDs stable | not run: no `FLINKS_*` in `services/core/.env.local`, so real Flinks was not called. `-m flinks_sandbox --co` collects 1 test | `services/core/tests/test_bank_flinks_sandbox.py:83` - `assert first_ids <= {...}` (exists, not executed; carried) | BLOCKED |
| C33 | ConnectBank shows Plaid + Flinks + hint; otherwise Plaid only; non-404 goes to Sentry | `provider choice: with/without Flinks` (connect-bank and choose-accounts) and `connect url loader` x4 PASSED | `frontend/tests/connect-bank.test.tsx:151-152`, `:161`; `frontend/tests/bank-api-flinks.test.ts:50`, `:58` (carried). choose-accounts (new at 93fb8fb): `frontend/tests/choose-accounts.test.tsx:343-344` order Plaid, Flinks, Continue; `:346` no "Connect another bank"; `:348` Plaid opens Link; `:355` no Flinks button without Flinks | PASS |
| C34 | dialog loading, Esc focus, origin, REDIRECT | `dialog loading and focus`, `message origin:` x3 PASSED | `frontend/tests/flinks-connect.test.tsx:62-69`, `:81`, `:91` (carried) | PASS |
| C35 | action body; 503 stillPreparing retry; 409 | `flinks:` x4, `still preparing retry...`, `already connected...` PASSED | `frontend/tests/connect-bank-action.test.ts:102`, `:111`; `frontend/tests/flinks-connect.test.tsx:116`, `:125` (carried) | PASS |
| C36 | "via Plaid/Flinks"; no Reconnect for Flinks | `provider labels, and a Flinks bank needing attention has no Reconnect` PASSED | `frontend/tests/bank-settings-page.test.tsx:402-403`, `:406-407` (carried) | PASS |
| C37 | 375 px, Tab, 44 px, axe, Flinks dialog closed and open | `C43 layout keyboard and axe` PASSED (Flinks off). `flinks layout keyboard and axe` now exists and **skipped**: `Flinks is not configured: spec 17a open question 1` | `frontend/e2e/bank-connect.spec.ts:62`, `:64`, `:67` (Flinks off, re-read). Flinks-on test: `:91` skip guard; `:93`, `:95`, `:98` closed; `:104` and the dialog axe check open; `:107-109` Esc returns focus. Written, but never executed | BLOCKED |

### Level and sampling judgment (carried from 0490b60, one addition)

- The round-1 judgments still hold. The fix touched none of the code they rest on.
- **Added:** C20's Sentry half is proven at the client level. The test runs the app's own `monitoring.init_sentry` with a capturing transport (`services/core/tests/test_flinks_client.py:271-298`), so `_before_send` and `redact` are the real ones. It sends two events with frame locals: an unexpected `RuntimeError` from the transport, and the new `INVALID_RESPONSE`.
  - **The test discriminates.** I injected a fault, without editing the tree: a pytest plugin in the scratchpad reset `app.log.SECRET_KEY_FRAGMENTS` to its pre-fix tuple. The test then **failed** at `services/core/tests/test_flinks_client.py:350` with `AssertionError: <LOGIN_ID>`. Killed.

### Swept rows that say "existing" (carried from 0490b60)

- Authorization (`OwnerDep` at `services/core/app/modules/bank_sync/api.py:74`) and concurrency (lock order, `DuplicateBankError` on the unique) are unchanged by the fix.

## Findings

### Round-1 items, re-judged at 93fb8fb

- **F1 - fixed and proven (one residual, see F5).**
  - **The redactor gained Flinks names.** `services/core/app/log.py:27-34` adds `login_id`, `loginid`, `accountnumber`, `holder`, `username`, `api-key` and `auth-key`. A probe of `redact()` returned `[REDACTED]` for `login_id`, `json.LoginId`, `a.AccountNumber`, `a.Holder`, `headers.x-api-key`, `headers.flinks-auth-key` and `secret`.
  - **A malformed answer is no longer a raw 500.** It becomes `FlinksError(INVALID_RESPONSE)` with `from None` (`services/core/app/modules/bank_sync/flinks.py:274-281`). sentry_sdk's `walk_exception_chain` honours `__suppress_context__` (`.venv/Lib/site-packages/sentry_sdk/utils.py:837`), so the inner `KeyError` frames holding the raw account dict are not sent.
  - **The test settles the claim.**
    - It asserts that two events were captured (`:339`).
    - It asserts that frame `vars` are present (`:341`), so a test that captured no locals could not pass vacuously.
    - It asserts that none of the loginId, auth key, API key, authorize token, account number or holder name appears (`:342-350`).
    - It was fault-injected as above.
  - **Locals swept in the Flinks frames of `flinks.py`, `service.py` and `api.py`.** All are covered: `login_id`, `secret` (`service.py:1041`, `:1471`), `body` (`api.py`), `json` / `LoginId`, `headers`, `query.authorizeToken` (`token`) and `access_token_ciphertext`.
- **F2 - fixed and proven.** `services/core/app/modules/bank_sync/flinks.py:120` normalises a `yyyy/MM/dd` prefix before `fromisoformat`. `test_last_refresh_accepts_slash_dates` PASSED: `services/core/tests/test_flinks_client.py:367` asserts `== "2026-10-15T07:30:00+00:00"`. The ISO form still passes (C26).
- **F3 - accepted plan-level item, not a code defect.** Every connect-time `FlinksError` that is not `OPERATION_PENDING` answers `503 PROVIDER_UNAVAILABLE` (`services/core/app/modules/bank_sync/api.py:202`), and the web shows "still preparing" with a retry. That is the behaviour AC 28 approved. It violates no other rule I found: no secret is exposed, and the retry is idempotent per C17.
- **F4 - fixed and proven.** `services/core/app/modules/bank_sync/flinks.py:156` has no fallback to the name. `test_missing_institution_id_is_not_the_name` PASSED (`services/core/tests/test_flinks_client.py:385`, `institution_id == ""`). The empty ID then hits `NO_INSTITUTION` (`services/core/app/modules/bank_sync/service.py:541`), which answers 503, not a duplicate keyed on a display name.
- **G2 - fixed (the test exists), still BLOCKED (credential).** `frontend/e2e/bank-connect.spec.ts:86-110` covers 375 px, the 44 px targets, axe with the dialog closed and open, Tab and Enter, and Esc returning focus. It skips at `:91` while Flinks is off. It has never run green.
- **G3 - fixed.** The corrected proof prints nothing at `93fb8fb`. The claim is unchanged.
- **G4 - fixed and proven.** `frontend/tests/choose-accounts.test.tsx:327-357` renders `ChooseAccounts` with and without `flinks`. That covers the branch at `frontend/components/onboarding/choose-accounts.tsx:137-147`: the relabel to "Connect with Plaid" and the rendered `FlinksConnect`.

### New residual (adversarial review of the fix)

- **F5 - Low, security: a Sentry frame local in `HttpxFlinksClient._send` still carries the loginId for `DeleteCard`.**
  - **Where:** `delete` passes `path = f"DeleteCard/{login_id}"` (`services/core/app/modules/bank_sync/flinks.py:293`), which becomes the `path` local of `_send` (`:189`).
  - **Why the redactor misses it:**
    - The key `path` is not a secret fragment.
    - `TOKEN_PATTERN`'s lookbehind `(?<=/DeleteCard/)` (`services/core/app/log.py:45`) needs a leading slash that this value lacks.
    - A probe returned `{'path': 'DeleteCard/3f2b1c4e-...'}` unredacted, while the full URL form was redacted.
  - **When it would reach Sentry:** only when a non-`httpx.HTTPError` exception escapes `self._http.request` during a disconnect. `disconnect` catches only `FlinksError` (`services/core/app/modules/bank_sync/service.py:1483`), so Starlette would then report it with frame vars. An `httpx.HTTPError` becomes `FlinksError ... from None` (`flinks.py:199-203`) and is caught. The likelihood is low.
  - **Fix shape:** the pattern `(?<=DeleteCard/)` without the slash, or a `path` value that keeps the slash.
  - **Coverage:** no check covers it, because C20 is about logs and responses, and the new Sentry test exercises `accounts` only.

## Gate

*Verified at `93fb8fb` unless marked as carried.*

- API named proofs: one pytest call, `-k` alternation, `-p no:cacheprovider -rA`. **62 passed, 0 failed, 2 deselected** (the `flinks_sandbox` test among them).
- C5 suites: **181 passed, 0 failed**. C5 corrected grep: **no output**.
- Web vitest: 6 files, **61 passed, 0 failed**.
- Playwright `-g "C43|flinks layout keyboard and axe"`: **3 passed, 1 skipped** (Flinks-on, blocked).
- Fault injection (C20 Sentry): the pre-fix redactor fragments make `test_sentry_event_carries_no_flinks_secrets` fail at `services/core/tests/test_flinks_client.py:350`. Killed.
- `uv run ruff format --check .`: 192 files already formatted. `uv run ruff check .`: all checks passed. `uv run mypy app`: no issues in 75 files.
- `npm run typecheck`: exit 0. `npx eslint` on the two touched web test files: exit 0.
- Model vs migration drift, and the `contracts/openapi.json` regeneration: carried from 0490b60. The fix touched no model, migration or route.

### Ranked gaps (why the verdict is FAIL)

The only gaps holding the verdict at FAIL are credential blockers (open question 1).

1. **G1 - C32 BLOCKED (credential).** `services/core/tests/test_bank_flinks_sandbox.py:83` exists and collects, but is not executed without `FLINKS_*`. Criterion 17's stable-ID assumption is still unproven.
2. **G2 - C37 Flinks-on half BLOCKED (credential).** `frontend/e2e/bank-connect.spec.ts:86` is now written, but it skips at `:91` because Flinks is not configured.

Not gating, because no check covers it:

3. **F5 - Low, security residual.** `services/core/app/modules/bank_sync/flinks.py:293`, through `_send`'s `path` local at `:189`, and the lookbehind in `services/core/app/log.py:45`. Recommended as a small follow-up fix.
