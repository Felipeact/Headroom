# Flinks as a second bank provider verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: d49f5fd..0490b60e6a884e214410f951e8124a054ac91481
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

35 of 37 checks are proven with located evidence at `0490b60`. 2 are BLOCKED: C32, and the Flinks-on half of C37. Both wait on open question 1, the missing Flinks sandbox credentials. None FAIL. The verdict is FAIL because a BLOCKED row is not a PASS. The adversarial review also found one security defect in the code: Sentry frame locals can carry the loginId and the `AccountNumber` (Findings F1). It is not covered by any check.

## Checks

Proofs were run at HEAD `0490b60`:

- API: one pytest call over `test_bank_provider_migration.py`, `test_bank_connect_flinks.py`, `test_flinks_client.py`, `test_bank_sync_flinks.py` and `test_bank_flinks_sandbox.py`, with the full `-k` alternation, `-p no:cacheprovider -rA -v`. Result: **58 passed, 3 deselected**. Every named test showed individually as PASSED.
- C5 suites, run whole: **181 passed**.
- Web: one `npx vitest run` over 5 files, `--reporter=verbose`. Result: **47 passed**.
- Playwright: `-g "C43|flinks layout keyboard and axe"`. Result: **3 passed** (2 setup, plus C43).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | existing rows become `plaid`, columns renamed | `test_existing_rows_become_plaid` PASSED | `services/core/tests/test_bank_provider_migration.py:132` - `assert tuple(row) == ("plaid", "item-1", "ins_1")`; `:148` no `plaid_*` column left; `:151-152` account/transaction renames | PASS |
| C2 | downgrade restores `plaid_*`, drops `provider`, rows intact | `test_downgrade_restores_plaid_names` PASSED | `services/core/tests/test_bank_provider_migration.py:162` - `{"plaid_item_id", "plaid_institution_id"} <= columns(...)`; `:165` - `"provider" not in columns(...)`; `:169-178` row and transaction count kept | PASS |
| C3 | `other` rejected by `ck_bank_connections_provider`, plaid/flinks insert | `test_provider_check_constraint` PASSED | `services/core/tests/test_bank_provider_migration.py:186` - `pytest.raises(IntegrityError, match="ck_bank_connections_provider")` after plaid/flinks inserts at `:184-185` | PASS |
| C4 | `(provider, item)` and `(business, provider, institution)` unique; other provider inserts | `test_provider_uniques` PASSED | `services/core/tests/test_bank_provider_migration.py:209` - `match="uq_bank_connections_provider_provider_item_id"`; `:215` - `match="uq_bank_connections_business_provider_institution"`; the flinks twin at `:201-207` inserts | PASS |
| C5 | existing Plaid suites pass with only renames | 8 suites: 181 passed; the grep printed 2 lines (see Findings G3) | `services/core/tests/test_security_rules.py:110` - `assert len(routes) == 29` (was 28); `:147` - `assert len(routes) == 36` (was 35). Both are route-count bumps for the new route, not weakenings | PASS |
| C6 | list shows `provider` plaid/flinks | `test_list_shows_provider` PASSED | `services/core/tests/test_bank_connect_flinks.py:391` - `sorted(c["provider"] for c in response.json()["items"]) == [...]` | PASS |
| C7 | sandbox connect URL and query, origin | `test_connect_url[connect_url_sandbox]`, `test_connect_url_sandbox` PASSED | `services/core/tests/test_bank_connect_flinks.py:135-142` - origin, `/v2/`, `authorizeToken == ["token-1"]`, `jsRedirect`, `Days365`, `language`, `query.get("demo") == ["true"]`; `:152` origin `https://toolbox-iframe.private.fin.ag` | PASS |
| C8 | `acme` instance, no `demo` | `test_connect_url[connect_url_production_has_no_demo]` PASSED | `services/core/tests/test_bank_connect_flinks.py:142` - `assert query.get("demo") == demo` with `demo=None` for `acme` (`:116`) | PASS |
| C9 | any of 4 settings unset gives 404 problem+json | `test_connect_url_not_configured[x4]` PASSED | `services/core/tests/test_bank_connect_flinks.py:174-175` - `status_code == 404`, `content-type == "application/problem+json"` | PASS |
| C10 | bookkeeper 403, stranger 404 on both routes | `test_connect_url_denied`, `test_flinks_connect_denied` PASSED | `services/core/tests/test_bank_connect_flinks.py:185-190` (connect-url 403/404); `:201-202` - `connect_flinks(bookkeeper,...) == 403`, `connect_flinks(stranger,...) == 404` | PASS |
| C11 | 201, provider, sha256 item, decryptable loginId, mask, audit provider | `test_flinks_connect_stores_connection` PASSED | `services/core/tests/test_bank_connect_flinks.py:220` - `provider_item_id == flinks_item_id(LOGIN_ID)`; `:222` - `decrypt_access_token(...) == LOGIN_ID`; `:225` mask `"6789"`; `:233` audit `{"provider": "flinks", ...}` | PASS |
| C12 | 5-way `Type` mapping | `test_account_type_mapping[x5]` PASSED | `services/core/tests/test_flinks_client.py:136` - `assert account_type(flinks_type) == ours`, with the table at `:127-131` | PASS |
| C13 | first sync queued once | `test_flinks_connect_queues_first_sync` PASSED | `services/core/tests/test_bank_connect_flinks.py:258-259` - `len(syncs) == 1`, `syncs[0].login_id == LOGIN_ID` | PASS |
| C14 | `SetScheduledRefresh` `{loginId, isActivated: true}` | `test_enable_nightly_refresh_body`, `test_flinks_connect_enables_refresh` PASSED | `services/core/tests/test_flinks_client.py:148` - `recorder.body("SetScheduledRefresh") == {"loginId": LOGIN_ID, "isActivated": True}`; `services/core/tests/test_bank_connect_flinks.py:268` - `flinks.refresh_enabled == [LOGIN_ID]` | PASS |
| C15 | 5 bad bodies give 422; Plaid without `provider` gives 201 | `test_connect_body_validation[x5]`, `test_connect_body_validation_plaid_default` PASSED | `services/core/tests/test_bank_connect_flinks.py:294` - `status_code == 422` over the table at `:273-279`; `:312-313` - 201 and `provider == "plaid"` | PASS |
| C16 | duplicate institution gives 409, one connection | `test_flinks_duplicate_institution_is_409` PASSED | `services/core/tests/test_bank_connect_flinks.py:324-326` - `409`, detail, `len(stored(...)[0]) == 1` | PASS |
| C17 | still preparing: 503 and its detail, nothing stored, no DeleteCard; retry gives 201 | `test_flinks_connect_still_preparing` PASSED | `services/core/tests/test_bank_connect_flinks.py:336-340` - `503`, problem+json, `detail == STILL_PREPARING`, `stored == ([], [])`, `flinks.deleted == []`; `:345` - `retry.status_code == 201` | PASS |
| C18 | 10 s poll via injected sleep, budget 3/30 | `test_async_poll_budget_succeeds_within_budget`, `test_async_poll_budget_exhausted[3,30]` PASSED | `services/core/tests/test_flinks_client.py:177` - `sleeps == [10] * polls`; `:178` - `paths().count("GetAccountsDetailAsync/req-1") == polls` | PASS |
| C19 | error/timeout gives `FlinksError(status, code)` only; 503; timeout 15 | `test_errors_carry_only_code`, `..._on_timeout`, `test_timeout_is_15s`, `test_flinks_failure_is_503[x2]` PASSED | `services/core/tests/test_flinks_client.py:196` - `(http_status, flinks_code) == (401, "INVALID_LOGIN")`; `:214` - `(None, "ReadTimeout")`; `:225` - all timeouts 15; `services/core/tests/test_bank_connect_flinks.py:357` - `status_code == 503` | PASS |
| C20 | no loginId, AccountNumber or holder in logs/responses | `test_no_secrets_in_logs_or_responses` PASSED | `services/core/tests/test_bank_connect_flinks.py:435` - `assert secret not in logs`; `:437` - `assert secret not in response.text`, over `LOGIN_ID, ACCOUNT_NUMBER, HOLDER_NAME` | PASS |
| C21 | `WithAccountIdentity`/`WithKYC` false; AccountNumber not kept | `test_accounts_detail_body_excludes_identity` PASSED | `services/core/tests/test_flinks_client.py:236` - body `== {..., "WithAccountIdentity": False, "WithKYC": False, ...}`; `:245` - `"00012345678901" not in repr(snapshot)` | PASS |
| C22 | Days365 then Days90 | `test_first_sync_days365_then_days90` PASSED | `services/core/tests/test_bank_sync_flinks.py:147` - `[(days, with_tx, polls)] == [("Days365", True, SYNC_POLLS), ("Days90", True, SYNC_POLLS)]` | PASS |
| C23 | Credit 12.345 gives 1234, Debit 50.10 gives -5010, pending false, description, date | `test_transaction_values_and_sign` PASSED | `services/core/tests/test_bank_sync_flinks.py:172` - `(amount_cents in, out) == (1234, -5010)`; `:173-178` pending, description, date | PASS |
| C24 | resync gives 0/0/0; changed amount gives modified 1, row count unchanged | `test_resync_is_idempotent_and_modifies` PASSED | `services/core/tests/test_bank_sync_flinks.py:200` - `(0, 0, 0)`; `:201` - `(0, 1, 0)`; `:203` - `len(stored) == 2` | PASS |
| C25 | absent transaction kept, removed 0 | `test_absent_transaction_is_kept` PASSED | `services/core/tests/test_bank_sync_flinks.py:220-221` - `removed == 0`, `set(...) == {"old", "new"}` | PASS |
| C26 | `last_synced_at = min(now, LastRefresh)`, now when later/missing | `test_last_synced_at_follows_last_refresh[earlier,later,missing]` PASSED | `services/core/tests/test_bank_sync_flinks.py:242` - `connection(c).last_synced_at == expected`, cases at `:226-229` | PASS |
| C27 | balances, relabel, one event with connection_id; a no-op publishes none | `test_balances_relabel_and_event` PASSED | `services/core/tests/test_bank_sync_flinks.py:267-271` - `(150050, 140050)`; `:273` relabeled 2; `:274-275` one event with `connection_id`; `:276` - `not again.changed` | PASS |
| C28 | nightly syncs Flinks via cached Authorize; 1/2/4 h retries into `failed_nights` | `test_nightly_syncs_flinks`, `test_nightly_flinks_retries`, `test_authorize_cached_body` PASSED | `services/core/tests/test_bank_sync_flinks.py:296-297` synced via Flinks; `:312-313` - 4 attempts at 6,7,9,13 h, `failed_nights == 1`; `services/core/tests/test_flinks_client.py:262` - `body("Authorize") == {"LoginId": LOGIN_ID, "MostRecentCached": True}` | PASS |
| C29 | INVALID_LOGIN/DISABLED_LOGIN set `login_required`; other codes don't | `test_login_codes_set_login_required[x3]` PASSED | `services/core/tests/test_bank_sync_flinks.py:332` - `login_required is wanted`; `:335` - `(view.status == "login_required") is wanted` | PASS |
| C30 | DeleteCard with loginId, 204; on failure local delete plus orphan log, no loginId | `test_disconnect_flinks`, `test_disconnect_flinks_when_delete_card_fails` PASSED | `services/core/tests/test_bank_sync_flinks.py:360` - `flinks.deleted == [login_id]`; `:384` row gone; `:387-389` one orphan line with `connection_id`, `login_id not in logs` | PASS |
| C31 | Flinks link-token gives 409 with its detail | `test_flinks_link_token_is_409` PASSED | `services/core/tests/test_bank_sync_flinks.py:401-402` - `409`, `detail == "Reconnect this bank: disconnect it, then connect it again."` | PASS |
| C32 | sandbox transaction IDs stable | not run: no `FLINKS_*` in `.env.local`, so real Flinks was not called. Deselected by default (`pyproject.toml:51` addopts); `-m flinks_sandbox --co` collects 1 test | `services/core/tests/test_bank_flinks_sandbox.py:83` - `assert first_ids <= {t.transaction_id for t in second.transactions}` (exists, not executed) | BLOCKED |
| C33 | ConnectBank shows Plaid + Flinks + hint; else Plaid only; non-404 failure goes to Sentry | `provider choice: with/without Flinks`, `connect url loader` x4 PASSED | `frontend/tests/connect-bank.test.tsx:151-152` - order and hint; `:161` - one button; `frontend/tests/bank-api-flinks.test.ts:50` - 404 not reported; `:58` - `Sentry.captureException` called once on 503 | PASS |
| C34 | dialog: loading until load, Esc returns focus, wrong origin ignored, REDIRECT connects | `dialog loading and focus`, `message origin: x3` PASSED | `frontend/tests/flinks-connect.test.tsx:62-65` status until `load`; `:68-69` Esc closes, `activeElement` is the button; `:81` - `connectFlinksBank` not called for another origin; `:91` - called with `(BUSINESS, LOGIN_ID, ...)` | PASS |
| C35 | action posts `{provider: flinks, login_id}`; 503 gives stillPreparing with a retry on the same id; 409 gives already connected | `flinks: x4` (action), `still preparing retry...`, `already connected...` PASSED | `frontend/tests/connect-bank-action.test.ts:102` - `body: { provider: 'flinks', login_id: LOGIN_ID }`; `:111` - `{ error: 'stillPreparing' }`; `frontend/tests/flinks-connect.test.tsx:116` - second call equals `[BUSINESS, LOGIN_ID, ...]`; `:125` already connected | PASS |
| C36 | "via Plaid/Flinks"; Flinks attention has no Reconnect | `provider labels, and a Flinks bank needing attention has no Reconnect` PASSED | `frontend/tests/bank-settings-page.test.tsx:402-403` - via labels; `:406-407` - `reconnectFlinks` text, Reconnect button `toBeNull()` | PASS |
| C37 | 375 px, Tab, 44 px, axe, with the Flinks dialog closed and open | `C43 layout keyboard and axe` PASSED (Flinks off). `flinks layout keyboard and axe` matches no test: `grep` finds only `C43` at `frontend/e2e/bank-connect.spec.ts:58` | `frontend/e2e/bank-connect.spec.ts:67` - `expect(axe.violations).toEqual([])`; `:62` scrollWidth <= 375; `:64` height >= 44. Flinks-on half: no test, and no credentials | BLOCKED |

### Level and sampling judgment

- All status-code claims (C6, C7, C9, C10, C11, C15, C16, C17, C19, C31) are proven through FastAPI's `TestClient`, so there is no level gap.
- C17 proves "3 polls" only at the client level (C18). The API test uses a fake that answers pending once. That is an acceptable split, because `CONNECT_POLLS` is what reaches the client at `services/core/app/modules/bank_sync/service.py:537`.
- C21 asserts one `GetAccountsDetail` body (the sync one, `WithTransactions: true`). The connect-time body is the same literal at `services/core/app/modules/bank_sync/flinks.py:255-261`, so this sampling is sound.
- C28 samples the retry schedule at 6/7/9/13 h. It does not prove that a run between retries is skipped. That is the existing Plaid machinery, reused.
- C33's coverage row claims the choose-accounts "Connect another bank" surface. No test renders `ChooseAccounts` with `flinks`: `frontend/tests/choose-accounts.test.tsx` only gained `provider: 'plaid'`. See G4.
- The connect-url `503` member is proven by `test_flinks_connect_url_failure_is_503` (`services/core/tests/test_bank_connect_flinks.py:371`). That test is not named in any check's proof. I ran it separately and it passed.

### Swept rows that say "existing"

- **authorization.** `OwnerDep = require_member(Role.OWNER)` at `services/core/app/modules/bank_sync/api.py:74` guards `create_flinks_connect_url` (`:241`) and `create_connection` (`:303`). Present.
- **concurrency.** `sync_connection` takes `repository.lock_connection` (`services/core/app/modules/bank_sync/service.py:1158`), then `_sync_locked` calls `lock_accounts` (`:1085`). That is the connection-then-accounts order. Two racing Flinks connects reach `IntegrityError` at `insert_connection` (which flushes, `repository.py:45`), and that maps to `DuplicateBankError` (`service.py` in `connect_flinks_bank`, `_violates(exc, INSTITUTION_INDEX) or _violates(exc, FLINKS_ITEM_INDEX)`). Present.

## Gate

- API named proofs: 58 passed, 0 failed (3 deselected: the `flinks_sandbox` test, plus 2 supporting tests, run separately: 2 passed).
- C5 suites: 181 passed, 0 failed.
- Web vitest: 47 passed, 0 failed.
- Playwright C43: 3 passed.
- Model vs migration drift: `alembic.autogenerate.compare_metadata` against the local DB at `86276e8fa7aa` reported 0 diffs.
- `contracts/openapi.json`: regenerating it with `uv run python -m app.export_openapi` left the file byte-identical to the committed one.

## Findings

### Ranked gaps (why the verdict is FAIL)

Credential blockers (open question 1, blocks go-live) come first, then code and test defects.

1. **G1 - C32 BLOCKED (credential).** The sandbox ID-stability test exists (`services/core/tests/test_bank_flinks_sandbox.py:65`, `:83`) and is deselected by default. It was not run because no `FLINKS_*` values are set. Criterion 17's stable-ID assumption is still unproven.
2. **G2 - C37 Flinks-on half BLOCKED (credential), and its test is absent (test defect).** The proof's `-g "flinks layout keyboard and axe"` matches nothing in `frontend/e2e/bank-connect.spec.ts`. Only `C43` exists (`:58`), and the feature never touched that file. So nothing yet runs axe, the 375 px check or the Tab order with the Flinks dialog open (AC 30). Even with credentials, the test still has to be written.
3. **G3 - C5 second proof printed 2 lines.** These are `-    assert len(routes) == 28` and `-    assert len(routes) == 35` in `services/core/tests/test_security_rules.py`, replaced at `:110` and `:147` by `29` and `36`. Both are route counts updated for the new `POST .../bank/flinks/connect-url`, and `test_bookkeeper_access.py:38` adds that route to the stranger/bookkeeper denial list. That is strengthened, not weakened. The other changes to existing tests are mechanical `plaid_*` to `provider_*` renames, one line reflowed (`test_alert_emails.py:419`), and `"provider"` added to expected key sets. The proof as written ("prints nothing") is literally not met. The check should have excluded route-count bumps. That is a precision gap in the check, not a code defect.
4. **G4 - coverage-row gap (test).** The `connect-bank surfaces (3)` row maps choose-accounts "Connect another bank" to C33. No test renders `frontend/components/onboarding/choose-accounts.tsx` with `flinks` set. That component's Flinks branch, which relabels the button to "Connect with Plaid" and renders `FlinksConnect`, is unproven.

### Code defects (adversarial review)

- **F1 - High, security: Sentry frame locals can carry the loginId and the full `AccountNumber`/holder data.**
  - Where: `services/core/app/monitoring.py:28-33` and `services/core/app/log.py:11-37`.
  - `sentry_sdk` 2.71.0 defaults `include_local_variables=True`.
  - `redact` keeps a bare-UUID `login_id` and a nested `AccountNumber`. A probe of `redact({'login_id': <uuid>, 'a': {'AccountNumber': ..., 'Holder': {...}}})` returned both unredacted:
    - `TOKEN_PATTERN` covers only the `/DeleteCard/` path segment.
    - No key fragment matches `login_id` or `accountnumber`.
  - Consequence: any unexpected (non-`FlinksError`) exception sends these values to Sentry.
    - Example: a `KeyError` in `_snapshot` (`services/core/app/modules/bank_sync/flinks.py:128`, `:144`, `:146`), or a `ValueError` from `_datetime` (`:119`).
    - The frames of `HttpxFlinksClient.accounts` (`login_id`, `:245`) and `_snapshot` (the raw account dict `a`, `:126`) are captured.
    - `sync_in_background` (`service.py`, `except (PlaidError, FlinksError)`) and `create_connection` leave such exceptions unhandled, so the FastAPI/Starlette integration reports them.
  - This breaks AGENTS.md: "Never log, print, or return ... raw data received from Plaid or other providers", and the loginId is a token (AD-145).
  - C20 does not cover Sentry, so this is uncovered rather than contradicting a check.
- **F2 - Medium, robustness: `_datetime` parses `Login.LastRefresh` with `datetime.fromisoformat`, which fails on a slash date.** At `services/core/app/modules/bank_sync/flinks.py:116-120`. `_date` (`:111-113`) explicitly handles Flinks' `yyyy/MM/dd`. If `LastRefresh` uses the same format, every Flinks sync and connect raises `ValueError`. That is not a `FlinksError`: nightly counts it as a generic failure, the background sync leaves it unhandled, and the connect route returns `500`. It also triggers F1. The format is unconfirmed until the sandbox is available (open question 1).
- **F3 - Low, UX: every connect-time `FlinksError` becomes `503`, and the web shows "still preparing - Try again" for all of them.** `services/core/app/modules/bank_sync/api.py` `_flinks_failed` sends `PROVIDER_UNAVAILABLE` for anything that isn't `OPERATION_PENDING`, including `INVALID_LOGIN`. `frontend/app/onboarding/bank/actions.ts` maps every `503` to `stillPreparing` and does not read `detail`. A permanently bad login therefore offers an endless retry. This is consistent with AC 28 as written, so it is a spec precision issue.
- **F4 - Low, data:** at `services/core/app/modules/bank_sync/flinks.py:154`, `institution_id` falls back to the institution *name* when `InstitutionId` is missing. The per-business duplicate check would then key on a display name.

### Reviewed and found correct

- **Sign.** `credit - debit` in cents, in one place inside `bank_sync` (`services/core/app/modules/bank_sync/service.py` `_flinks_transaction`). `to_cents` uses `Decimal(str(x))` with half-even rounding (`service.py:192-198`). Floats are never stored. C23 proves it.
- **Tenancy.**
  - `has_institution`, `transactions_by_provider_id`, `delete_transactions` and `connection_accounts` all filter on `business_id` (`services/core/app/modules/bank_sync/repository.py`).
  - `connection_for_item` is intentionally cross-business, for webhooks, as before.
  - The global `(provider, provider_item_id)` unique means a second business posting the same loginId gets `409`, which needs the secret.
- **Plaid webhook lookup** is now restricted to `provider == "plaid"` (`services/core/app/modules/bank_sync/repository.py:112`), so a Flinks hash can never match. No test pins this filter. That is minor and not covered by a check.
- **Migration.**
  - Upgrade and downgrade are symmetric (`services/core/migrations/versions/*_add_provider_to_bank_connections.py:41-128`).
  - Downgrade refuses while any Flinks row exists (`:91-94`).
  - Constraint renames are explicit.
  - C1, C2, C3 and C4 run it on Postgres, and the model-vs-DB diff is 0.
- **postMessage origin.** `if (event.origin !== origin) return` (`frontend/components/onboarding/use-flinks-connect.ts:43`) uses strict equality against the API-supplied origin, and the listener is attached only while the dialog is open (`:41`). It does not also check `event.source` against the iframe window. That is acceptable given the exact-origin check. The server action re-validates the loginId as a UUID before sending it (`frontend/app/onboarding/bank/actions.ts`, `LOGIN_ID`).
- **Logs.** `flinks.request_failed`, `bank_sync.sync_failed` and `bank_connection.orphaned` carry only ids and codes. httpx's `DeleteCard/{loginId}` request line is redacted (`services/core/app/log.py:36`). C20 and C30 prove it.
- **AGENTS.md.** I found no violation beyond F1:
  - `TODO(question)` comments mark the unconfirmed Flinks strings and headers.
  - The generated files were regenerated, not hand-edited.
  - Interface text is in `messages/en.json`.
