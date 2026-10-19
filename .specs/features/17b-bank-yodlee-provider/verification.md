# Yodlee as a second bank provider - verification report

**Verdict**: PASS
**Profile**: light
**Diff range**: ac281ac^..5145430 (HEAD); round-4 scope de55fc2..5145430 (771863e, 21744d9, a84494c, 611d8fc, 564ec9c, 5145430)
**Round**: 4 - scoped
**Verifier**: independent sub-agent (author != verifier)

All 50 checks are proven at `5145430`. Round 3 had no verdict other than PASS, so this round covers the diff `de55fc2..5145430`, which contains:

- the caplog rewrite of the gap-8 test;
- the second `Proof:` lines on C7, C18, C34 and C40;
- the new check C50;
- the FastLink container fix in the shared hook.

The hook changed, so every web check that goes through it (C38-C43, C50) was re-run at HEAD. C44 could not run here and carries from round 3.

- **CI for HEAD:** GitHub Actions run `39281203709` on `5145430116c0` completed `success`. I observed it, not just read a report of it.
  - api: `uv run pytest` gave `1198 passed, 5 deselected` with 0 failed. "Check the OpenAPI contract is current" passed.
  - web: `npm test` gave `427 passed (427)` across 56 files, and lint, typecheck, build and "Check generated API types are current" all passed.
- **Fault injection:** two faults were injected on the new C50 surface, and both were killed.

## Binding sources

Carried from f25367b. No source is marked binding. Step 1 does not run because the profile is `light`. The container fix keeps the composition the same: the same `div#container-fastlink` renders under the same `active` condition, with only a `ref` added (`frontend/components/onboarding/connect-bank.tsx:104-106`, `frontend/components/settings/yodlee-reconnect-banner.tsx:58`).

## Checks

**Verified at 5145430** for the web checks C37-C43, C45 and C50, for the non-DB API checks C7 and C49, and for C4 proof 2. **Verified at 5145430 through CI run 39281203709** for every DB-backed check. **Carried from de55fc2** for C44 only.

How each part was run:

- **Web, one batched call** (from `frontend`). The command was `npx vitest run tests/connect-bank.test.tsx tests/yodlee-connect.test.tsx tests/bank-settings-page.test.tsx tests/security-headers.test.ts tests/connect-yodlee-bank-action.test.ts -t "yodlee action|loading|error and retry|success posts provider account|sends the yodlee provider|close returns to start|copy from messages|yodlee reconnect|csp allows yodlee|container exists when fastlink opens" --reporter=verbose`.
  - Result: 12 passed, 25 skipped, 5 files, exit 0. Every cited test printed `✓`, including both C50 tests.
  - `C10 loading skeleton` also matched the `loading` term. It is a spec-17 test and carries no 17b check.
- **Lint and typecheck** (from `frontend`): `npm run lint` exit 0, and `npm run typecheck` (`next typegen && tsc --noEmit`) exit 0.
- **API, non-DB, local** (from `services/core`):
  - `uv run python -m pytest tests/test_yodlee_client.py -rA -p no:cacheprovider -k "timeout_raises_yodlee_error or timeout_is_15_seconds"` gave `PASSED ...::test_timeout_raises_yodlee_error` and `PASSED ...::test_timeout_is_15_seconds`, 2 passed.
  - The C49 file was run with `-k yodlee`: 4 PASSED.
- **API, DB-backed** (no Postgres on this machine, so CI is the evidence). CI run `39281203709` at `5145430`: `1198 passed, 5 deselected, 2 warnings`, 0 failed, 0 skipped.
  - CI prints pytest progress as dots, not test names. The proof that every named test ran is therefore that each file's dot count matches its locally collected count, with no `F`, `E` or `s`:
    - `tests/test_bank_sync_yodlee.py`: 14 dots, 14 collected (including `test_disconnect_when_yodlee_is_off_deletes_locally`);
    - `tests/test_bank_connect_yodlee.py`: 38+3 = 41 dots, 41 collected;
    - `tests/test_bank_yodlee_migration.py`: 3;
    - `tests/test_yodlee_client.py`: 12;
    - `tests/test_log.py`: 28;
    - the 7 C4 proof-1 files are all dots.
  - The earlier run `39277846920` for `a84494c` also completed `success` with `1198 passed`. That is the first green CI of the caplog change. `git diff a84494c..HEAD -- services/` is empty.
- **C4 proof 2:** `git diff ac281ac^..HEAD -- services/core/tests | grep -E "^-\s+assert"` still prints only the two route-count lines. a84494c removed no `assert` line: its only removed lines are the two `structlog` imports, the `with structlog.testing.capture_logs()` line and the old `orphaned =` comprehension, and none of them starts with `assert`.
- **C44:** `npx playwright test e2e/bank-yodlee.spec.ts` needs the API and Postgres. It could not run on this machine, and CI has no Playwright job. It is carried from de55fc2 (3 passed, 16.9 s), where it ran against the pre-fix hook. See gap 2.

### Citation changes since round 3

- `tests/test_bank_sync_yodlee.py` lost two import lines in a84494c, so every citation in it moved up by 2.
- `frontend/tests/yodlee-connect.test.tsx` gained one import line in 5145430, so every citation in it moved down by 1. The C42 test moved below the new C50 test.
- Every other cited file is untouched in `de55fc2..HEAD`, so those citations carry from de55fc2.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | check accepts plaid, yodlee; rejects other | CI 39281203709: `test_bank_yodlee_migration.py` 3/3 | `services/core/tests/test_bank_yodlee_migration.py:21-24` `pytest.raises(IntegrityError, match="ck_bank_connections_provider")` for `provider="other"` | PASS |
| C2 | downgrade fails with a yodlee row, deletes nothing | CI 39281203709 (as C1) | `services/core/tests/test_bank_yodlee_migration.py:31` `pytest.raises(AssertionError, match="ck_bank_connections_provider")`; `:36-41` count `== 1` | PASS |
| C3 | downgrade restores `('plaid')` | CI 39281203709 (as C1) | `services/core/tests/test_bank_yodlee_migration.py:48-51` a yodlee insert raises after the downgrade | PASS |
| C4 | Plaid suites pass; only the two route-count tripwires edited | proof 1: CI 39281203709, all 7 files green; proof 2: local git diff, exactly 2 lines | `services/core/tests/test_security_rules.py:110` `assert len(routes) == 30`; `:147` `assert len(routes) == 37`; a84494c removed no `assert` | PASS |
| C5 | list shows provider per connection | CI 39281203709 (`test_bank_connect_yodlee.py` 41/41) | `services/core/tests/test_bank_connect_yodlee.py:106` `sorted(i["provider"] for i in items) == ["plaid", "yodlee"]` | PASS |
| C6 | any of 6 settings unset: providers omits yodlee, fastlink 404 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:137` `== {"providers": ["plaid"]}`; `:138` `== 404`, parametrized over 6 | PASS |
| C7 | over 15 s raises `YodleeError(http_status=None)` | local: both proofs `PASSED`; CI 12/12 | `services/core/tests/test_yodlee_client.py:46` `raised.value.http_status is None`; new proof `:178` `test_timeout_is_15_seconds`, `:187` `seen == [{"connect": 15.0, "read": 15.0, "write": 15.0, "pool": 15.0}]` - asserts the 15 s bound the first proof cannot | PASS |
| C8 | error carries status and code, no body | CI 39281203709; untouched | `services/core/tests/test_yodlee_client.py:59` `== (400, "Y301")`; `:60-61` `"SECRET-BODY-TEXT" not in` | PASS |
| C9 | DEBIT +25.0, CREDIT -25.0 | CI 39281203709 | `services/core/tests/test_yodlee_client.py:94-97` `== {"yodlee:1": 25.0, "yodlee:2": -25.0}` | PASS |
| C10 | only POSTED returned | CI 39281203709 | `services/core/tests/test_yodlee_client.py:110` `== ["yodlee:1"]` | PASS |
| C11 | stored debit -2500, credit 2500 | CI 39281203709 (`test_bank_sync_yodlee.py` 14/14) | `services/core/tests/test_bank_sync_yodlee.py:157-160` `{...amount_cents...} == {"Payment 1": -2500, "Payment 2": 2500}` | PASS |
| C12 | providers 200, both lists | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:146-147` `== 200`, `["plaid", "yodlee"]`; `:151` `["plaid"]` | PASS |
| C13 | registers `hr-<hex>` once; 200 with 4 fields | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:163` `== 200`; `:165-176`; `:178` `yodlee.registered == [login_name(business_id)]` | PASS |
| C14 | no second registration | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:190` `yodlee.registered == [login_name(business_id)]` | PASS |
| C15 | edit-mode parameters | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:203-204` `provider_account_id == pa`, `launches[-1] == (login_name(business_id), pa)` | PASS |
| C16 | Plaid connection_id -> 409 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:215-216` `== 409`, problem+json | PASS |
| C17 | Yodlee failure -> 503 problem+json, no detail | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:227-230` `== 503`, `"Y902" not in response.text` | PASS |
| C18 | no access token, client secret, admin login in logs or Sentry | CI 39281203709: `test_bank_connect_yodlee.py` 41/41, `test_log.py` 28/28 | proof 1 unchanged; new proof 2 `services/core/tests/test_bank_connect_yodlee.py:621` `test_no_yodlee_secret_in_logs_or_sentry`, `:665` `assert transport.events`, `:666` `leaks = [ACCESS_TOKEN, secret, admin, login_name(business_id)]`, `:667-668` `[v for v in leaks if v in logs] == []`, `... in events] == []` - names all three AC 15 values | PASS |
| C19 | user token uses `hr-` login, never admin | CI 39281203709 | `services/core/tests/test_yodlee_client.py:126` `set(logins) == {USER}` | PASS |
| C20 | 201; item ID, encrypted login, audit, first sync | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:261` `== 201`; `:270`; `:272`; `:277-278`; `:280-281` | PASS |
| C21 | only checking CAD included | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:299` `{"Chequing CAD": True, "Savings CAD": False, "Chequing USD": False, "Visa": False}` | PASS |
| C22 | same institution twice -> 409 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:316` `== 409`; `:318` `len(connections) == 1` | PASS |
| C23 | 3 field mismatches -> 422 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:340-341` `== 422`, `stored(...) == ([], [])` | PASS |
| C24 | no accounts -> nothing stored, deleted, 503 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:353-355` | PASS |
| C25 | `yodlee:123` | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:244` `== ["yodlee:123"]` | PASS |
| C26 | 3 rows, one event added=3 | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:256-258` `result.added == 3`, `len(...) == 3`, `== [3]` | PASS |
| C27 | second sync 0/0/0, no event | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:271` `== (0, 0, 0)`; `:273` `len(seen) == published` | PASS |
| C28 | 730 then 90 days | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:282` `fake.transaction_from_dates == [...]` | PASS |
| C29 | `last_synced_at` = earlier of | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:293` `== NOW - timedelta(hours=10)`; `:297` `== NOW + timedelta(minutes=1)` | PASS |
| C30 | `login_required` | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:307` `is True`; `:310` `view.status == "login_required"` | PASS |
| C31 | nightly sync, 1 h retry, fourth failure ends night | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:356` `["synced"] == 1`; `:372` `== utc(2026, 10, 6, 7)`; `:379` `failed_nights == 1` | PASS |
| C32 | mid-sync failure changes nothing | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:328-330` `== []`, `balance(c) == 10000`, `last_synced_at is None` | PASS |
| C33 | delete remote first | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:411-412` `still_stored_at_delete == [True]`, `fake.deleted == [(LOGIN, ...)]` | PASS |
| C34 | failed delete -> 503, rows kept | CI 39281203709 | service level `services/core/tests/test_bank_sync_yodlee.py:435-437` row, `balance(c) == 10000`, `len(transactions(c)) == 1`; new proof 2 `services/core/tests/test_bank_connect_yodlee.py:546` `test_repair_and_disconnect_over_http`, `:564` `failed.status_code == 503`, `:566` `len(stored(business_id)[0]) == 1` - carries the route's `503`, which proof 1 (below the HTTP boundary) cannot | PASS |
| C35 | not found -> disconnect succeeds | CI 39281203709 | `services/core/tests/test_bank_sync_yodlee.py:468` no `DELETE` sent; `:470` `session.get(...) is None` | PASS |
| C36 | link-token for Yodlee -> 409 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:369-370` `== 409`, detail | PASS |
| C37 | Yodlee action only when offered | local vitest `yodlee action shows only where the API offers Yodlee` ✓ | `frontend/tests/connect-bank.test.tsx:137-138`; `:142` `[BANK.connect, BANK.yodleeConnect]` | PASS |
| C38 | disabled and announced while opening | local vitest `loading` ✓ (hook changed) | `frontend/tests/yodlee-connect.test.tsx:64` `textContent == BANK.yodleeOpening`; `:65` `disabled == true`; `:66` `aria-busy == 'true'` | PASS |
| C39 | route failure: en.json error, retry | local vitest `error and retry` ✓ | `frontend/tests/yodlee-connect.test.tsx:75` `alert().textContent == BANK.errors.launchFailed`; `:76` enabled; `:80-82` second launch, `fastlink.open` called once, no error | PASS |
| C40 | onSuccess 42 -> connect with yodlee and "42" | local vitest `success posts provider account` ✓; `sends the yodlee provider and the provider account, then redirects` ✓ | `frontend/tests/yodlee-connect.test.tsx:99` `toHaveBeenCalledWith(BUSINESS, '42')`; new proof 2 `frontend/tests/connect-yodlee-bank-action.test.ts:37`, `:44` `body: { provider: 'yodlee', provider_account_id: '4242' }` - carries the `provider = yodlee` half of the claim | PASS |
| C41 | close -> initial state, no connect | local vitest `close returns to start` ✓ | `frontend/tests/yodlee-connect.test.tsx:111` not called; `:112` container `toBeNull()`; `:113-115` enabled, label, no error | PASS |
| C42 | strings from en.json | local vitest `copy from messages` ✓ | `frontend/tests/yodlee-connect.test.tsx:146-148` `yodleeHint`, `yodleeConnect`, `yodleeProvider` | PASS |
| C43 | settings reconnect: edit mode, then repair | local vitest `yodlee reconnect opens fastlink in edit mode, then repairs` ✓ | `frontend/tests/bank-settings-page.test.tsx:413` `launchFastLink` `(BUSINESS, rbc.id)`; `:415` `{ configName: 'Headroom', flow: 'edit', providerAccountId: 4242 }`; `:418` `repairConnection` `(BUSINESS, rbc.id)` | PASS |
| C44 | 375 px, axe, 44 px, keyboard | carried from de55fc2 (Playwright 3 passed). Not runnable here (no API, no Postgres), and CI has no e2e job | `frontend/e2e/bank-yodlee.spec.ts:16` `scrollWidth <= 375`; `:19` `height >= 44`; `:22` `violations == []`; `:25-27` keyboard, then `#container-fastlink` visible | PASS (carried from de55fc2) |
| C45 | CSP allows Yodlee | local vitest `csp allows yodlee's fastlink script and frame` ✓ | `frontend/tests/security-headers.test.ts:37-38` | PASS |
| C46 | other business -> 404 x3 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:403-404` `== 404`, `yodlee.calls == []` | PASS |
| C47 | non-owner -> 403 x3 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:417-418` `== 403` | PASS |
| C48 | unknown business -> 404 x3 | CI 39281203709 | `services/core/tests/test_bank_connect_yodlee.py:430-431` `== 404` | PASS |
| C49 | deploy check fails on shared ID or secret, prints no value | local: 4 PASSED (`test_shared_yodlee_credential_fails[...]` x3, `test_yodlee_config_name_may_match`) | `.specs/features/34-launch-production/test_check_no_shared_credentials.py:153` `code == 1`; `:155` `"yodlee-same-value-7" not in output` | PASS |
| C50 | `#container-fastlink` exists when `fastlink.open` runs (connect and reconnect, first activation), no error; container gone after a failed open | local vitest `container exists when fastlink opens` ✓; `reconnect container exists when fastlink opens` ✓ | the fake throws `Invalid container element` like the real `initialize.js` (`frontend/tests/yodlee-connect.test.tsx:121-124`); `:130` `expect(present).toEqual([true])` (exactly one open, with the container present); `:131` no alert; after a throwing open, `:139` `alert().textContent == BANK.errors.launchFailed`, `:140` `document.getElementById(FASTLINK_CONTAINER_ID)).toBeNull()`. Reconnect: `frontend/tests/bank-settings-page.test.tsx:447` `expect(present).toEqual([true])`; `:448` reconnect error `toBeNull()` | PASS |

Named tests confirmed: every web name printed `✓` in this round's vitest run. The local API names printed `PASSED`. DB-backed names are confirmed by matching CI's per-file dot counts to the locally collected counts.

### The gap-8 test (a84494c), read against critical rule 3

`services/core/tests/test_bank_sync_yodlee.py:473` `test_disconnect_when_yodlee_is_off_deletes_locally`.

- **Not weakened.**
  - The final assertion is byte-identical to round 3: `:500` `assert [e["provider_item_id"] for e in orphaned] == [c.provider_account_id]`.
  - The local-deletion assertions at `:495` (`transactions(c) == []`) and `:497` (`session.get(BankConnection, ...) is None`) are unchanged.
  - Only the capture source changed: `:484` `caplog.clear()`, `:498` `logs = [r.msg for r in caplog.records if isinstance(r.msg, dict)]`, `:499` filter on `e.get("event") == "bank_connection.orphaned"`.
- **The new capture path works.** `app/log.py:79-84` configures `ProcessorFormatter.wrap_for_formatter` with `cache_logger_on_first_use=True`. With that configuration, the stdlib `LogRecord.msg` is the structlog event dict.
  - I confirmed this without a database: in a fresh process, after `configure_logging()`, `service.log.error("bank_connection.orphaned", provider_item_id="y")` reached a root handler as `{'provider_item_id': 'y', 'event': 'bank_connection.orphaned', 'level': 'error', ...}`.
  - The stated root cause of the earlier failure holds: once a logger is cached, structlog's `capture_logs` no longer sees it.
- **It still discriminates.** Removing `log.error("bank_connection.orphaned", ...)` at `services/core/app/modules/bank_sync/service.py:1438-1444` leaves no matching record. `orphaned` becomes `[]`, and `[] == [c.provider_account_id]` fails.
  - The `isinstance(r.msg, dict)` filter can only drop records, so it cannot invent a match.
  - A wrong `provider_item_id` also fails.
- **Observed green:** CI `39277846920` (a84494c) and `39281203709` (HEAD) both ran this file, 14/14 dots.
- **New, low: the test now depends on test order (a false negative, never a false pass).**
  - `configure_logging()` runs only in the app lifespan (`app/main.py:37`), in `run_due.main` (`app/jobs/run_due.py:43`) and in other test modules. Nothing in `tests/test_bank_sync_yodlee.py` or `tests/conftest.py` calls it.
  - In my fresh-process simulation with structlog unconfigured, the same `log.error` reached the root handler as `[]`, because structlog's default `PrintLogger` bypasses stdlib.
  - So run alone (`pytest tests/test_bank_sync_yodlee.py -k disconnect_when_yodlee_is_off`), the test is expected to fail. It passes in the full suite because earlier modules configure logging. This is predicted from the simulation and not observed, since there is no Postgres here.

### The fix, read against C38-C43 and C50 (`frontend/components/onboarding/use-yodlee-connect.ts`)

- `open()` now ends at `setActive(true)` then `setLaunch(result.launch)` (`:106-107`). The ref callback `attachContainer` (`:57-94`) opens FastLink only when it receives a non-null element and there is a pending `launch`. It clears `launch` first, so a later re-attach is a no-op. A throwing `open` resets `active` and sets `launchFailed` (`:88-91`).
- The loading state is unchanged: `opening` is still set in `try` and cleared in `finally` (`:96-113`).
- The callbacks `onSuccess`, `onError` and `onClose` moved verbatim into the ref callback (`:72-86`), so C40 and C41 are unchanged in behaviour.
- `open`'s dependency list correctly drops `onLinked` (`:113`), and `attachContainer` depends on `[launch, onLinked]` (`:93`).
- Before this fix, C40's `:95` `document.getElementById(containerId)).not.toBeNull()` passed even with the bug, because it ran after `act` had already rendered. C50's in-call `present` probe is what makes the timing visible. Fault F1 below confirms it.

## Coverage

Carried from de55fc2. The profile is `light`, so this join is optional, and the fix touched no API set. The one web set this round adds:

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| hosts of `#container-fastlink` (2) | code: `frontend/components/onboarding/connect-bank.tsx:104-106`, `frontend/components/settings/yodlee-reconnect-banner.tsx:58` (every `ref={attachContainer}`) | connect-bank C50 `frontend/tests/yodlee-connect.test.tsx:130` · reconnect banner C50 `frontend/tests/bank-settings-page.test.tsx:447` | - |

## Faults injected

The profile is `light`, so this step is not required. It ran because the brief asked for it on C50. Each fault was applied to the real tree, then reverted with `git checkout -- frontend/components/onboarding/use-yodlee-connect.ts`. `git status --porcelain` matched the baseline (`?? .playwright-mcp/` only) after each one.

| Mutation | Location | Killed |
| --- | --- | --- |
| F1: the original bug. `open()` calls `window.fastlink!.open(..., FASTLINK_CONTAINER_ID)` synchronously right after `setActive(true)`, instead of `setLaunch` | `frontend/components/onboarding/use-yodlee-connect.ts:106-107` | yes - both C50 tests failed: `expected [ false ] to deeply equal [ true ]` (`frontend/tests/yodlee-connect.test.tsx:130`, `frontend/tests/bank-settings-page.test.tsx:447`) |
| F3: the failed-open `catch` keeps `active` (drop `setActive(false)`) | `frontend/components/onboarding/use-yodlee-connect.ts:88-91` | yes - `frontend/tests/yodlee-connect.test.tsx:140` `expected <div id="container-fastlink" …> to be null`. The reconnect C50 test stays green because it does not exercise a failed open (see gap 4) |

## Other commits in scope

- **771863e** (round-3 report): docs only.
- **21744d9** (tracked `.pyc` under `.specs/features/34-launch-production/__pycache__/`): this affects no 17b claim.
  - Python validates bytecode against the source's mtime and size, and recompiles when stale. C49 ran green here from source.
  - Running C49 locally rewrote both tracked `.pyc` files again. I restored them with `git checkout`. That is hygiene churn (gap 5).
- **611d8fc** (second `Proof:` lines): each added proof names a test that exists, ran green at HEAD, and asserts the claim. See the C7, C18, C34 and C40 rows. Round 3's low gap 5 is closed.
- **564ec9c** (C50): the claim matches the fix and the binding behaviour of FastLink described in the brief. `checks.md`'s header line still says "49 checks" (gap 6).
- **STATE.md:** AD-151 (`.specs/STATE.md:158`) now records the Yodlee-off disconnect decision. Round 3's gap 4 (the record half) is closed.

## Ranked remaining gaps

None blocks the verdict. In order of risk:

1. **Residual race window** (carried from round 3): concurrent uncommitted connects where the second fails on a Yodlee error can delete the provider account that the first then stores. `services/core/app/modules/bank_sync/service.py:502-507,582-587`.
2. **C44 not re-run against the new hook.** Playwright needs the API and Postgres, and CI has no e2e job. The keyboard path in `frontend/e2e/bank-yodlee.spec.ts:25-27` ends at `#container-fastlink` visible, and it last passed at de55fc2 with the old hook. The unit proofs of the same path are green at HEAD.
3. **React 19 StrictMode, dev only (low, reasoned, not observed).**
   - React 19 invokes ref callbacks twice on mount in StrictMode, and Next 16's App Router enables StrictMode by default (`frontend/next.config.ts` does not disable it).
   - The second call reuses the same closure, in which `launch` is still non-null because `setLaunch(null)` has not re-rendered yet. So in `npm run dev`, `attachContainer` (`frontend/components/onboarding/use-yodlee-connect.ts:57-60`) may call `window.fastlink.open` twice.
   - Production builds do not double-invoke.
4. **C50's failed-open clause is proven on the connect screen only.** `frontend/tests/yodlee-connect.test.tsx:139-140` covers it; `frontend/tests/bank-settings-page.test.tsx:422-450` does not exercise a throwing open. Both screens share the hook, and fault F3 shows that one proof catches the regression (precision, low).
5. **The gap-8 test is order-dependent.** `services/core/tests/test_bank_sync_yodlee.py:484,498` reads records that reach stdlib only after some earlier test has called `configure_logging()`. Run alone, it is expected to fail. That is a false negative, not a false pass.
6. **C18 discrimination** (carried): the client secret and admin login never enter the faked stack. `services/core/tests/test_bank_connect_yodlee.py:667-668`. The real-client redaction is proven at key level only, in `services/core/tests/test_log.py:189,202-206`.
7. **The re-query in the `except`** (carried) can mask a database-loss error and skip the orphaned log. `services/core/app/modules/bank_sync/service.py:502-507`.
8. **Out of scope** (carried): while Yodlee is off, the nightly job fails each Yodlee connection every night.
9. **Hygiene:**
   - The tracked `.pyc` under `.specs/features/34-launch-production/__pycache__/` change on every run of C49.
   - The `checks.md` header still says "49 checks in 8 slices" with C50 present (`.specs/features/17b-bank-yodlee-provider/checks.md:6`).

Closed since round 3: the `checks.md` Proof lines for C7, C18, C34 and C40 (611d8fc), and the Yodlee-off disconnect decision record (AD-151).

## Gate

Verified at 5145430:

- **CI run `39281203709`** (`5145430116c0`, `completed success`):
  - api: `uv run pytest` gave `1198 passed, 5 deselected, 2 warnings`, 0 failed. ruff, mypy and "Check the OpenAPI contract is current" passed.
  - web: `npm test` gave `Test Files 56 passed (56)`, `Tests 427 passed (427)`. lint, typecheck, build and "Check generated API types are current" passed.
- **CI run `39277846920`** (a84494c, `completed success`): api `1198 passed, 5 deselected`; web `425 passed`.
- **Local web proofs:** `npx vitest run <5 files> -t "<alternation>" --reporter=verbose` gave 12 passed, 0 failed, 25 skipped. `npm run lint` and `npm run typecheck` both exit 0.
- **Local API proofs:** `uv run python -m pytest tests/test_yodlee_client.py -k "timeout_raises_yodlee_error or timeout_is_15_seconds"` gave 2 passed. The C49 file with `-k yodlee` gave 4 passed.
- **C4 proof 2:** exactly the 2 expected lines.
- **Playwright C44:** carried from de55fc2 (3 passed). Not run in round 4.
