# Flinks as a second bank provider verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: d49f5fd..e44ef58135fd3d14f769cfc667ab2b819d0d3137
**Round**: 3 - scoped
**Verifier**: independent sub-agent (author != verifier)

At `e44ef58`, 35 of 37 checks are proven with located evidence. 2 are BLOCKED: C32, and the Flinks-on half of C37. None FAIL. Both blocked rows wait on open question 1, the missing Flinks sandbox credentials. `services/core/.env.local` holds no `FLINKS_*` value (`grep -c FLINKS_` = 0), and real Flinks was not called. A BLOCKED row is not a PASS, so the verdict is FAIL.

Round 2's F5, and the-judge's F1, F2 and F3, are all fixed. The fault injections for F5 and F2 both killed their mutants. One new Medium finding, F6, is outside C1-C37. The `providers.py` move broke spec 14's Plaid sandbox proof, which still calls the removed `service.to_cents`.

What this round re-ran and re-read:

- **Scope:** `git diff 93fb8fb..e44ef58`, which covers `5fb8e60` (the F5 fix) and `e44ef58` (the judge fixes).
- **Proofs:** every proof was re-run in full at `e44ef58`.
- **Citations:** refreshed in the files the diff touched. Those are `services/core/app/log.py`, `services/core/app/modules/bank_sync/service.py`, the new `providers.py`, `services/core/tests/conftest.py`, `test_bank_connect_flinks.py`, `test_bank_sync_flinks.py`, `test_flinks_client.py`, `frontend/components/onboarding/use-flinks-connect.ts` and `frontend/tests/flinks-connect.test.tsx`.
- **Carried forward:** citations in files the diff did not touch are carried from `93fb8fb`, and marked as such. Those files are the migration test, `flinks.py`, `api.py`, the web component tests other than flinks-connect, and the e2e spec.

## Checks

*Proof runs verified at `e44ef58`. A citation marked "(refreshed)" was re-read at `e44ef58`. One marked "(carried from 93fb8fb)" is in a file the diff did not touch.*

What was run at HEAD:

- **API:** one pytest call over `test_bank_provider_migration.py`, `test_bank_connect_flinks.py`, `test_flinks_client.py`, `test_bank_sync_flinks.py` and `test_bank_flinks_sandbox.py`. It used the `-k` alternation of every named proof, the round-1 and round-2 additions and the 2 new F5 tests, with `-p no:cacheprovider -rA`. Result: **65 passed, 1 deselected** (the `flinks_sandbox` test). Every named test showed individually as PASSED.
- **C5 suites, run whole:** **181 passed**.
- **Web:** one `npx vitest run` over 6 files (`connect-bank`, `bank-api-flinks`, `flinks-connect`, `connect-bank-action`, `bank-settings-page` and `choose-accounts`), with `--reporter=verbose`. Result: **6 files, 61 passed**.
- **Playwright:** both `localhost:3000` (307) and `localhost:8000` answered curl. `-g "C43|flinks layout keyboard and axe"` gave **3 passed, 1 skipped** (2 setup, C43, and the Flinks test skipped).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | existing rows become `plaid`, columns renamed | `test_existing_rows_become_plaid` PASSED | `services/core/tests/test_bank_provider_migration.py:132`, `:148`, `:151-152` (carried from 93fb8fb) | PASS |
| C2 | downgrade restores `plaid_*`, drops `provider`, rows intact | `test_downgrade_restores_plaid_names` PASSED | `services/core/tests/test_bank_provider_migration.py:162`, `:165`, `:169-178` (carried from 93fb8fb) | PASS |
| C3 | `other` rejected by `ck_bank_connections_provider` | `test_provider_check_constraint` PASSED | `services/core/tests/test_bank_provider_migration.py:186` (carried from 93fb8fb) | PASS |
| C4 | both uniques; other provider inserts | `test_provider_uniques` PASSED | `services/core/tests/test_bank_provider_migration.py:201-209`, `:215` (carried from 93fb8fb) | PASS |
| C5 | Plaid suites pass with only renames | 8 suites: **181 passed**. The corrected grep `git diff d49f5fd -- services/core/tests \| grep -E "^-\s+assert" \| grep -vE "plaid_(item\|account\|transaction\|institution)_id\|len\(routes\) =="` **printed nothing** (exit 1) | `services/core/tests/test_security_rules.py:110`, `:147`, the route-count tripwires (carried from 93fb8fb). `e44ef58` removed no `assert` line in tests | PASS |
| C6 | list shows `provider` | `test_list_shows_provider` PASSED | `services/core/tests/test_bank_connect_flinks.py:391-392` (refreshed) | PASS |
| C7 | sandbox connect URL, query, origin | `test_connect_url[connect_url_sandbox]`, `test_connect_url_sandbox` PASSED | `services/core/tests/test_bank_connect_flinks.py:133-140`, `:150` (refreshed) | PASS |
| C8 | `acme` instance, no `demo` | `test_connect_url[connect_url_production_has_no_demo]` PASSED | `services/core/tests/test_bank_connect_flinks.py:140`, `query.get("demo") == demo` (refreshed) | PASS |
| C9 | 4 unset settings give 404 problem+json | `test_connect_url_not_configured[x4]` PASSED | `services/core/tests/test_bank_connect_flinks.py:172-174` (refreshed) | PASS |
| C10 | bookkeeper 403, stranger 404 | `test_connect_url_denied`, `test_flinks_connect_denied` PASSED | `services/core/tests/test_bank_connect_flinks.py:183-190`, `:199-202` (refreshed) | PASS |
| C11 | 201, sha256 item, decryptable loginId, mask, audit | `test_flinks_connect_stores_connection`, `..._unknown_type_is_other` PASSED | `services/core/tests/test_bank_connect_flinks.py:218`, `:220`, `:223`, `:231` (refreshed) | PASS |
| C12 | 5-way `Type` mapping | `test_account_type_mapping[x5]` PASSED | `services/core/tests/test_flinks_client.py:136` (refreshed, unchanged; the fix only appended at `:386`) | PASS |
| C13 | first sync queued once | `test_flinks_connect_queues_first_sync` PASSED | `services/core/tests/test_bank_connect_flinks.py:256-257` (refreshed) | PASS |
| C14 | `SetScheduledRefresh` body | `test_enable_nightly_refresh_body`, `test_flinks_connect_enables_refresh` PASSED | `services/core/tests/test_flinks_client.py:148` (refreshed); `services/core/tests/test_bank_connect_flinks.py:266` (refreshed) | PASS |
| C15 | 5 bad bodies 422; Plaid default 201 | `test_connect_body_validation[x5]`, `..._plaid_default` PASSED | `services/core/tests/test_bank_connect_flinks.py:292-294`, `:310-311` (refreshed) | PASS |
| C16 | duplicate institution 409 | `test_flinks_duplicate_institution_is_409` PASSED | `services/core/tests/test_bank_connect_flinks.py:322-324` (refreshed) | PASS |
| C17 | still preparing 503, nothing stored, no DeleteCard; retry 201 | `test_flinks_connect_still_preparing` PASSED | `services/core/tests/test_bank_connect_flinks.py:334-339`, `:343-344` (refreshed) | PASS |
| C18 | 10 s poll, budget 3/30 | `test_async_poll_budget_*` PASSED (3 tests) | `services/core/tests/test_flinks_client.py:177-178` (refreshed) | PASS |
| C19 | `FlinksError(status, code)` only; 503; timeout 15 | `test_errors_carry_only_code`, `..._on_timeout`, `test_timeout_is_15s`, `test_flinks_failure_is_503[x2]`, `test_flinks_connect_url_failure_is_503` PASSED | `services/core/tests/test_flinks_client.py:196`, `:214`, `:223-225` (refreshed); `services/core/tests/test_bank_connect_flinks.py:355-357`, `:369-370` (refreshed) | PASS |
| C20 | no loginId, AccountNumber or holder in logs/responses | `test_no_secrets_in_logs_or_responses`, `test_sentry_event_carries_no_flinks_secrets` and the new `test_sentry_event_from_delete_carries_no_login_id` PASSED | `services/core/tests/test_bank_connect_flinks.py:434`, `:436`, `:438` (refreshed); `services/core/tests/test_flinks_client.py:339-350`, `:425-427` (refreshed) | PASS |
| C21 | identity flags false; AccountNumber not kept | `test_accounts_detail_body_excludes_identity` PASSED | `services/core/tests/test_flinks_client.py:236`, `:245` (refreshed) | PASS |
| C22 | Days365 then Days90 | `test_first_sync_days365_then_days90` PASSED | `services/core/tests/test_bank_sync_flinks.py:146` (refreshed); the request is now built at `services/core/app/modules/bank_sync/providers.py:286-291` | PASS |
| C23 | half-even sign and values | `test_transaction_values_and_sign` PASSED | `services/core/tests/test_bank_sync_flinks.py:171-178` (refreshed); sign at `services/core/app/modules/bank_sync/providers.py:239-241` | PASS |
| C24 | resync 0/0/0; modified 1 | `test_resync_is_idempotent_and_modifies` PASSED | `services/core/tests/test_bank_sync_flinks.py:198-203` (refreshed) | PASS |
| C25 | absent transaction kept | `test_absent_transaction_is_kept` PASSED | `services/core/tests/test_bank_sync_flinks.py:219-220` (refreshed); `removed=[]` at `services/core/app/modules/bank_sync/providers.py:269` | PASS |
| C26 | `last_synced_at = min(now, LastRefresh)` | `test_last_synced_at_follows_last_refresh[x3]` PASSED | `services/core/tests/test_bank_sync_flinks.py:241` (refreshed); `services/core/app/modules/bank_sync/providers.py:304-306` | PASS |
| C27 | balances, relabel, one event | `test_balances_relabel_and_event` PASSED | `services/core/tests/test_bank_sync_flinks.py:266-275` (refreshed) | PASS |
| C28 | nightly via cached Authorize; 1/2/4 h retries | `test_nightly_syncs_flinks`, `test_nightly_flinks_retries`, `test_authorize_cached_body` PASSED | `services/core/tests/test_bank_sync_flinks.py:295-296`, `:311-312` (refreshed); `services/core/tests/test_flinks_client.py:262` (refreshed) | PASS |
| C29 | login codes set `login_required` | `test_login_codes_set_login_required[x3]` PASSED | `services/core/tests/test_bank_sync_flinks.py:331`, `:334` (refreshed) | PASS |
| C30 | DeleteCard 204; a failure still deletes locally and logs the orphan | `test_disconnect_flinks`, `..._when_delete_card_fails` PASSED | `services/core/tests/test_bank_sync_flinks.py:358-359`, `:381-388` (refreshed); the log is at `services/core/app/modules/bank_sync/providers.py:330-336` | PASS |
| C31 | Flinks link-token 409 | `test_flinks_link_token_is_409` PASSED | `services/core/tests/test_bank_sync_flinks.py:400-401` (refreshed) | PASS |
| C32 | sandbox transaction IDs stable | not run: there is no `FLINKS_*` in `services/core/.env.local`, so real Flinks was not called. `-m flinks_sandbox --co` collects 1 test | `services/core/tests/test_bank_flinks_sandbox.py:83` (exists, never executed; carried from 93fb8fb) | BLOCKED |
| C33 | ConnectBank shows Plaid + Flinks + hint; otherwise Plaid only; non-404 goes to Sentry | `provider choice` (connect-bank and choose-accounts) and `connect url loader` x4 PASSED | `frontend/tests/connect-bank.test.tsx:151-152`, `:161`; `frontend/tests/bank-api-flinks.test.ts:50`, `:58`; `frontend/tests/choose-accounts.test.tsx:343-355` (carried from 93fb8fb) | PASS |
| C34 | dialog loading, Esc focus, origin, REDIRECT | `dialog loading and focus`, `message origin:` x3 PASSED | `frontend/tests/flinks-connect.test.tsx:62-69`, `:81`, `:91` (refreshed; the fix inserted 2 lines after `:92`) | PASS |
| C35 | action body; 503 stillPreparing retry; 409 | `flinks:` x4, `still preparing retry...`, `already connected...` PASSED | `frontend/tests/connect-bank-action.test.ts:102`, `:111` (carried from 93fb8fb); `frontend/tests/flinks-connect.test.tsx:118`, `:127` (refreshed, shifted +2) | PASS |
| C36 | "via Plaid/Flinks"; no Reconnect for Flinks | `provider labels, and a Flinks bank needing attention has no Reconnect` PASSED | `frontend/tests/bank-settings-page.test.tsx:402-407` (carried from 93fb8fb) | PASS |
| C37 | 375 px, Tab, 44 px, axe, with the Flinks dialog closed and open | `C43 layout keyboard and axe` PASSED (Flinks off). `flinks layout keyboard and axe` **skipped**: Flinks is not configured | `frontend/e2e/bank-connect.spec.ts:62`, `:64`, `:67` (Flinks off); Flinks-on skip guard at `:91`, checks at `:93-109` (carried from 93fb8fb; written but never executed) | BLOCKED |

### The providers.py move (verified at e44ef58)

- **The move preserves behaviour.** I took every line `e44ef58` removed from `service.py`, applied the renames, and diffed the result against `providers.py`:
  - **Renames applied:** `_plaid_account`→`plaid_account`, `_flinks_account`→`flinks_account`, `_invalid`→`invalid_response`, `_fetch`→`fetch`, `_synced_at`→`synced_at` and `_remove_at_provider`→`remove_at_provider`.
  - **Removed lines not found in `providers.py`:** only the six rewritten call sites (`service.py:272`, `:444`, `:714`, `:826`, `:832`, `:1232`).
  - **Lines in `providers.py` that are new:** only the module docstring, the imports and `log = structlog.get_logger(__name__)` (`providers.py:1-34`).
  - Every function body moved verbatim.
- **The sign rules are unchanged.**
  - Plaid: `amount_cents=-cents` with `cents = to_cents(transaction.amount)` (`services/core/app/modules/bank_sync/providers.py:194`, `:205`).
  - Flinks: `(to_cents(credit) or 0) - (to_cents(debit) or 0)` (`providers.py:239-241`).
  - A grep of `app/` for other sign flips (`-to_cents`, `amount_cents=-`, `= -cents`, `* -1`) finds only `providers.py:205`.
  - AGENTS.md's "flip the sign once, in bank_sync" still holds, because `providers.py` is inside `bank_sync`.
- **`remove_at_provider` still logs `bank_connection.orphaned` with only IDs and codes.** Its fields are `business_id`, `connection_id`, `provider="flinks"` and `error_code` (`providers.py:330-336`). C30 still asserts one orphan line, with the connection ID and no loginId (`services/core/tests/test_bank_sync_flinks.py:386-388`).
- **The logger name change does not matter.** The event's `logger` field is now `app.modules.bank_sync.providers`.
  - No test asserts the logger name. C30 matches on the event name in captured stdout.
  - `app/monitoring.py:35` ignores only the `problems` logger, so the error-level orphan line still reaches Sentry as before.
  - No other reference to the old logger name exists in `app/`, `tests/`, `.specs/` or `context/`. It is a cosmetic change to the field, and it would matter only to an external log query, of which the repo has none.
- **Module boundaries hold.** `providers.py` imports only `bank_sync`'s own `flinks`, `models`, `plaid` and `tokens` (`providers.py:16-32`), and no module outside `bank_sync` imports `providers`.
  - `service.py` re-imports `ReportedAccount`, `ReportedTransaction`, `Update` and the functions (`service.py:42-52`).
  - It no longer exposes `to_cents` or `account_type`. See F6.
- **The full suite was run at HEAD as a regression net for the refactor:** 1185 passed, 6 deselected.

### Level and sampling judgment (carried from 93fb8fb, two additions)

- The round-1 and round-2 judgments still hold.
- **Added: the F5 tests discriminate.** I injected a fault without editing the tree. A pytest plugin in the scratchpad restored the pre-fix lookbehind `(?<=/DeleteCard/)` in `app.log.TOKEN_PATTERN`. Both new tests then **failed**: `services/core/tests/test_flinks_client.py:400` and `:426`. Killed.
- **Added: the F2 assertion discriminates.** I injected a fault without editing the tree. A scratchpad vitest config aliased `@/components/onboarding/use-flinks-connect` to a copy without the new `router.refresh()` (`use-flinks-connect.ts:36`). Then `message origin: a REDIRECT from the iframe connects with its loginId` **failed** with "expected vi.fn() to be called 1 times, but got 0 times" at `frontend/tests/flinks-connect.test.tsx:93`. Killed.

### Swept rows that say "existing" (carried from 93fb8fb)

- Authorization (`OwnerDep`, `services/core/app/modules/bank_sync/api.py:74`) and concurrency (the lock order, and `DuplicateBankError` on the unique) are unchanged. `_sync_locked` still fetches, then locks the accounts, then applies (`service.py:826-832`).

## Findings

### Earlier items, re-judged at e44ef58

- **Round-2 F5 - fixed and proven.**
  - The lookbehind is now `(?<=DeleteCard/)` (`services/core/app/log.py:45`), so a bare `DeleteCard/<id>` frame local is redacted, along with the URL form.
  - `test_delete_card_login_id_redacted_in_any_form` covers both forms (`services/core/tests/test_flinks_client.py:388-400`).
  - `test_sentry_event_from_delete_carries_no_login_id` drives a real `client.delete` whose transport raises `RuntimeError`, and asserts that the event carries frame `vars` and no loginId (`:425-427`).
  - Both tests were fault-injected and killed, as described above.
  - The pattern is looser now, but harmless: it would also redact a token after a `DeleteCard/` that has no leading slash.
- **Judge F1 (should-fix) - resolved.**
  - The provider adapters live in `services/core/app/modules/bank_sync/providers.py` (336 lines), and `service.py` dropped from 1581 to 1293 lines.
  - The move is behaviour-preserving inside `app/`, as described above. It has one test-side regression outside C1-C37, which is F6.
- **Judge F2 (should-fix) - resolved.**
  - `submit` calls `router.refresh()` after every connect result (`frontend/components/onboarding/use-flinks-connect.ts:36`), and `router` was added to the deps at `:39`.
  - The assertion is at `frontend/tests/flinks-connect.test.tsx:93` and was killed by fault injection.
  - On success, the server action redirects, and the extra refresh is harmless.
- **Judge F3 (nit) - resolved.**
  - `flinks` and `no_flinks` are imported once in `services/core/tests/conftest.py:150-151`.
  - Every `# noqa: F811` on a Flinks fixture is gone from `test_bank_connect_flinks.py` and `test_bank_sync_flinks.py`.
  - The remaining `# noqa: F811` sit only on Plaid's `fake` fixture (`test_bank_connect_flinks.py:284`, `:299`, `:375`), and each carries a stated reason.
  - `ruff check .` passes.

### New finding

- **F6 - Medium, regression outside C1-C37: spec 14's Plaid sandbox proof calls a function that `e44ef58` removed.**
  - **Where:** `services/core/tests/test_transaction_sync_sandbox.py:104` reads `service.to_cents(...)`, but `to_cents` moved to `providers.py:65` and is not re-exported. A probe, `hasattr(app.modules.bank_sync.service, "to_cents")`, returned `False`.
  - **Effect:** when spec 14's C39/C40 sandbox proof is run (`-m plaid_sandbox`), it will raise `AttributeError` at `:104` after a real sync. That proof was green before `e44ef58`.
  - **Why nothing caught it:**
    - The test is deselected by default (`services/core/pyproject.toml:51`).
    - Ruff cannot see a missing attribute on a module.
    - The gate runs mypy on `app` only.
    - Collection succeeds, because the attribute is read at run time.
  - I did not run it, because it calls the real Plaid sandbox. The failure follows from the code.
  - **Fix shape:** import `to_cents` from `app.modules.bank_sync.providers` in that test.
  - **Coverage:** no check of this feature covers it, so it does not change the C1-C37 verdict. It does contradict the "behaviour-preserving" claim of `e44ef58` at the test level.
- **Note (not a finding):** in the REDIRECT-without-loginId branch, `useFlinksConnect` closes the dialog through `setOpen(false)` and does not refresh (`frontend/components/onboarding/use-flinks-connect.ts:56-58`). A reopen then reuses the same authorize token. Whether Flinks spends the token on such a redirect is not documented in the judge's research log. This was the behaviour before `e44ef58`, and F2 did not target it.

## Gate

*Verified at `e44ef58` unless marked as carried.*

- API named proofs: one pytest call, `-k` alternation, `-p no:cacheprovider -rA`. **65 passed, 0 failed, 1 deselected** (`flinks_sandbox`).
- C5 suites: **181 passed, 0 failed**. C5 corrected grep: **no output**.
- Full API suite (`uv run pytest -p no:cacheprovider -q -x`): **1185 passed, 0 failed, 6 deselected** (the sandbox-marked tests, F6's among them).
- Web vitest: 6 files, **61 passed, 0 failed**.
- Playwright `-g "C43|flinks layout keyboard and axe"`: **3 passed, 1 skipped** (Flinks on, blocked).
- Fault injection: F5 killed (`test_flinks_client.py:400`, `:426`); F2 killed (`flinks-connect.test.tsx:93`).
- `uv run ruff format --check .`: 193 files already formatted. `uv run ruff check .`: all checks passed. `uv run mypy app`: no issues in 76 source files.
- `npm run typecheck`: exit 0. `npx eslint` on `use-flinks-connect.ts` and `flinks-connect.test.tsx`: exit 0.
- Model vs migration drift and the `contracts/openapi.json` regeneration: carried from 93fb8fb. The diff touched no model, migration or route.

### Ranked gaps (why the verdict is FAIL)

The only gaps holding the verdict at FAIL are credential blockers (open question 1):

1. **G1 - C32 BLOCKED (credential).** `services/core/tests/test_bank_flinks_sandbox.py:83` exists and collects, but it cannot run without `FLINKS_*`. Criterion 17's stable-ID assumption is still unproven.
2. **G2 - C37 Flinks-on half BLOCKED (credential).** `frontend/e2e/bank-connect.spec.ts:86` is written, but it skips at `:91` because Flinks is not configured.

Not gating, because no check of this feature covers it:

3. **F6 - Medium.** `services/core/tests/test_transaction_sync_sandbox.py:104` calls the removed `service.to_cents`, which breaks spec 14's Plaid sandbox proof. This needs a one-line import fix before that proof is next run.
