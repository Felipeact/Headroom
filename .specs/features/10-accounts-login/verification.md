# 10 - Login with Clerk verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: c4aa31f..02ab1d3 (`development`, HEAD `02ab1d3`). The round 2 fix diff is e01daa9..02ab1d3.
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

**33 of 34 checks are proven at `02ab1d3`.** The one check that is not proven is C33 (CI on the pushed commit). It still cannot run: pushing to `development` deploys staging, and that waits on the user. Every round 1 failure in C26, C28 and C29 now passes, and so the verdict is FAIL only because of C33. Once the push is approved and C33's proof is green, the feature can PASS.

## Fix diff reviewed (verified at 02ab1d3)

- **`frontend/lib/api/auth.ts`:** reads `exp` from the cookie token. When the token has under 10 seconds left, it calls `session.getToken({ expiresInSeconds: 60 })` to mint a new one. A token whose expiry cannot be read is sent unchanged.
  - The option is real in the installed Clerk: `ServerGetTokenOptions.expiresInSeconds` is declared at `frontend/node_modules/@clerk/shared/dist/types/ssr.d.ts:24`, and `@clerk/backend` forwards it as `expires_in_seconds`.
  - Nothing new is logged, cached or stored, and `proofs.sh c31` still passes.
- **`frontend/tests/api-auth.test.ts`:** adds two tests.
  - A token with 50 seconds left is kept, and `getToken` is called exactly once.
  - A token with 5 seconds left is replaced by the fresh one, and `getToken` is last called with `{ expiresInSeconds: 60 }`.
  - The two C21 tests are unchanged except for the helper. `tok_abc` is not shaped like a JWT, so it takes the "expiry unreadable, send unchanged" path. The assertion is still the exact header, so C21's claim holds.
- **`services/core/tests/test_auth.py`:** `REJECTIONS` gains `("bearer_empty", lambda: "Bearer", "missing")` and now has 13 cases. For this case `removeprefix("Bearer ")` leaves `"Bearer"`, so the test also asserts that the word `Bearer` never appears in the log, which is stricter.
- **`frontend/e2e/auth.spec.ts`:** C26 calls `settle(page)` after the Tab sequence and before axe. No assertion was removed or loosened.

## Checks

### How the proofs ran (verified at 02ab1d3)

The table's evidence cells refer to these runs by name:

- **pytest:** `uv run pytest tests/test_auth.py tests/test_accounts.py tests/test_settings.py tests/test_migrations.py -v -k "<the 17 proof keywords>"` exited 0 with 41 passed. The output lists every parametrised id, including `test_rejected_logs_reason[bearer_empty]`.
- **vitest:** `npx vitest run tests/user-name.test.ts tests/api-auth.test.ts tests/app-layout.test.tsx tests/auth-protect.test.ts tests/clerk-appearance.test.ts --reporter=verbose` exited 0 with 11 passed, each named.
- **`proofs.sh`:** `bash proofs.sh c15 c31 c32` exited 0. `bash proofs.sh c20`, run after R2-1 to R2-3 (each includes C18), printed `PASS c20`.
- **Playwright set-up:** every run used `NEXT_PUBLIC_SENTRY_DSN=` (empty).
  - So that the API log could be read, I started the API myself with the same command the config uses (`uv run fastapi dev app/main.py --port 8100`, from `services/core`) and logged its output to the scratchpad.
  - Playwright then reused it (`reuseExistingServer: !process.env.CI`) and started the web app itself.
- **Playwright runs:**
  - R2-1, R2-2 and R2-3 each ran `e2e/auth.spec.ts` plus the 5 older specs, and each exited 0 with 82 passed.
  - R2-4 ran the C28 command exactly as written and exited 0 with 74 passed.
- **API log across all four runs:**
  - 293 `GET /v1/me` requests, all returning `200`, and 0 non-200.
  - 0 `auth.rejected` events.
  - 0 `SyntaxError` lines in the Playwright output.

### Results

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | valid RS256 token -> 200, keys exactly id/clerk_user_id/created_at | pytest `test_valid_token_returns_me` PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:99` - `set(body) == {"id", "clerk_user_id", "created_at"}`; `:100` - `body["clerk_user_id"] == "user_test_c1"`; `:101` - `uuid.UUID(body["id"])` | PASS |
| C2 | 4 missing or malformed headers -> problem 401 + `WWW-Authenticate: Bearer` | pytest `test_missing_or_malformed_header[no_header,basic,bearer_empty,no_prefix]` PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:42-49` - `status_code == 401`, `content-type == "application/problem+json"`, `www-authenticate == "Bearer"`, `title == "Unauthorized"`, `detail == "Authentication required."`, `instance == "/v1/me"`; called at `:118` | PASS |
| C3 | exp -10s rejected, exp -3s accepted | pytest both `expired` tests PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:125` - `assert_rejected(...)`; `:132` - `.status_code == 200` | PASS |
| C4 | other key, altered payload -> 401 | pytest `test_bad_signature[2 ids]` PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:138` - `assert_rejected(...)` | PASS |
| C5 | none, HS256 with PEM, RS512 -> 401 | pytest `test_wrong_algorithm[3 ids]` PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:150` - `assert_rejected(...)` | PASS |
| C6 | nbf +10s, no sub -> 401 | pytest both `nbf_or_sub` tests PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:157`, `:161` - `assert_rejected(...)` | PASS |
| C7 | azp foreign 401 / listed 200 / absent 200 / list empty 200 | pytest 4 `test_authorized_parties_*` PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:168` - `assert_rejected`; `:175`, `:180` - `== 200`; `:184` - `clerk_authorized_parties == []`; `:187` - `== 200` | PASS |
| C8 | every /v1 route 401 without token; /healthz/live 200 | pytest `test_every_v1_route_requires_token` PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:198` - `"/v1/me" in v1`; `:203` - `response.status_code == 401, (method, path)`; `:205` - `/healthz/live ... == 200` | PASS |
| C9 | missing CLERK_JWT_KEY -> ValidationError naming it; parties parsing | pytest 3 `clerk` tests PASSED (verified at 02ab1d3) | `services/core/tests/test_settings.py:67` - `"clerk_jwt_key" in str(excinfo.value)`; `:87` - `Settings().clerk_authorized_parties == parsed` | PASS |
| C10 | first request -> exactly 1 row, id matches | pytest PASSED (verified at 02ab1d3) | `services/core/tests/test_accounts.py:44` - `rows_for(sub) == 1`; `:47` - `str(user.id) == response.json()["id"]` | PASS |
| C11 | 3 sequential calls -> same id, 1 row | pytest PASSED (verified at 02ab1d3) | `services/core/tests/test_accounts.py:55` - `len(ids) == 1`; `:56` - `rows_for(sub) == 1` | PASS |
| C12 | two threads released by one barrier -> same id, no error, 1 row | pytest PASSED (verified at 02ab1d3) | `services/core/tests/test_accounts.py:78-81` - `errors == []`, `len(results) == 2`, `results[0] == results[1]`, `rows_for(sub) == 1` | PASS |
| C13 | rejected request leaves 0 rows | pytest PASSED (verified at 02ab1d3) | `services/core/tests/test_accounts.py:91` - `status_code == 401`; `:92` - `rows_for(sub) == 0` | PASS |
| C14 | users schema exact, downgrade removes it, check clean | pytest `test_users_table_upgrade_downgrade_and_check` PASSED (verified at 02ab1d3) | `services/core/tests/test_migrations.py:128` - the exact column set; `:133` - `{("pk_users",...),("uq_users_clerk_user_id","UNIQUE","clerk_user_id")}`; `:145` - `"users" not in tables`; `:150` - `check` returncode 0 | PASS |
| C15 | module files, docstring, no cross-module import | `proofs.sh c15` -> PASS (verified at 02ab1d3) | `.specs/features/10-accounts-login/proofs.sh:19`, `:25`, `:27` | PASS |
| C16 | 5 protected paths -> /sign-in signed out | R2-1/2/3 passed (verified at 02ab1d3) | `frontend/e2e/auth.spec.ts:53` - `expect.poll(() => pathOf(page), { message: path }).toBe('/sign-in')` over `PROTECTED` (`:8`) | PASS |
| C17 | /sign-in, /sign-up 200, form, no shell | R2-1/2/3 passed (verified at 02ab1d3) | `frontend/e2e/auth.spec.ts:63` - `status() ... toBe(200)`; `:64-65` - input and `Continue` visible; `:66` - `getByTestId('shell') ... toHaveCount(0)` | PASS |
| C18 | signed in, shell + full name from Clerk | R2-1/2/3 passed (verified at 02ab1d3) | `frontend/e2e/auth.spec.ts:128` - `getByTestId('header-user')).toContainText((await testUser()).fullName)`; the test user's first and last names are non-empty (checked in round 1, carried from e01daa9) | PASS |
| C19 | display name full name / email fallback | vitest 2 tests passed (verified at 02ab1d3) | `frontend/tests/user-name.test.ts:31` - `toBe('Ada Lovelace')`; `:36` - `toBe('ada@example.test')` | PASS |
| C20 | after sign-in, exactly 1 users row for the test user's Clerk ID | `proofs.sh c20` -> PASS (verified at 02ab1d3) | `.specs/features/10-accounts-login/proofs.sh:49` - `[ "$rows" = "1" ]`; the API log shows 293 `GET /v1/me` -> 200 this round, so verified tokens reached the API in this round | PASS |
| C21 | authHeaders -> `{Authorization: "Bearer tok_abc"}`; null rejects; no console | vitest `authHeaders sends...`, `authHeaders rejects...` passed (verified at 02ab1d3) | `frontend/tests/api-auth.test.ts:39` - `toEqual({ Authorization: 'Bearer tok_abc' })`; `:47` - `rejects.toThrow()`; `:40`, `:48` - `not.toHaveBeenCalled()` | PASS |
| C22 | /v1/me 401 or rejected -> errorTitle, no children | vitest 2 `me fails` tests passed (verified at 02ab1d3) | `frontend/tests/app-layout.test.tsx:47`, `:56` - `getByText(messages.States.errorTitle)`; `:48`, `:57` - `queryByText('page content')).toBeNull()` | PASS |
| C23 | desktop sign out -> /sign-in, / again -> /sign-in | R2-1/2/3 passed (verified at 02ab1d3) | `frontend/e2e/auth.spec.ts:140`, `:143` - `toBe('/sign-in')` | PASS |
| C24 | 375px: name + Sign out in Dialog, -> /sign-in | R2-1/2/3 passed (verified at 02ab1d3) | `frontend/e2e/auth.spec.ts:152` - `dialog.getByTestId('menu-user')).toContainText(fullName)`; `:155` - `toBe('/sign-in')` | PASS |
| C25 | primary button bg == --accent; form font is Plex | R2-1/2/3 passed (verified at 02ab1d3) | `frontend/e2e/auth.spec.ts:86` - `expect(buttonBackground).toBe(accent)`; `:94` - `toMatch(/IBM Plex Sans/)`; `:96` - `formFont.split(',')[0].trim()).toBe(plexFamily)` | PASS |
| C26 | auth pages at 375: no overflow, Tab order, axe 0 | R2-1/2/3 passed, 3 of 3 (verified at 02ab1d3) | `frontend/e2e/auth.spec.ts:110` - `toBeLessThanOrEqual(375)`; `:112-113` - `tabTo(input)`, `tabTo(continueButton)`; `:115` - `settle(page)` added after the Tab walk; `:118` - `axe.violations ... toEqual([])` | PASS |
| C27 | Sign out >= 44x44, Tab-reachable, axe 0, desktop + 375 | R2-1/2/3 passed (verified at 02ab1d3) | `frontend/e2e/auth.spec.ts:167-168`, `:183-184` - `toBeGreaterThanOrEqual(44)`; `:169`, `:185` - `tabTo`; `:171`, `:187` - `violations).toEqual([])` | PASS |
| C28 | existing 5 specs pass signed in | R2-1, R2-2, R2-3 (superset) and R2-4 (the exact C28 command) all exited 0, 4 of 4 (verified at 02ab1d3) | `frontend/e2e/shell.spec.ts:70` - `expect(page.locator('main h1')).toHaveText(title)`; `:293` - the same over `PAGES` at 375 and 1440 (round 1 failed here on the error state); `:279` - `expect(skip).toBeFocused()` (round 1 failed here on `/sign-in`); `frontend/e2e/dev-components.spec.ts:237` - toast `toHaveCount(0)` | PASS |
| C29 | each of the 13 rejected cases in C2-C7 logs one `auth.rejected` with the listed reason, no token | pytest `test_rejected_logs_reason[13 ids incl. bearer_empty]` PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:217` - `REJECTIONS` with 13 entries, including `bearer_empty` -> `missing`; `:258` - `len(rejected) == 1`; `:259` - `rejected[0]["reason"] == reason`; `:261`, `:263` - `header not in out`, `secret not in out` | PASS |
| C30 | accepted request logs no token | pytest PASSED (verified at 02ab1d3) | `services/core/tests/test_auth.py:274-275` - `value not in out.out`, `value not in out.err` | PASS |
| C31 | getToken only in lib/api/auth.ts, which has no console/cookies/storage | `proofs.sh c31` -> PASS (verified at 02ab1d3; `auth.ts` changed in the fix) | `.specs/features/10-accounts-login/proofs.sh:57` - `[ "$hits" = "frontend/lib/api/auth.ts" ]`; `:59` - fails on `console.\|cookies(\|localStorage\|sessionStorage` | PASS |
| C32 | env examples have the keys; no Clerk key or PEM in tracked or addable files | `proofs.sh c32` -> PASS (verified at 02ab1d3) | `.specs/features/10-accounts-login/proofs.sh:68`, `:71` - `grep -qxF "$line"`; `:77` - `[ -z "$leaks" ]` | PASS |
| C33 | CI run on the pushed commit: jobs web and api succeed | **not run**: nothing is pushed, and pushing to `development` deploys staging, which still lacks the Clerk variables, so it waits on the user | no evidence - `.specs/features/10-accounts-login/proofs.sh` c33 needs `origin/development` at the feature commit | NOT RUN |
| C34 | every layout/page outside root, sign-in and sign-up has `await auth.protect()`; proxy has no createRouteMatcher; >= 8 files | vitest `every page protected` passed (verified at 02ab1d3) | `frontend/tests/auth-protect.test.ts:23` - `toBeGreaterThanOrEqual(8)`; `:27` - `expect(unprotected).toEqual([])`; `:30` - `not.toMatch(/createRouteMatcher/)` | PASS |

## Round 1 non-PASS verdicts re-judged (verified at 02ab1d3)

### C28: was FLAKY, now PASS

- **Round 1 failure modes:** the shell showed the error state while signed in, the shared session dropped to `/sign-in`, and the toast-timing test failed.
- **This round:** 4 of 4 runs were green. The API log I captured myself shows 0 `auth.rejected` events and 0 non-200 `/v1/me` responses out of 293. Neither the session drop nor the `SyntaxError` the coordinator reported happened.
- **What I cannot confirm:**
  - These runs finished faster than round 1 (42-47 s against about 1.4 min), likely because the API and the `.next` build were already warm. So the slow-render condition that let tokens expire was probably not recreated. The near-expiry branch is proven at the unit level (`frontend/tests/api-auth.test.ts:62-63`), not end to end.
  - The coordinator says the root cause of the session drop is unconfirmed. I cannot confirm it either: it did not recur in my 4 runs.
- **Result:** C28 is PASS on what I observed, with the residual risk noted.

### C26: was FLAKY, now PASS

- 3 of 3 runs were green.
- The fix, a `settle(page)` call before axe, addresses the animating-error cause seen in round 1. axe still checks the settled colour, so the check is not weaker.

### C29: was GAP, now PASS

- All 13 members of C2-C7 are in `REJECTIONS`, and the reasons map to Coverage: 4 cases give `missing`, 1 gives `expired`, 7 give `invalid` and 1 gives `unauthorized_party`.

### C33: NOT RUN, unchanged

- It still needs the user's go-ahead to push.

## Level and sampling judgments

These are carried from e01daa9. The fix diff did not touch these files, apart from the `test_auth.py` change re-judged above.

- **C8:** the table is built from OpenAPI paths, because FastAPI 0.142.2 keeps the `/v1` router out of `app.routes`. It is complete for today's routes. A future route marked `include_in_schema=False` would drop out of the table but would still be guarded by the router-level dependency (`services/core/app/main.py:45-51`).
- **C12:** a barrier releases the two threads together, but nothing forces their inserts to overlap. It is probabilistic evidence for the unique-constraint guarantee.
- **C20:** the proof would also pass on a row left from an earlier run. This round, the API log provides separate evidence that tokens reached the API.
- **C34:** a substring check. It would catch a deleted `auth.protect()`, but not one moved into a comment or out of first position. It does not scan `route.ts` handlers or server actions. `frontend/app/dev/sentry-check/actions.ts` (spec 07) has no auth check and is outside this diff.
- **Tests changed in round 1:** carried from e01daa9. The four tests changed in round 1 were adapted, not weakened. The round 2 test changes only add cases or a wait (see "Fix diff reviewed").

## Swept re-read

Carried from e01daa9. The fix diff touched none of the cited constraints.

- **C12:** `uq_users_clerk_user_id` is at `services/core/migrations/versions/07f1bcba78b6_create_users.py:35`, and `on_conflict_do_nothing` is at `services/core/app/modules/accounts/repository.py:13`.
- **C1:** verification needs no network call to Clerk, because `services/core/app/auth.py:42` calls `jwt.decode` with the PEM key from settings.
- **Note on the fix:** the new web-side refresh in `frontend/lib/api/auth.ts` does call Clerk's Backend API, but only when a token is close to expiring. API-side verification stays local.

## Gate

Verified at 02ab1d3:

- **pytest:** 41 passed, 0 failed.
- **vitest:** 11 passed, 0 failed.
- **`proofs.sh`:** c15, c20, c31 and c32 all PASS.
- **Playwright:** 4 runs, 82 + 82 + 82 + 74 passed, 0 failed.
- **C33:** not run.
- **API log:** 0 `auth.rejected` events.
- **Tree:** clean before and after, apart from this report.

## Ranked gaps

1. **C33 is not run.** CI on the pushed feature commit is unproven until the user approves the push to `development`. After that, run `bash .specs/features/10-accounts-login/proofs.sh c33`.
