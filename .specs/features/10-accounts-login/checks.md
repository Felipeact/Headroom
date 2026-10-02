# 10 - Login with Clerk checks

Profile: light
Plan: `.specs/features/10-accounts-login/plan.md`

34 checks in 4 slices · 8 one-way doors · 2 open, of which 0 block the build (staging variables block go-live; C33 needs the push go-ahead and the CI secret)

Commands run from `services/core/` (`uv run pytest ...`) or `frontend/` (`npx vitest run <file> -t "<name>"`, `npx playwright test <file> -g "<name>"`). `bash .specs/features/10-accounts-login/proofs.sh <cNN>` runs from anywhere in the repo. The DB-backed pytest tests and Playwright need a Postgres on `localhost:5432` with database `headroom` (CI has one; locally a portable Postgres in the scratchpad). Playwright starts the web app on 3000 and the API on 8100, and signs in through `@clerk/testing` with `E2E_CLERK_USER_USERNAME` / `E2E_CLERK_USER_PASSWORD` from `frontend/.env.local`. API tests sign tokens with an RSA key pair generated per test session; they never call Clerk.

## Checks

### S1 - The API knows who is calling · 8 files · 40 KB · ~10k

**C1** - `GET /v1/me` with an RS256 token signed by the test key whose public PEM is `CLERK_JWT_KEY`, `exp` 60s ahead, `sub` `user_test_c1`, returns `200` with JSON keys exactly `id`, `clerk_user_id`, `created_at`, where `clerk_user_id` is `user_test_c1` and `id` parses as a UUID (AC 1, door 2)
Proof: `uv run pytest tests/test_auth.py -k "valid_token_returns_me"`

**C2** - Each of: no `Authorization` header, `Basic dXNlcjpwdw==`, `Bearer` with nothing after it, and a valid token sent without the `Bearer ` prefix, returns `401` with `Content-Type` `application/problem+json`, body `status` `401`, `title` `Unauthorized`, `detail` `Authentication required.`, `instance` `/v1/me`, and header `WWW-Authenticate: Bearer` (AC 2, door 2)
Proof: `uv run pytest tests/test_auth.py -k "missing_or_malformed_header"`

**C3** - A token with `exp` 10s in the past returns the C2 `401`; a token with `exp` 3s in the past returns `200` (the 5-second leeway) (AC 3, door 2)
Proof: `uv run pytest tests/test_auth.py -k "expired"`

**C4** - A token signed by a second, unrelated RSA key, and a valid token whose payload segment is replaced with one carrying a different `sub` (signature kept), each return the C2 `401` (AC 4, door 2)
Proof: `uv run pytest tests/test_auth.py -k "bad_signature"`

**C5** - Tokens with `alg` `none` (unsigned), `HS256` signed with the public PEM as the HMAC secret, and `RS512` signed by the test key each return the C2 `401` (AC 5, door 2)
Proof: `uv run pytest tests/test_auth.py -k "wrong_algorithm"`

**C6** - A token with `nbf` 10s in the future, and a token with no `sub` claim, each return the C2 `401` (AC 6, door 2)
Proof: `uv run pytest tests/test_auth.py -k "nbf_or_sub"`

**C7** - With `CLERK_AUTHORIZED_PARTIES=http://localhost:3000,https://app.test`: `azp` `https://evil.test` returns the C2 `401`; `azp` `https://app.test` returns `200`; no `azp` returns `200`. With `CLERK_AUTHORIZED_PARTIES` empty, `azp` `https://evil.test` returns `200` (AC 7, door 2)
Proof: `uv run pytest tests/test_auth.py -k "authorized_parties"`

**C8** - For every route in `app.main.app.routes` whose path starts with `/v1` (at least one: `/v1/me`), a request without a token returns `401`; `/healthz/live` without a token returns `200` (AC 8, door 3)
Proof: `uv run pytest tests/test_auth.py -k "every_v1_route_requires_token"`

**C9** - `Settings()` with no `CLERK_JWT_KEY` in the environment or env file raises `ValidationError` naming `clerk_jwt_key`; `CLERK_AUTHORIZED_PARTIES=http://a.test, https://b.test` parses to `["http://a.test", "https://b.test"]`, and unset parses to `[]` (Impact: configuration, AD-001)
Proof: `uv run pytest tests/test_settings.py -k "clerk"`

### S2 - First sign-in creates the user · 6 files · 25 KB · ~6k

**C10** - The first `GET /v1/me` with a `sub` not in `users` leaves exactly `1` row with that `clerk_user_id`, whose `id` equals the response `id` (AC 9, door 1)
Proof: `uv run pytest tests/test_accounts.py -k "first_request_creates_user"`

**C11** - Three sequential `GET /v1/me` calls with the same `sub` return the same `id` and leave exactly `1` row for that `sub` (AC 10)
Proof: `uv run pytest tests/test_accounts.py -k "repeat_requests_reuse_user"`

**C12** - Two threads released by one barrier each call `accounts.service.get_or_create_user` with their own session and the same new `clerk_user_id`; both return the same `id`, neither raises, and exactly `1` row exists (AC 10, door 1)
Proof: `uv run pytest tests/test_accounts.py -k "concurrent_first_requests"`

**C13** - A `GET /v1/me` rejected with `401` (expired token, `sub` `user_test_rejected`) leaves `0` rows with that `clerk_user_id` (AC 11)
Proof: `uv run pytest tests/test_accounts.py -k "rejected_request_creates_nothing"`

**C14** - After `alembic upgrade head` on an empty database, the schema has table `users` with columns exactly `id` (`uuid`, primary key), `clerk_user_id` (`text`, not null), `created_at` (`timestamp with time zone`, not null), and a unique constraint named `uq_users_clerk_user_id` on `clerk_user_id`; `alembic downgrade -1` removes the table; `alembic check` reports no differences at head (AC 20, door 1, AD-003)
Proof: `uv run pytest tests/test_migrations.py -k "users_table"`

**C15** - `app/modules/accounts/` has `api.py`, `service.py`, `models.py`, `repository.py`; `service.get_or_create_user` has a docstring; no file under `app/modules/accounts/` imports from another `app.modules.*` package (door 4)
Proof: `bash .specs/features/10-accounts-login/proofs.sh c15`

### S3 - Sign in, see the shell, sign out · 14 files · 60 KB · ~15k

**C16** - Without a session, each of `/`, `/alerts`, `/expected-payments`, `/settings`, `/dev/components` ends on a URL whose path is `/sign-in` (AC 12, door 5)
Proof: `npx playwright test e2e/auth.spec.ts -g "signed out redirects"`

**C17** - Without a session, `/sign-in` and `/sign-up` each answer `200`, show a Clerk form with an identifier input and a `Continue` button, and contain no `[data-testid="shell"]` (AC 13, door 5)
Proof: `npx playwright test e2e/auth.spec.ts -g "auth pages without shell"`

**C18** - After signing in as the test user, `/` shows `[data-testid="shell"]` and the header shows the test user's full name (first and last name, read from the Clerk Backend API in the test setup) (AC 14)
Proof: `npx playwright test e2e/auth.spec.ts -g "shows the name"`

**C19** - With `currentUser()` mocked: first `Ada` last `Lovelace` gives `Ada Lovelace`; no names and primary email `ada@example.test` gives `ada@example.test` (AC 14)
Proof: `npx vitest run tests/user-name.test.ts -t "display name"`

**C20** - After the C18 sign-in, `users` holds exactly `1` row whose `clerk_user_id` is the test user's Clerk ID, so the shell's `/v1/me` call carried a token the API verified (AC 15, door 6)
Proof: `bash .specs/features/10-accounts-login/proofs.sh c20`

**C21** - `authHeaders()` with Clerk's `auth()` mocked so `getToken()` resolves `tok_abc` returns exactly `{ Authorization: "Bearer tok_abc" }`; when `getToken()` resolves `null` it rejects, and neither case calls `console` (AC 15, AC 23, door 6)
Proof: `npx vitest run tests/api-auth.test.ts -t "authHeaders"`

**C22** - The `(app)` layout, with `api.GET("/v1/me")` mocked to return status `401`, and again mocked to reject, renders `States.errorTitle` (`We couldn't load this page`) and does not render its children (AC 16)
Proof: `npx vitest run tests/app-layout.test.tsx -t "me fails"`

**C23** - Signed in at desktop width, activating `Sign out` ends on a URL whose path is `/sign-in`, and a following visit to `/` again ends on `/sign-in` (AC 17)
Proof: `npx playwright test e2e/auth.spec.ts -g "sign out desktop"`

**C24** - Signed in at 375px, the name and `Sign out` are inside the phone menu Dialog; activating `Sign out` there ends on `/sign-in` (AC 17, AC 19)
Proof: `npx playwright test e2e/auth.spec.ts -g "sign out phone"`

**C25** - On `/sign-in`, Clerk's primary button has computed `background-color` equal to the `--accent` token's computed value, and the form's computed `font-family` starts with the IBM Plex Sans family that `next/font` registers (AC 18, door 5, AD-012)
Proof: `npx playwright test e2e/auth.spec.ts -g "themed with tokens"`

**C26** - On `/sign-in` and `/sign-up` at 375px, `document.documentElement.scrollWidth` is at most `375`; pressing Tab from the page start reaches the identifier input and then the `Continue` button; axe reports `0` violations (AC 18)
Proof: `npx playwright test e2e/auth.spec.ts -g "auth pages 375 keyboard axe"`

**C27** - Signed in, at desktop width and at 375px (menu open), the `Sign out` control's bounding box is at least `44` by `44` px, it is reachable by Tab alone, and axe reports `0` violations on `/` (AC 19)
Proof: `npx playwright test e2e/auth.spec.ts -g "sign out reachable"`

**C28** - The specs that existed before this feature (`shell`, `home`, `api-check`, `dev-components`, `sentry-check`) pass when signed in as the test user (Impact: web routing)
Proof: `npx playwright test e2e/shell.spec.ts e2e/home.spec.ts e2e/api-check.spec.ts e2e/dev-components.spec.ts e2e/sentry-check.spec.ts`

**C34** - Every `layout.tsx` and `page.tsx` under `frontend/app/`, except `app/layout.tsx` and the files under `app/sign-in/` and `app/sign-up/`, contains `await auth.protect()`; `proxy.ts` does not import `createRouteMatcher`; the test sees at least `8` files: the `(app)` layout, its 4 pages and the 3 `app/dev/` pages (door 7, added mid-build)
Proof: `npx vitest run tests/auth-protect.test.ts -t "every page protected"`

### S4 - Nothing secret is kept · 4 files · 15 KB · ~4k

**C29** - For each rejected case in C2-C7, captured log output contains one `auth.rejected` event whose `reason` is `missing`, `expired`, `invalid` or `unauthorized_party` as listed in Coverage, and contains neither the token string nor the `Authorization` header value (AC 21, door 2)
Proof: `uv run pytest tests/test_auth.py -k "rejected_logs_reason"`

**C30** - For an accepted `GET /v1/me`, no captured log line contains the token string (AC 22)
Proof: `uv run pytest tests/test_auth.py -k "accepted_logs_no_token"`

**C31** - Among `git ls-files frontend`, `getToken` appears only in `frontend/lib/api/auth.ts`, which contains no `console.`, `cookies(`, `localStorage` or `sessionStorage` (AC 23)
Proof: `bash .specs/features/10-accounts-login/proofs.sh c31`

**C32** - `frontend/.env.example` has `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=`, `CLERK_SECRET_KEY=`, `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`; `services/core/.env.example` has `CLERK_JWT_KEY=` and `CLERK_AUTHORIZED_PARTIES=`; no file in `git ls-files -co --exclude-standard` (tracked, plus untracked-not-ignored) contains a Clerk key (`sk_test_`, `sk_live_`, `pk_test_` or `pk_live_` followed by at least 20 key characters) or a PEM line (`-----BEGIN` then `PUBLIC KEY-----`, `PRIVATE KEY-----` or the `RSA` forms) (Impact: configuration, L-006)
Proof: `bash .specs/features/10-accounts-login/proofs.sh c32`

**C33** - The CI run for the pushed feature commit on `development` has jobs `web` and `api`, both concluding `success` (Impact: CI, AD-004)
Proof: `bash .specs/features/10-accounts-login/proofs.sh c33`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /v1/me` statuses (2) | 200 C1 · 401 C2 | - |
| token rejection causes (11) | missing header C2 · malformed header C2 · expired C3 · other key C4 · altered payload C4 · `none` C5 · `HS256` C5 · `RS512` C5 · `nbf` future C6 · no `sub` C6 · foreign `azp` C7 | - |
| leeway edges (2) | 3s past accepted C3 · 10s past rejected C3 | - |
| `azp` cases (4) | listed C7 · foreign C7 · absent C7 · list empty C7 | - |
| `auth.rejected` reasons (4) | `missing` C29 (no/malformed header) · `expired` C29 (C3) · `invalid` C29 (C4-C6) · `unauthorized_party` C29 (C7) | - |
| routes and auth (2 kinds) | every `/v1/*` C8, table-driven over `app.routes` · `/healthz/live` open C8 | - |
| doors (8) | 1 `users` C10 C12 C14 · 2 verification C1-C7 · 3 `/v1` router C8 · 4 module layout C15 · 5 Clerk web C16 C17 C25 · 6 token headers C20 C21 · 7 per-page protection C16 C34 · 8 token copies C25 | - |
| `users` row lifecycle (4) | first C10 · repeat C11 · concurrent C12 · rejected C13 | - |
| protected pages (5) | `/` C16 · `/alerts` C16 · `/expected-payments` C16 · `/settings` C16 · `/dev/components` C16 | - |
| auth pages (2) | `/sign-in` C17 C25 C26 · `/sign-up` C17 C26 | - |
| name sources (2) | full name C18 C19 · email fallback C19 | - |
| `/v1/me` failures in the shell (2) | non-200 C22 · rejected call C22 | - |
| sign-out placements (2) | desktop header C23 C27 · phone menu C24 C27 | - |
| startup config: `CLERK_JWT_KEY` (3 assemblies) | `Settings` C9 · pytest assembly (conftest env) C1 · Playwright API on 8100 (`.env.local`) C20 | - |
| env examples (2 files) | `frontend/.env.example` C32 · `services/core/.env.example` C32 | - |
| existing e2e specs (5) | `shell` C28 · `home` C28 · `api-check` C28 · `dev-components` C28 · `sentry-check` C28 | - |

- Claims naming a status code, route or response shape: C1, C2, C8 cross the HTTP boundary through `TestClient`; C16-C18, C23-C27 cross it in a browser
- C20 is the only end-to-end proof that the web app sends the token; C21 proves the header shape at its own layer

## Swept

- validation: C2, C5, C6 (malformed header, algorithm, required claims); C9 (settings)
- failure modes: C22 (`/v1/me` fails in the shell); C3, C4 (bad tokens)
- idempotency: C11 (repeat requests reuse the row)
- authorization: C8 (every `/v1` route), C16 (every page); per-business access is spec 11
- concurrency: C12 (two first requests at once, settled by `uq_users_clerk_user_id`)
- data lifecycle: n/a - no deletion, archival or backfill is specified; Clerk user deletion is out of scope in the plan
- dependency failure: C1 (verification needs no network call to Clerk, so a Clerk outage does not fail API requests); C22 (API down)
- state transitions: C16, C18, C23 (signed out -> signed in -> signed out)
- observability: C29 (`auth.rejected` with reason), C30, C31 (no token in logs)

## Handoff

- S1-S4 touch about 20 existing and new files: 66 KB existing (`wc -c` on `main.py`, `settings.py`, `env.py`, `test_migrations.py`, `test_settings.py`, both `.env.example`, both layouts, `error.tsx`, the shell components, the five e2e specs, `playwright.config.ts`, `en.json`, `ci.yml`, `client.ts`) plus about 40 KB new = 106 KB / 4 = ~27k tokens, under the 150k budget - one builder
- Mechanism: one builder
- **Settled mid-build:** C32's secret patterns were literal prefixes, which `checks.md` itself contains; restated before its proof was written as a prefix plus 20+ key characters or a full PEM line, with no folder excluded. C8's route table reads `app.openapi()["paths"]`, because this FastAPI keeps included routers out of `app.routes`
- **Settled mid-build:** Door 7 (user chose per-page `auth.protect()` over the deprecated `createRouteMatcher`), with C34 added for it. The test user signs in through `@clerk/testing`'s email (sign-in token) path: the password path stops at `needs_client_trust`, Clerk's new-device email check, so `E2E_CLERK_USER_PASSWORD` is unused and the user is looked up by `E2E_CLERK_USER_USERNAME`
