# 10 - Login with Clerk verification

**Verdict**: PASS
**Profile**: light
**Diff range**: c4aa31f..990e12a (`development` = `origin/development` = `990e12a`); round 3 fix diff 02ab1d3..990e12a
**Round**: 3 - scoped
**Verifier**: independent sub-agent (author != verifier)

**34 of 34 checks are proven at `990e12a`.** C33 now runs: the CI run on `990e12a` has jobs `web` and `api`, and both concluded `success`.

The history is recorded honestly. The previous push, `e56a9db`, failed CI (`api: failure`, `web: success`). Its failed-job log contains `relation "users" does not exist` 84 times, which matches the cause the coordinator reported. The fix in `990e12a` changes test setup only. No assertion in C1-C13, C29 or C30 changed.

## Fix diff reviewed (verified at 990e12a)

### What changed

- **`services/core/tests/conftest.py`** adds a session-scoped fixture, `migrated_database`. It:
  - creates a fresh `headroom_test_<hex>` database;
  - runs `alembic upgrade head` on it, and asserts the return code is 0;
  - points `DATABASE_URL` at it and clears the `get_settings`, `get_engine` and `get_sessionmaker` caches;
  - on teardown, restores the previous `DATABASE_URL`, clears the caches again and runs `DROP DATABASE ... WITH (FORCE)`.
- **`services/core/tests/test_auth.py`** and **`services/core/tests/test_accounts.py`** each add only the line `pytestmark = pytest.mark.usefixtures("migrated_database")`, plus a comment.
  - `git diff 02ab1d3..990e12a` shows no other change to either file.
  - Every assertion is byte-identical. Their line numbers shifted by +3, and the citations below are refreshed.
- **`checks.md`** gains one Handoff line, "Settled after push". It describes the fix. No check text changed.

### Does the fixture weaken or change C1-C13, C29 or C30?

No.

- **C1-C9, C29, C30** (the token and log checks in `test_auth.py`):
  - These tests never read the database directly. The fixture only decides which database the `get_or_create_user` call on the accepted path writes to.
  - The 401 paths stop before any database access. `current_user` depends on `verified_clerk_user_id`, and that raises first (`services/core/app/auth.py:39-59`).
- **C10-C13** (the row checks in `test_accounts.py`):
  - The request goes through `TestClient(app)`, which resolves `get_session` through the same cached `get_sessionmaker`. The test's own `rows_for` and the `sub` cleanup use that same sessionmaker. So the request and the count read one database.
  - The fixture is stricter than before. The database is empty and at Alembic head for each session. C13's fixed `sub`, `user_test_rejected`, can no longer find a leftover row from an earlier run.
- **C12** still gives each thread its own session from the same sessionmaker, and `uq_users_clerk_user_id` exists in the fresh database through the real migration.
- **C14** keeps its own empty database (`empty_database_url`). The fixture does not touch it.
- **C20's proof** reads the configured `headroom` database through `proofs.sh`. The fixture does not run there, so C20 is unchanged.
- **No leftover databases:** after this round's pytest run, `SELECT datname FROM pg_database WHERE datname LIKE 'headroom_test_%'` returned no rows.

## Checks

### How the proofs ran (all verified at 990e12a)

- **pytest:** `uv run pytest tests/test_auth.py tests/test_accounts.py tests/test_settings.py tests/test_migrations.py -v -k "<the 17 proof keywords>"`.
  - Exit 0, 41 passed, each test named, the same set as round 2.
  - This time the fixture created, migrated and dropped its own database.
- **vitest:** `npx vitest run tests/user-name.test.ts tests/api-auth.test.ts tests/app-layout.test.tsx tests/auth-protect.test.ts tests/clerk-appearance.test.ts --reporter=verbose`.
  - Exit 0, 11 passed, each named.
- **`proofs.sh`:**
  - `bash proofs.sh c15 c31 c32` exited 0.
  - `bash proofs.sh c20`, run after R3-1 (which includes C18), printed `PASS c20`.
  - `C33_SHA=990e12a… bash proofs.sh c33` printed `PASS c33` and exited 0.
- **Playwright:**
  - **R3-1:** `NEXT_PUBLIC_SENTRY_DSN= npx playwright test e2e/auth.spec.ts` plus the 5 older specs. Exit 0, 82 passed. All 8 `auth.spec.ts` tests appear individually: C16, C17, C25, C26, C18, C23, C24 and C27.
  - **R3-2:** the C28 command exactly as written. Exit 0, 74 passed.
- **CI** (`gh run list --workflow CI --branch development`):
  - `990e12a`: completed, success, run 37075474479. Jobs: `web success`, `api success`.
  - `e56a9db`: completed, failure, run 37075194958. Jobs: `api failure`, `web success`.

The evidence cells below refer to these runs by name.

### Results

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | valid RS256 token -> 200, keys exactly id/clerk_user_id/created_at | pytest PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:102` - `set(body) == {"id", "clerk_user_id", "created_at"}`; `:103` - `body["clerk_user_id"] == "user_test_c1"`; `:104` - `uuid.UUID(body["id"])` | PASS |
| C2 | 4 missing or malformed headers -> problem 401 + `WWW-Authenticate: Bearer` | pytest 4 ids PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:45-52` (`assert_rejected` at `:44`) - `status_code == 401`, `content-type == "application/problem+json"`, `www-authenticate == "Bearer"`, `title == "Unauthorized"`, `detail == "Authentication required."`, `instance == "/v1/me"`; called at `:121` | PASS |
| C3 | exp -10s rejected, exp -3s accepted | pytest PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:128` - `assert_rejected(...)`; `:135` - `.status_code == 200` | PASS |
| C4 | other key, altered payload -> 401 | pytest 2 ids PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:141` - `assert_rejected(...)` | PASS |
| C5 | none, HS256 with PEM, RS512 -> 401 | pytest 3 ids PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:153` - `assert_rejected(...)` | PASS |
| C6 | nbf +10s, no sub -> 401 | pytest PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:160`, `:164` - `assert_rejected(...)` | PASS |
| C7 | azp foreign 401 / listed 200 / absent 200 / list empty 200 | pytest 4 PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:171` - `assert_rejected`; `:178`, `:183` - `== 200`; `:187` - `clerk_authorized_parties == []`; `:190` - `== 200` | PASS |
| C8 | every /v1 route 401 without token; /healthz/live 200 | pytest PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:201` - `"/v1/me" in v1`; `:206` - `response.status_code == 401, (method, path)`; `:208` - `/healthz/live ... == 200` | PASS |
| C9 | missing CLERK_JWT_KEY -> ValidationError naming it; parties parsing | pytest 3 PASSED (verified at 990e12a) | `services/core/tests/test_settings.py:67` - `"clerk_jwt_key" in str(excinfo.value)`; `:87` - `Settings().clerk_authorized_parties == parsed` | PASS |
| C10 | first request -> exactly 1 row, id matches | pytest PASSED (verified at 990e12a) | `services/core/tests/test_accounts.py:47` - `rows_for(sub) == 1`; `:50` - `str(user.id) == response.json()["id"]` | PASS |
| C11 | 3 sequential calls -> same id, 1 row | pytest PASSED (verified at 990e12a) | `services/core/tests/test_accounts.py:58` - `len(ids) == 1`; `:59` - `rows_for(sub) == 1` | PASS |
| C12 | two threads released by one barrier -> same id, no error, 1 row | pytest PASSED (verified at 990e12a) | `services/core/tests/test_accounts.py:81` - `errors == []`; `:83` - `results[0] == results[1]`; `:84` - `rows_for(sub) == 1` | PASS |
| C13 | rejected request leaves 0 rows | pytest PASSED (verified at 990e12a) | `services/core/tests/test_accounts.py:95` - `rows_for(sub) == 0` (status 401 asserted on the line before) | PASS |
| C14 | users schema exact, downgrade removes it, check clean | pytest PASSED (verified at 990e12a) | `services/core/tests/test_migrations.py:128` - the exact column set; `:133` - pk and `uq_users_clerk_user_id`; `:145` - `"users" not in tables`; `:150` - `check` returncode 0 | PASS |
| C15 | module files, docstring, no cross-module import | `proofs.sh c15` PASS (verified at 990e12a) | `.specs/features/10-accounts-login/proofs.sh:19`, `:25`, `:27` | PASS |
| C16 | 5 protected paths -> /sign-in signed out | R3-1 passed (verified at 990e12a) | `frontend/e2e/auth.spec.ts:53` - `expect.poll(() => pathOf(page), { message: path }).toBe('/sign-in')` | PASS |
| C17 | /sign-in, /sign-up 200, form, no shell | R3-1 passed (verified at 990e12a) | `frontend/e2e/auth.spec.ts:63` - `toBe(200)`; `:66` - `getByTestId('shell') ... toHaveCount(0)` | PASS |
| C18 | signed in, shell + full name from Clerk | R3-1 passed (verified at 990e12a) | `frontend/e2e/auth.spec.ts:128` - `getByTestId('header-user')).toContainText((await testUser()).fullName)` | PASS |
| C19 | display name full name / email fallback | vitest passed (verified at 990e12a) | `frontend/tests/user-name.test.ts:31` - `toBe('Ada Lovelace')`; `:36` - `toBe('ada@example.test')` | PASS |
| C20 | after sign-in, exactly 1 users row for the test user's Clerk ID | `proofs.sh c20` after R3-1, PASS (verified at 990e12a) | `.specs/features/10-accounts-login/proofs.sh:49` - `[ "$rows" = "1" ]` | PASS |
| C21 | authHeaders -> `{Authorization: "Bearer tok_abc"}`; null rejects; no console | vitest passed (verified at 990e12a) | `frontend/tests/api-auth.test.ts:39` - `toEqual({ Authorization: 'Bearer tok_abc' })`; `:47` - `rejects.toThrow()`; `:40`, `:48` - `not.toHaveBeenCalled()` | PASS |
| C22 | /v1/me 401 or rejected -> errorTitle, no children | vitest passed (verified at 990e12a) | `frontend/tests/app-layout.test.tsx:47`, `:56` - `getByText(messages.States.errorTitle)`; `:48`, `:57` - `queryByText('page content')).toBeNull()` | PASS |
| C23 | desktop sign out -> /sign-in, / again -> /sign-in | R3-1 passed (verified at 990e12a) | `frontend/e2e/auth.spec.ts:140`, `:143` - `toBe('/sign-in')` | PASS |
| C24 | 375px: name + Sign out in Dialog, -> /sign-in | R3-1 passed (verified at 990e12a) | `frontend/e2e/auth.spec.ts:152` - `toContainText(fullName)` inside `dialog`; `:155` - `toBe('/sign-in')` | PASS |
| C25 | primary button bg == --accent; form font is Plex | R3-1 passed (verified at 990e12a) | `frontend/e2e/auth.spec.ts:86` - `expect(buttonBackground).toBe(accent)`; `:96` - `formFont.split(',')[0].trim()).toBe(plexFamily)` | PASS |
| C26 | auth pages at 375: no overflow, Tab order, axe 0 | R3-1 passed (verified at 990e12a) | `frontend/e2e/auth.spec.ts:110` - `toBeLessThanOrEqual(375)`; `:112-113` - `tabTo`; `:118` - `axe.violations ... toEqual([])` | PASS |
| C27 | Sign out >= 44x44, Tab-reachable, axe 0, desktop + 375 | R3-1 passed (verified at 990e12a) | `frontend/e2e/auth.spec.ts:167-168`, `:183-184` - `toBeGreaterThanOrEqual(44)`; `:171`, `:187` - `violations).toEqual([])` | PASS |
| C28 | existing 5 specs pass signed in | R3-1 (superset) and R3-2 (the exact command) both exit 0; 6 of 6 green runs across rounds 2 and 3 (verified at 990e12a) | `frontend/e2e/shell.spec.ts:70` - `expect(page.locator('main h1')).toHaveText(title)`; `:293` - same at 375 and 1440; `:279` - `expect(skip).toBeFocused()` | PASS |
| C29 | each of the 13 rejected cases in C2-C7 logs one `auth.rejected` with the listed reason, no token | pytest 13 ids PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:220` - `REJECTIONS` with 13 cases; `:261` - `len(rejected) == 1`; `:262` - `rejected[0]["reason"] == reason`; `:264`, `:266` - `header not in out`, `secret not in out` | PASS |
| C30 | accepted request logs no token | pytest PASSED (verified at 990e12a) | `services/core/tests/test_auth.py:277-278` - `value not in out.out`, `value not in out.err` | PASS |
| C31 | getToken only in lib/api/auth.ts, which has no console/cookies/storage | `proofs.sh c31` PASS (verified at 990e12a) | `.specs/features/10-accounts-login/proofs.sh:57`, `:59` | PASS |
| C32 | env examples have the keys; no Clerk key or PEM in tracked or addable files | `proofs.sh c32` PASS (verified at 990e12a) | `.specs/features/10-accounts-login/proofs.sh:68`, `:71`, `:77` | PASS |
| C33 | CI run for the pushed commit on development: jobs web and api, both success | `C33_SHA=990e12a bash proofs.sh c33` printed `PASS c33`, exit 0; `gh run view 37075474479` shows `web success`, `api success` (verified at 990e12a) | `.specs/features/10-accounts-login/proofs.sh:101` - `[ "$(job_names "$jobs")" = "api,web" ]` (the job names must be exactly api and web); `:102-103` - `job_conclusion ... = "success"` for web and api | PASS |
| C34 | every layout/page outside root, sign-in and sign-up has `await auth.protect()`; proxy has no createRouteMatcher; >= 8 files | vitest passed (verified at 990e12a) | `frontend/tests/auth-protect.test.ts:23` - `toBeGreaterThanOrEqual(8)`; `:27` - `expect(unprotected).toEqual([])`; `:30` - `not.toMatch(/createRouteMatcher/)` | PASS |

### C33 history

- **`e56a9db` (CI run 37075194958):** jobs `api failure` and `web success`. Its `--log-failed` output contains `relation "users" does not exist` 84 times.
- **`990e12a` (CI run 37075474479):** jobs `web success` and `api success`.
- **Proof scope:** the default for `proofs.sh c33` is `origin/development`, which equals `990e12a`. The proof was run with `C33_SHA` set to that same commit.

## Level and sampling judgments

These are carried from e01daa9 and 02ab1d3. The round 3 diff touched none of their code.

### Notes that do not block

- **C8:** the route table is read from the OpenAPI paths.
  - A future `/v1` route marked `include_in_schema=False` would drop out of the table.
  - Such a route would still be guarded by the router-level dependency (`services/core/app/main.py:45-51`).
- **C12:** the barrier releases both threads together, but nothing forces their writes to overlap. The proof is probabilistic.
- **C20:** the proof would also pass on a row left by an earlier run. In round 2 the API log showed `/v1/me` returning 200 throughout, which is separate evidence that verified tokens reached the API.
- **C34:** a substring check.
  - It does not scan `route.ts` handlers or server actions.
  - `frontend/app/dev/sentry-check/actions.ts` (spec 07, outside this diff) has no auth check.
- **C28 residual (from round 2):** the refresh for a token about to expire is proven at unit level (`frontend/tests/api-auth.test.ts:62-63`). The slow-render condition from round 1 was not recreated end to end.

### Tests changed in earlier rounds

Carried from e01daa9 and 02ab1d3. Each one was adapted, not weakened.

## Swept re-read

Carried from e01daa9.

- `uq_users_clerk_user_id` is at `services/core/migrations/versions/07f1bcba78b6_create_users.py:35`.
- `on_conflict_do_nothing` is at `services/core/app/modules/accounts/repository.py:13`.
- Verification uses the local PEM, with no call to Clerk: `services/core/app/auth.py:42`.
- The fresh database in round 3 is built by that same migration, so the constraint C12 relies on is present there.

## Gate

Verified at 990e12a.

- **pytest:** 41 passed, 0 failed.
- **vitest:** 11 passed, 0 failed.
- **`proofs.sh`:** c15, c20, c31, c32 and c33 all PASS.
- **Playwright:** 82 passed, then 74 passed, with 0 failed.
- **CI on `990e12a`:** web success, api success.
- **Real tree:** clean apart from this report.
