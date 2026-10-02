# 10 - Login with Clerk verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: c4aa31f..e01daa9 (`development`, HEAD `e01daa9`)
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

31 of 34 checks are proven with located evidence at HEAD. Not proven: C33 (not run, needs the push), C29 (its proof covers 12 of the 13 rejection cases it claims), and C28 (its proof is unreliable: green in 1 of 4 runs that included it). C26 is also unreliable (red in 1 of 3 runs). Three of the C28 failures were new failure modes added by this feature: the signed-in shell showed the error state, or the shared session went back to `/sign-in` partway through the suite.

## Checks

Proof batches at HEAD `e01daa9`, with Postgres on localhost:5432 and nothing listening on 3000 or 8100 beforehand:

- **pytest A:** `uv run pytest tests/test_auth.py tests/test_accounts.py tests/test_settings.py tests/test_migrations.py -v -k "<the 17 proof keywords>"`. Exit 0, 40 passed, every parametrised id listed individually.
- **vitest:** `npx vitest run tests/user-name.test.ts tests/api-auth.test.ts tests/app-layout.test.tsx tests/auth-protect.test.ts tests/clerk-appearance.test.ts tests/dev-gate.test.ts tests/api-check-page.test.tsx --reporter=verbose`. Exit 0, 16 passed, each named.
- **proofs.sh:** `bash proofs.sh c15 c31 c32` exited 0. `bash proofs.sh c20`, run straight after PW-3, exited 0.
- **Playwright runs** (all with `NEXT_PUBLIC_SENTRY_DSN=`):
  - **PW-1:** auth plus the 5 existing specs. Exit 1, 80 passed, 2 failed: `shell.spec.ts:96` current link (C4), and `shell.spec.ts:289` axe at 375, whose `main h1` read "We couldn't load this page".
  - **PW-2:** the same set. Exit 1, 80 passed, 2 failed: `auth.spec.ts:99` C26, and `shell.spec.ts:274` skip link, where the page had become `/sign-in`.
  - **PW-3:** `auth.spec.ts` alone. Exit 0, 10 passed.
  - **PW-4:** the C28 command exactly as written. Exit 1, 73 passed, 1 failed: `dev-components.spec.ts:229` toast lasts 4 seconds.
  - **PW-5:** the C28 command exactly as written. Exit 0, 74 passed.

Every named test appears in the output above as run.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | valid RS256 token -> 200, keys exactly id/clerk_user_id/created_at | pytest A `test_valid_token_returns_me` PASSED | `services/core/tests/test_auth.py:99` - `assert set(body) == {"id", "clerk_user_id", "created_at"}`; `:100` - `body["clerk_user_id"] == "user_test_c1"`; `:101` - `uuid.UUID(body["id"])` | PASS |
| C2 | 4 missing or malformed headers -> problem 401 + `WWW-Authenticate: Bearer` | pytest A `test_missing_or_malformed_header[no_header,basic,bearer_empty,no_prefix]` PASSED | `services/core/tests/test_auth.py:42-49` - `status_code == 401`, `content-type == "application/problem+json"`, `www-authenticate == "Bearer"`, `title == "Unauthorized"`, `detail == "Authentication required."`, `instance == "/v1/me"`; called at `:118` | PASS |
| C3 | exp -10s rejected, exp -3s accepted | pytest A `test_expired_beyond_leeway_rejected`, `test_expired_within_leeway_accepted` PASSED | `services/core/tests/test_auth.py:125` - `assert_rejected(...)` (exp=now-10); `:132` - `.status_code == 200` (exp=now-3) | PASS |
| C4 | other key, altered payload -> 401 | pytest A `test_bad_signature[other_key_token,altered_payload_token]` PASSED | `services/core/tests/test_auth.py:138` - `assert_rejected(client.get("/v1/me", headers=bearer(make())))` | PASS |
| C5 | none, HS256 with PEM, RS512 -> 401 | pytest A `test_wrong_algorithm[none_alg_token,hs256_with_public_pem_token,rs512_token]` PASSED | `services/core/tests/test_auth.py:150` - `assert_rejected(...)` | PASS |
| C6 | nbf +10s, no sub -> 401 | pytest A `test_nbf_or_sub_future_nbf_rejected`, `test_nbf_or_sub_missing_sub_rejected` PASSED | `services/core/tests/test_auth.py:157`, `:161` - `assert_rejected(...)` | PASS |
| C7 | azp foreign 401 / listed 200 / absent 200 / list empty 200 | pytest A 4 `test_authorized_parties_*` PASSED | `services/core/tests/test_auth.py:168` - `assert_rejected`; `:175`, `:180` - `.status_code == 200`; `:184` - `clerk_authorized_parties == []`, `:187` - `== 200` | PASS |
| C8 | every /v1 route 401 without token; /healthz/live 200 | pytest A `test_every_v1_route_requires_token` PASSED | `services/core/tests/test_auth.py:198` - `assert "/v1/me" in v1`; `:203` - `assert response.status_code == 401, (method, path)`; `:205` - `/healthz/live ... == 200` | PASS |
| C9 | missing CLERK_JWT_KEY -> ValidationError naming it; parties parsing | pytest A `test_clerk_jwt_key_required`, `test_clerk_authorized_parties_parse[comma_list,unset]` PASSED | `services/core/tests/test_settings.py:67` - `assert "clerk_jwt_key" in str(excinfo.value)`; `:87` - `Settings().clerk_authorized_parties == parsed` | PASS |
| C10 | first request -> exactly 1 row, id matches | pytest A `test_first_request_creates_user` PASSED | `services/core/tests/test_accounts.py:44` - `rows_for(sub) == 1`; `:47` - `str(user.id) == response.json()["id"]` | PASS |
| C11 | 3 sequential calls -> same id, 1 row | pytest A `test_repeat_requests_reuse_user` PASSED | `services/core/tests/test_accounts.py:55` - `len(ids) == 1`; `:56` - `rows_for(sub) == 1` | PASS |
| C12 | two threads released by one barrier -> same id, no error, 1 row | pytest A `test_concurrent_first_requests` PASSED | `services/core/tests/test_accounts.py:78-81` - `errors == []`, `len(results) == 2`, `results[0] == results[1]`, `rows_for(sub) == 1` | PASS |
| C13 | rejected request leaves 0 rows | pytest A `test_rejected_request_creates_nothing` PASSED | `services/core/tests/test_accounts.py:91` - `status_code == 401`; `:92` - `rows_for(sub) == 0` | PASS |
| C14 | users schema exact, downgrade removes it, check clean | pytest A `test_users_table_upgrade_downgrade_and_check` PASSED | `services/core/tests/test_migrations.py:128` - column set `{("id","uuid","NO"),("clerk_user_id","text","NO"),("created_at","timestamp with time zone","NO")}`; `:133` - constraints `{("pk_users","PRIMARY KEY","id"),("uq_users_clerk_user_id","UNIQUE","clerk_user_id")}`; `:145` - `"users" not in tables`; `:150` - `check` returncode 0 | PASS |
| C15 | module files, docstring, no cross-module import | `proofs.sh c15` -> `PASS c15` | `.specs/features/10-accounts-login/proofs.sh:19` - `[ -f "$dir/$f" ]`; `:25` - docstring non-empty; `:27` - grep for `app.modules.` other than accounts | PASS |
| C16 | 5 protected paths -> /sign-in signed out | PW-1, PW-2, PW-3 `C16 signed out redirects` passed | `frontend/e2e/auth.spec.ts:53` - `expect.poll(() => pathOf(page), { message: path }).toBe('/sign-in')` over `PROTECTED` (`:8`, all 5 paths) | PASS |
| C17 | /sign-in, /sign-up 200, form, no shell | PW-1/2/3 `C17 auth pages without shell` passed | `frontend/e2e/auth.spec.ts:63` - `response?.status() ... toBe(200)`; `:64-65` - input and `Continue` visible; `:66` - `getByTestId('shell') ... toHaveCount(0)` | PASS |
| C18 | signed in, shell + full name from Clerk | PW-1/2/3 `C18 shows the name` passed | `frontend/e2e/auth.spec.ts:125` - `getByTestId('shell')).toBeVisible()`; `:126` - `getByTestId('header-user')).toContainText((await testUser()).fullName)` | PASS |
| C19 | display name full name / email fallback | vitest `display name is the full name`, `display name falls back to the primary email` passed | `frontend/tests/user-name.test.ts:31` - `toBe('Ada Lovelace')`; `:36` - `toBe('ada@example.test')` | PASS |
| C20 | after sign-in, exactly 1 users row for the test user's Clerk ID | `proofs.sh c20` after PW-3 -> `PASS c20` | `.specs/features/10-accounts-login/proofs.sh:49` - `[ "$rows" = "1" ]` | PASS |
| C21 | authHeaders -> `{Authorization: "Bearer tok_abc"}`; null rejects; no console | vitest 2 `authHeaders ...` passed | `frontend/tests/api-auth.test.ts:31` - `toEqual({ Authorization: 'Bearer tok_abc' })`; `:39` - `rejects.toThrow()`; `:32`, `:40` - `expect(spy).not.toHaveBeenCalled()` | PASS |
| C22 | /v1/me 401 or rejected -> errorTitle, no children | vitest `me fails with 401...`, `me fails when the call rejects...` passed | `frontend/tests/app-layout.test.tsx:47`, `:56` - `getByText(messages.States.errorTitle)`; `:48`, `:57` - `queryByText('page content')).toBeNull()` | PASS |
| C23 | desktop sign out -> /sign-in, / again -> /sign-in | PW-1/2/3 `C23 sign out desktop` passed | `frontend/e2e/auth.spec.ts:138` - `toBe('/sign-in')` after click; `:141` - `toBe('/sign-in')` after `goto('/')` | PASS |
| C24 | 375px: name + Sign out in Dialog, -> /sign-in | PW-1/2/3 `C24 sign out phone` passed | `frontend/e2e/auth.spec.ts:150` - `dialog.getByTestId('menu-user')).toContainText(fullName)`; `:151` - Sign out inside `dialog`; `:153` - `toBe('/sign-in')` | PASS |
| C25 | primary button bg == --accent; form font is Plex | PW-1/2/3 `C25 themed with tokens` passed | `frontend/e2e/auth.spec.ts:86` - `expect(buttonBackground).toBe(accent)`; `:94` - `plexFamily ... toMatch(/IBM Plex Sans/)`; `:96` - `formFont.split(',')[0].trim()).toBe(plexFamily)` | PASS |
| C26 | auth pages at 375: no overflow, Tab order, axe 0 | PW-1 and PW-3 passed; **PW-2 failed** | `frontend/e2e/auth.spec.ts:110` - `width ... toBeLessThanOrEqual(375)`; `:112-113` - `tabTo(input)`, `tabTo(continueButton)`; `:116` - `axe.violations ... toEqual([])`. In PW-2 this failed on `/sign-up` with a color-contrast violation (ratio 1.18, `#f4e9e9` on white) on Clerk's `#error-password` text. That colour is part-way through a fade-in, so axe runs while Clerk's field error is still animating after the Tab walk | FLAKY |
| C27 | Sign out >= 44x44, Tab-reachable, axe 0, desktop + 375 | PW-1/2/3 `C27 sign out reachable` passed | `frontend/e2e/auth.spec.ts:165-166`, `:181-182` - `toBeGreaterThanOrEqual(44)`; `:167`, `:183` - `tabTo(...)`; `:169`, `:185` - `violations).toEqual([])` | PASS |
| C28 | existing 5 specs pass signed in | **Green in 1 of 4 runs** that included them: PW-1 fail, PW-2 fail, PW-4 fail, PW-5 pass | `frontend/e2e/shell.spec.ts:70` - `expect(page.locator('main h1')).toHaveText(title)`; `:293` - same, the line PW-1 failed on (received "We couldn't load this page"); `:279` - `expect(skip).toBeFocused()`, the line PW-2 failed on (page was `/sign-in`); `frontend/e2e/dev-components.spec.ts:237` - toast `toHaveCount(0)` failed in PW-4 | FLAKY |
| C29 | each rejected case in C2-C7 logs one `auth.rejected` with the listed reason, no token | pytest A `test_rejected_logs_reason[12 ids]` PASSED | `services/core/tests/test_auth.py:257` - `len(rejected) == 1`; `:258` - `rejected[0]["reason"] == reason`; `:260`, `:262` - `header not in out`, `secret not in out`. `REJECTIONS` (`:217-234`) has 12 cases. C2-C7 has 13: the C2 `bearer_empty` case (`Authorization: Bearer`, `:109`) is not among them | GAP |
| C30 | accepted request logs no token | pytest A `test_accepted_logs_no_token` PASSED | `services/core/tests/test_auth.py:272` - `status_code == 200`; `:273-274` - `value not in out.out`, `value not in out.err` | PASS |
| C31 | getToken only in lib/api/auth.ts, which has no console/cookies/storage | `proofs.sh c31` -> `PASS c31` | `.specs/features/10-accounts-login/proofs.sh:57` - `[ "$hits" = "frontend/lib/api/auth.ts" ]`; `:59` - fails on `console.\|cookies(\|localStorage\|sessionStorage` | PASS |
| C32 | env examples have the keys; no Clerk key or PEM in tracked or addable files | `proofs.sh c32` -> `PASS c32` | `.specs/features/10-accounts-login/proofs.sh:68`, `:71` - `grep -qxF "$line"`; `:77` - `[ -z "$leaks" ]` over `git ls-files -co --exclude-standard` (`:75`) | PASS |
| C33 | CI run on the pushed commit: jobs web and api succeed | **not run**: nothing is pushed, and pushing needs the user's go-ahead | no evidence - `.specs/features/10-accounts-login/proofs.sh` c33 needs `origin/development` to carry the feature commit | NOT RUN |
| C34 | every layout/page outside root, sign-in and sign-up has `await auth.protect()`; proxy has no createRouteMatcher; >= 8 files | vitest `every page protected` passed | `frontend/tests/auth-protect.test.ts:23` - `files.length).toBeGreaterThanOrEqual(8)`; `:27` - `expect(unprotected).toEqual([])`; `:30` - `expect(proxy).not.toMatch(/createRouteMatcher/)` | PASS |

## Level and sampling judgments

- **C8:** table-driven over every `/v1` route that exists today. I confirmed that on FastAPI 0.142.2 `app.routes` holds the `/v1` router as an opaque `_IncludedRouter`, while `app.openapi()["paths"]` lists `/v1/me`, `/healthz/live` and `/healthz/ready`. So the handoff's substitution of OpenAPI paths for `app.routes` is real, and the table is complete for the current set. The loop is over methods, so it would also catch a second method on a path. Residual risk: a future `/v1` route with `include_in_schema=False` would drop out of the table. It would still be guarded, because door 3 attaches `Depends(current_user)` to the router itself (`services/core/app/main.py:45-51`). `/healthz/ready` is open without a token according to the existing `services/core/tests/test_health.py:56`, which sends no token, but C8 does not name it although AC 8 does. These are notes, not failures.
- **C12:** two threads, each with its own session, wait on one barrier and then call `get_or_create_user`. The race is resolved by `INSERT ... ON CONFLICT DO NOTHING` (`services/core/app/modules/accounts/repository.py:13`) against `uq_users_clerk_user_id` (`services/core/migrations/versions/07f1bcba78b6_create_users.py:35`). The barrier lines the two threads up, but nothing forces their inserts to overlap. A naive select-then-insert might still pass on a run where one thread commits before the other selects. The proof meets its literal claim, but it is probabilistic evidence for "enforced by the unique constraint". Under light, no mutant was run to measure this.
- **C20:** the users row for the test user has `created_at` 2026-10-02 21:58:46 UTC, about 20 minutes before this verification's first run. The proof would therefore pass on a row from an earlier run, even if the shell had stopped sending the token. This is a precision gap in the proof: it should delete the row first, or assert `created_at` after the sign-in. Evidence from this round that tokens currently reach the API comes from elsewhere. In PW-5 (and PW-3), `shell.spec.ts:70` saw page headings rather than the error state, which needs `/v1/me` to return 200 (`frontend/app/(app)/layout.tsx` `loadMe`).
- **C18:** `toContainText(fullName)` would pass trivially if `fullName` were `""`. I checked through the Clerk Backend API, without printing any values, that the test user has a non-empty first name and a non-empty last name, so the proof is meaningful today. The test does not assert that the name is non-empty, which is a precision note.
- **C34:** the test would fail if any of the 8 files lost `await auth.protect()`, because each file is checked for that substring (`frontend/tests/auth-protect.test.ts:25`). Today every hit is a real call, not a comment, so a deletion is caught. Limits:
  - A comment containing the string would satisfy the check.
  - It does not check door 7's "before anything else".
  - It scans only `page.tsx` and `layout.tsx`, so `route.ts` handlers and server actions are out of reach. `frontend/app/dev/sentry-check/actions.ts` (spec 07, not in this diff) is a server action with no auth check and no production gate of its own. Server actions are reachable as POST requests regardless of the page's `auth.protect()`. This is out of this feature's scope but worth a note for spec 11 onward.
- **C29:** the Coverage row "`missing` C29 (no/malformed header)" sits under a claim that says "each rejected case in C2-C7". The `bearer_empty` member has no C29 case. The code path is the same `credentials is None -> "missing"` (`services/core/app/auth.py:39`) as `no_header`, so the risk is low. Still, the claim covers a member its proof never exercises.
- **C26 and C28 flakiness:**
  - The C28 failures fall into two kinds. Three are new failure modes added by this feature:
    - PW-1's shell page showed the `(app)` error state while signed in. `/v1/me` failed for one render, for example a token accepted at the edge of its 60 s life by Next and then rejected by the API, or a refresh that failed. The logs do not say which; this is a hypothesis, not a confirmed cause.
    - PW-1's `current link (C4)`: its nav locator found no element.
    - PW-2's shared signed-in session ended up on `/sign-in` partway through the run.
  - PW-4's toast-duration failure is a timing-sensitive test from spec 06 that this diff did not touch, failing under suite load.
  - With repeated runs each failing a different test, "the specs that existed before this feature pass when signed in" is not reliably true at HEAD.
- **Changed tests, adapted or weakened:**
  - **`frontend/tests/dev-gate.test.ts`:** adapted. The page became `async`. The production case still asserts digest `NEXT_HTTP_ERROR_FALLBACK;404`. The development case moved from `not.toThrow()` to `resolves.toBeDefined()`, which is equivalent or stronger for a promise. The only addition is an `auth.protect` mock, and it runs after the gate under test.
  - **`frontend/tests/api-check-page.test.tsx`:** adds only the Clerk mock. No assertion changed.
  - **`frontend/e2e/shell.spec.ts`:** the copy check now skips `[data-user-content]`. Only the two `userName` spans carry that attribute (`frontend/components/shell/app-header.tsx:47`, `frontend/components/shell/mobile-menu.tsx:38`), so the exemption covers user data, not interface text. Adapted.
  - **`services/core/tests/test_migrations.py`:** `downgrade -1` became `downgrade base` in the audit_log test, because a second revision now sits on top. Its assertions (`"audit_log" not in tables`, `function is None`) are unchanged, and it passed at HEAD. Adapted.

## Swept re-read

- **validation, failure modes, idempotency, authorization, observability:** each cited check is in the table above, with the results shown there.
- **concurrency (C12):** the cited constraint exists: `uq_users_clerk_user_id` at `services/core/migrations/versions/07f1bcba78b6_create_users.py:35`, used by `on_conflict_do_nothing` at `services/core/app/modules/accounts/repository.py:13`.
- **dependency failure (C1, no network call to Clerk):** confirmed in the code, not in C1's test. `services/core/app/auth.py:42` calls `jwt.decode(credentials.credentials, settings.clerk_jwt_key, ...)` with the PEM key from settings, and nothing fetches a JWKS.
- **data lifecycle:** `n/a`, which is policy the user approved.

## Gate

- **pytest:** 40 passed, 0 failed (plus `test_audit_log_upgrade_downgrade_and_check`, 1 passed).
- **vitest:** 16 passed, 0 failed.
- **proofs.sh:** c15, c20, c31 and c32 all PASS.
- **Playwright `auth.spec.ts`:** 10 passed in PW-3. C26 failed once, in PW-2.
- **Playwright C28 set:** green in 1 of 4 runs.
- **C33:** not run.
- **Real tree:** `git status --porcelain` was empty before and after.

## Ranked gaps

1. **C28 is flaky at HEAD.**
   - It was green in only 1 of 4 runs, and 3 of its failures came from new authentication failure modes: the error state while signed in, and the session lost during the run.
   - Settling lines: `frontend/e2e/shell.spec.ts:293` and `frontend/e2e/shell.spec.ts:279`.
   - Fix: find out why `/v1/me` or the shared session fails intermittently, then make the suite reliably green.
2. **C33 was not run.** CI on the pushed commit is unproven until the user approves the push. See `.specs/features/10-accounts-login/proofs.sh` c33.
3. **C26 is flaky.** axe runs while Clerk's sign-up field error is still fading in (`frontend/e2e/auth.spec.ts:116`). Fix: wait for animations to settle after the Tab walk, before running axe.
4. **C29 has a coverage gap.** The C2 `bearer_empty` case is missing from `REJECTIONS` (`services/core/tests/test_auth.py:217`).
5. **Precision gaps that do not block:**
   - C20 passes on a row left by an earlier run (`.specs/features/10-accounts-login/proofs.sh:49`).
   - C12's overlap is not forced (`services/core/tests/test_accounts.py:67`).
