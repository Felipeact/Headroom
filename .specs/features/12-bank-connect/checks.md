# 12 - Connect a bank checks

Profile: light
Plan: `.specs/features/12-bank-connect/plan.md`

46 checks in 5 slices · 6 one-way doors · 2 open, of which 1 blocks (open question 2: local sandbox keys arrived 2026-10-04; the staging Railway variables are still the user's)

Commands run from `services/core/` (`uv run pytest ...`) or `frontend/` (`npx vitest run <file> -t "<name>"`, `npx playwright test <file> -g "<name>"`). `bash .specs/features/12-bank-connect/proofs.sh <cNN>` runs from anywhere in the repo. API unit tests use a fake `PlaidClient` through a dependency override and never call Plaid; `tests/conftest.py` sets fake `PLAID_*` values and a generated `TOKEN_ENCRYPTION_KEYS` only when the process env has none. The tests marked `plaid_sandbox` call the real Plaid sandbox, are deselected from the default run, and run through `proofs.sh`, which exports `services/core/.env.local` first; they fail, never skip, when the keys are missing. Playwright starts the web app on 3000 and the API on 8100, the API reading the sandbox keys from `.env.local`.

## Checks

### S1 - The API creates a link token · 6 files · 40 KB · ~10k

**C1** - As the owner, `POST /v1/businesses/{business_id}/bank/link-token` with the fake returning `link_token` `"link-sandbox-123"` and `expiration` `2026-10-04T16:00:00Z` returns `200` with JSON keys exactly `link_token`, `expiration` and those values (AC 1, door 5)
Proof: `uv run pytest tests/test_bank_connect.py -k "link_token_returned"`

**C2** - The fake records one link-token request for that call with `country_codes` `["CA"]`, `products` `["transactions"]`, `days_requested` `730`, `language` `"en"`, `client_name` `"Headroom"` and `client_user_id` equal to the caller's `users.id` as a string (AC 2)
Proof: `uv run pytest tests/test_bank_connect.py -k "link_token_request_values"`

**C3** - The real `PlaidClient`, over a mocked `plaid-python` `PlaidApi`, sends `link_token_create` a request whose `country_codes`, `products`, `transactions.days_requested`, `language`, `client_name` and `user.client_user_id` equal C2's values, and every SDK call it makes (link token, exchange, accounts, institution, remove) passes a 15-second request timeout (AC 2, AC 3, door 2)
Proof: `uv run pytest tests/test_plaid_client.py -k "sdk_requests"`

**C4** - The real `PlaidClient` turns an SDK `ApiException` whose body has `error_type` `"API_ERROR"`, `error_code` `"INTERNAL_SERVER_ERROR"` and `request_id` `"req-1"` into the port's one Plaid error carrying exactly those three values, and an SDK read timeout into the same error type (door 2)
Proof: `uv run pytest tests/test_plaid_client.py -k "errors_mapped"`

**C5** - With the fake's link-token call raising the Plaid error, and separately raising the timeout case, the route returns `502` `application/problem+json` with `detail` exactly `"We couldn't reach our bank connection provider. Try again."` (AC 3)
Proof: `uv run pytest tests/test_bank_connect.py -k "link_token_plaid_fails"`

### S2 - The API stores a connection · 10 files · 70 KB · ~18k

**C6** - As the owner, `POST .../bank/connections` with `{"public_token": "public-sandbox-1"}`, the fake returning institution `"TD Canada Trust"` and three accounts named `"Savings"`, `"Chequing"`, `"Visa"`, returns `201` with keys exactly `id`, `institution_name`, `created_at`, `accounts`; `institution_name` is `"TD Canada Trust"`; `accounts` holds 3 items, each with keys exactly `id`, `name`, `type`, `mask`, `currency`, `balance_cents`, ordered `Chequing`, `Savings`, `Visa` (AC 4, door 5)
Proof: `uv run pytest tests/test_bank_connect.py -k "connect_returns_connection"`

**C7** - After C6's call the database holds exactly `1` `bank_connections` row (the response `id`, that `business_id`, the fake's `plaid_item_id` and institution id) and exactly `3` `bank_accounts` rows with that `connection_id` and `business_id` (AC 5, door 3)
Proof: `uv run pytest tests/test_bank_connect.py -k "connect_stores_rows"`

**C8** - Plaid `(type, subtype)` maps to the stored and returned `type`: `(depository, checking)` -> `checking`, `(depository, savings)` -> `savings`, `(credit, credit card)` -> `credit_card`, `(loan, line of credit)` -> `line_of_credit`, `(credit, line of credit)` -> `line_of_credit`, `(depository, money market)` -> `other`, `(investment, brokerage)` -> `other`, `(loan, mortgage)` -> `other`, `(other, None)` -> `other` (table-driven, 9 cases) (AC 6, door 3)
Proof: `uv run pytest tests/test_bank_connect.py -k "account_type_mapping"`

**C9** - Account fields are stored and returned as: `mask` `"0001"` -> `"0001"` and `None` -> `null`; currency `iso_currency_code` `"CAD"` -> `"CAD"`, and `iso_currency_code` `None` with `unofficial_currency_code` `"USDC"` -> `"USDC"`; `balances.current` `1234.565` -> `123456`, `10.005` -> `1000`, `-50.0` -> `-5000`, `8000.0` -> `800000`, `None` -> `null` (table-driven) (AC 6)
Proof: `uv run pytest tests/test_bank_connect.py -k "account_field_mapping"`

**C10** - The stored `access_token_ciphertext` is not equal to and does not contain the fake's access token `"access-sandbox-secret-1"`; `MultiFernet` over the configured keys decrypts it to exactly that token; with `TOKEN_ENCRYPTION_KEYS` set to `<new>,<old>`, the new value decrypts with `Fernet(<new>)` alone, and a value encrypted earlier under `<old>` still decrypts through the module's decrypt function (AC 7, door 4)
Proof: `uv run pytest tests/test_bank_connect.py -k "token_encrypted"`

**C11** - C6's call writes exactly `1` `audit_log` row with `action` `bank_connection.created`, that `business_id`, `actor_user_id` `str(users.id)`, `target_type` `bank_connection`, `target_id` the connection `id`, and `details` exactly `{"institution_id": "<fake institution id>", "account_count": 3}`; a connect that fails at the database write leaves `0` such rows (AC 8)
Proof: `uv run pytest tests/test_bank_connect.py -k "connect_audited"`

**C12** - A second connect for the same business with the fake returning the same institution id and a new item returns `409` with `detail` exactly `"This bank is already connected."`; the fake's remove was called exactly once, with the second access token; the business still has exactly `1` connection and its original accounts (AC 9, door 3)
Proof: `uv run pytest tests/test_bank_connect.py -k "same_bank_twice_conflicts"`

**C13** - Two threads released by one barrier each call `bank_sync.service.connect_bank` with their own session, the same business, the same institution and different items; exactly one returns a connection and the other raises the service's duplicate error; the database holds exactly `1` connection for that business; the fake's remove was called exactly once, with the losing thread's access token (AC 10, door 3)
Proof: `uv run pytest tests/test_bank_connect.py -k "concurrent_connects"`

**C14** - With the fake's exchange raising a Plaid error of type `INVALID_INPUT`, the route returns `400` with `detail` exactly `"We couldn't finish connecting your bank. Try again."`, stores `0` connections, and the fake's remove was not called (AC 11)
Proof: `uv run pytest tests/test_bank_connect.py -k "invalid_public_token"`

**C15** - Each failure returns `502` with C5's detail and stores `0` connections and `0` accounts, with the fake's remove called as stated (table-driven, 4 cases): exchange raises `API_ERROR` (remove not called); accounts call raises (remove called once with the new access token); institution call raises (remove called once); accounts call times out (remove called once) (AC 12, AC 13)
Proof: `uv run pytest tests/test_bank_connect.py -k "plaid_failures"`

**C16** - With the database write failing after the exchange (the repository insert patched to raise `SQLAlchemyError`), and separately with `app.audit.record` raising, the route returns `500` problem details with `detail` `"An unexpected error occurred."` (AD-008), stores `0` connections and `0` accounts, and the fake's remove was called exactly once with the new access token (AC 13)
Proof: `uv run pytest tests/test_bank_connect.py -k "database_failure_removes_item"`

**C17** - With the accounts call raising and the fake's remove also raising, the route returns `502` with C5's detail and writes exactly one JSON log line with `event` `bank_connection.orphaned`, `level` `error`, the `business_id`, and the fake's `plaid_item_id` (AC 14)
Proof: `uv run pytest tests/test_bank_connect.py -k "orphaned_item_logged"`

**C18** - Bodies `{}`, `{"public_token": ""}`, `{"public_token": null}` and `{"public_token": "public-sandbox-1", "extra": 1}` each return `422` problem details with an `errors` item, make no Plaid call, and store no row (AC 15)
Proof: `uv run pytest tests/test_bank_connect.py -k "connect_body_validation"`

**C19** - After `alembic upgrade head` on an empty database: `bank_connections` has columns exactly `id`, `business_id` (`uuid`, not null), `plaid_item_id`, `plaid_institution_id`, `institution_name`, `access_token_ciphertext` (`text`, not null), `created_at`, `updated_at` (`timestamp with time zone`, not null), unique constraints `uq_bank_connections_plaid_item_id` and `uq_bank_connections_business_id_plaid_institution_id`, and no foreign key; `bank_accounts` has columns exactly `id`, `business_id`, `connection_id` (`uuid`, not null), `plaid_account_id`, `name`, `type`, `currency` (`text`, not null), `mask` (`text`, null), `balance_cents` (`bigint`, null), `created_at`, `updated_at`, foreign key `connection_id` -> `bank_connections.id` and no other, unique `uq_bank_accounts_plaid_account_id`, check `ck_bank_accounts_type`; `alembic downgrade -1` removes both tables; `alembic check` reports no differences at head (door 3, AD-003)
Proof: `uv run pytest tests/test_migrations.py -k "bank_connections_and_accounts"`

**C20** - Direct inserts that break each constraint raise `IntegrityError`: account `type` `loan` (`ck_bank_accounts_type`), a second connection with the same `plaid_item_id`, a second connection for the same `(business_id, plaid_institution_id)`, a second account with the same `plaid_account_id`, and an account whose `connection_id` matches no connection (door 3)
Proof: `uv run pytest tests/test_bank_connect.py -k "database_constraints"`

**C21** - Against the Plaid sandbox with the real `PlaidClient`: the link-token call returns a token starting `link-sandbox-`; a public token for `ins_42` (TD Canada Trust) from `/sandbox/public_token/create` posted to `POST .../bank/connections` returns `201` with `institution_name` `"TD Canada Trust"`, at least `1` account, every `type` in door 3's set and every `currency` `"CAD"`; the stored ciphertext decrypts to a token starting `access-sandbox-`; the test removes the item at the end (AC 1, AC 4, AC 6, AC 7 against the real provider)
Proof: `bash .specs/features/12-bank-connect/proofs.sh c21` (runs `uv run pytest -m plaid_sandbox tests/test_bank_connect_sandbox.py` with `.env.local` exported)

### S3 - Only the owner, only their business · 3 files · 30 KB · ~8k

**C22** - With user A owning business A and user B owning business B, B calling both bank routes on business A gets `404` with `detail` exactly `"Business not found."`, the same body as a random UUID except `instance`, and the fake records `0` calls (AC 16)
Proof: `uv run pytest tests/test_bank_connect.py -k "non_member_gets_404"`

**C23** - A member whose membership lookup (`accounts.service.get_membership`, patched) reports a role other than `owner` gets `403` with `detail` exactly `"You don't have permission to do this."` from both bank routes, and the fake records `0` calls (AC 17)
Proof: `uv run pytest tests/test_bank_connect.py -k "non_owner_gets_403"`

**C24** - The route walk over the app lists `("POST", "/businesses/{business_id}/bank/link-token")` and `("POST", "/businesses/{business_id}/bank/connections")`, and `business_routes_missing_member(app)` is `[]` (AC 18)
Proof: `uv run pytest tests/test_bank_connect.py -k "bank_routes_require_member"`

**C25** - Both bank routes return `401` without a token, through the existing walk over every `/v1` path (Surface 401s, AD-022)
Proof: `uv run pytest tests/test_auth.py -k "every_v1_route_requires_token"`

**C26** - Both bank routes with `business_id` `not-a-uuid` return `422` problem details with an `errors` item whose `loc` ends in `"business_id"`, and the fake records `0` calls (Surface 422)
Proof: `uv run pytest tests/test_bank_connect.py -k "malformed_business_id"`

### S4 - The access token never leaks · 4 files · 25 KB · ~6k

**C27** - Across the success path (C6), the duplicate (C12), `400` (C14), every `502` case (C15, C17), the `500` case (C16), `404` (C22), `403` (C23) and `422` (C18), no response body contains the fake's access tokens, the public token `"public-sandbox-1"`, or any stored ciphertext (AC 19)
Proof: `uv run pytest tests/test_bank_connect.py -k "no_token_in_responses"`

**C28** - Over the same paths, with logging configured and Sentry initialised on a fake transport, no captured log line and no captured Sentry event contains the fake's access tokens or the public token (AC 20)
Proof: `uv run pytest tests/test_bank_connect.py -k "no_token_in_logs_or_sentry"`

**C29** - C6's call writes exactly one JSON log line with `event` `bank_connection.created`, `business_id`, `connection_id`, `institution_id` and `account_count` `3`, and no captured log line contains the account names `Chequing`, `Savings`, `Visa`, the fake masks or the fake balance values (AC 21)
Proof: `uv run pytest tests/test_bank_connect.py -k "connect_logged"`

**C30** - `Settings()` raises `ValidationError` with `TOKEN_ENCRYPTION_KEYS` unset, `""`, `"not-a-key"`, and `"<valid>,not-a-key"`; with two valid keys it yields both, in order (AC 22, door 4)
Proof: `uv run pytest tests/test_settings.py -k "token_encryption_keys"`

**C31** - `Settings()` raises `ValidationError` with each of `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV` unset, and with `PLAID_ENV` `"development"`; it accepts `"sandbox"` and `"production"` (AC 23, door 6)
Proof: `uv run pytest tests/test_settings.py -k "plaid_settings"`

### S5 - Onboarding step 3 · 18 files · 110 KB · ~28k

**C32** - The step 2 server action, with `POST /v1/businesses` mocked: `201` calls `redirect("/onboarding/bank")`; `409` calls `redirect("/")` (AC 24)
Proof: `npx vitest run tests/create-business-action.test.ts -t "create business action"`

**C33** - The step 3 page: `GET /v1/businesses` answering `{"items": []}` calls `redirect("/onboarding/business")`; answering one business and the link-token call answering `200` renders the connect view with that `link_token` handed to the client component, and the link-token request goes to that business's id with `Authorization: Bearer <token>`; `GET /v1/businesses` answering `500` or rejecting, and the link-token call answering `502` or rejecting, each render `States.errorTitle` and no connect button (AC 25, AC 33)
Proof: `npx vitest run tests/bank-page.test.tsx -t "bank page"`

**C34** - The onboarding loading state (spec 11 C25) still renders `aria-busy="true"` with `States.loading`, and no `loading.tsx` under `app/onboarding/bank/` replaces it (AC 34)
Proof: `npx vitest run tests/onboarding-page.test.tsx -t "loading state"`
Proof: `npx vitest run tests/bank-page.test.tsx -t "uses the onboarding loading state"`

**C35** - The connect view renders, from `messages/en.json`, in document order: the wordmark, `Step 3 of 5`, the five-segment `aria-hidden` bar with exactly 3 segments in `bg-accent`, the heading `Connect your bank`, `Headroom reads your balances and transactions to build your 13-week forecast.`, the three items `Read-only` / `Headroom can see your balances and transactions. It can't move money.`, `Your password stays with your bank` / `You log in on your bank's own screen. Headroom never sees your password.`, `You're in control` / `Disconnect at any time, and Headroom removes that bank's data.` each with an `aria-hidden` icon, `Bank connections are provided by Plaid.`, and a button `Connect your bank` (AC 26)
Proof: `npx vitest run tests/connect-bank.test.tsx -t "renders the mockup"`
Proof: `npx vitest run tests/bank-page.test.tsx -t "header"` (added after verification round 1: the first proof renders only the view, not the page header)

**C36** - With `usePlaidLink` mocked: it receives the page's `link_token`; pressing `Connect your bank` while `ready` is `true` calls `open` exactly once (AC 27)
Proof: `npx vitest run tests/connect-bank.test.tsx -t "opens plaid link"`

**C37** - While `ready` is `false` the button is disabled; while the connect action is pending the button is disabled, has `aria-busy="true"`, reads `Connecting your bank…`, and a second click calls the action no more times (AC 28)
Proof: `npx vitest run tests/connect-bank.test.tsx -t "button states"`

**C38** - The connect server action, with `POST .../bank/connections` mocked: the request goes to the business id it was given with body exactly `{"public_token": "<token>"}` and `Authorization: Bearer <token>`; `201` calls `redirect("/")`; `409` returns the duplicate result and does not redirect; `400`, `502`, `500` and a rejected call each return the generic error result and do not redirect (AC 29, AC 30, AC 31)
Proof: `npx vitest run tests/connect-bank-action.test.ts -t "connect bank action"`

**C39** - In the connect view: `onSuccess("public-sandbox-1", ...)` calls the action with that token; a duplicate result shows `This bank is already connected.`; a generic error result shows `We couldn't connect your bank. Try again.`; `onExit` with an error object shows the generic message; `onExit` with `null` shows no message; each message sits above the button inside an element with `role="alert"`, and the button stays enabled after each (AC 30, AC 31, AC 32, AC 36)
Proof: `npx vitest run tests/connect-bank.test.tsx -t "outcomes"`

**C40** - No JSX text node or string attribute in `app/onboarding/**` or `components/onboarding/**` (now including the step 3 files) is a literal English string, and every message key they use exists in `messages/en.json` (AC 36)
Proof: `npx vitest run tests/onboarding-copy.test.ts -t "no literal copy"`

**C41** - Playwright, a Clerk user created for this run with no business: from the first `page.goto("/")`, completing step 2 ends on `/onboarding/bank`; pressing `Connect your bank`, choosing TD Canada Trust in the Plaid Link sandbox and logging in with `user_good` / `pass_good` ends on `/`; the time from the first `page.goto` to the `/` assertion is under `120000` ms (AC 24, AC 27, AC 29, AC 37; Done when 1)
Proof: `npx playwright test e2e/bank-connect.spec.ts -g "new user connects a sandbox bank"`

**C42** - Playwright, a Clerk user created for this run with no business: visiting `/onboarding/bank` ends on `/onboarding/business` (AC 25)
Proof: `npx playwright test e2e/bank-connect.spec.ts -g "no business goes to step 2"`

**C43** - Playwright on `/onboarding/bank` as the existing test user: at 375px wide `document.documentElement.scrollWidth` is at most `375`; at 1280px the column is at most `480` px wide and centred (gaps within 1px); the button is at least `44` px tall; Tab reaches `Connect your bank` and Enter opens the Plaid Link iframe; axe reports `0` violations before Link opens (AC 35)
Proof: `npx playwright test e2e/bank-connect.spec.ts -g "layout keyboard and axe"`

**C44** - With step 2 now landing on step 3, `e2e/global.setup.ts` and the spec 11 onboarding specs (`new user creates a business` ends on `/onboarding/bank`, then `/` shows the business name in the header within the same 120 s bound; `user with a business skips onboarding`; `quebec shows not available`; `layout keyboard and axe`) pass, and `shell`, `home`, `auth`, `api-check` pass unchanged (Impact: web onboarding)
Proof: `bash .specs/features/12-bank-connect/proofs.sh c44` (runs `npx playwright test e2e/onboarding.spec.ts e2e/shell.spec.ts e2e/home.spec.ts e2e/auth.spec.ts e2e/api-check.spec.ts`, as spec 11's C39 did)

**C45** - The generated files match the API: rerunning `uv run python -m app.export_openapi` and `npm run api:types` leaves `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` unchanged, and `openapi.json` holds both bank paths (Impact: API contract, AD-015, AD-016, AD-018)
Proof: `bash .specs/features/12-bank-connect/proofs.sh c45`

**C46** - All AGENTS.md checks for both areas pass: `ruff format --check`, `ruff check`, `mypy app`, `pytest` (default selection), and `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
Proof: `bash .specs/features/12-bank-connect/proofs.sh c46`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST /v1/businesses/{business_id}/bank/link-token` statuses (6) | 200 C1 · 401 C25 · 403 C23 · 404 C22 · 422 C26 · 502 C5 | - |
| `POST /v1/businesses/{business_id}/bank/connections` statuses (8) | 201 C6 · 400 C14 · 401 C25 · 403 C23 · 404 C22 · 409 C12 · 422 C18 · 502 C15 | - |
| one-way doors (6) | door 1 C24 · door 2 C3 · door 3 C19 · door 4 C10 · door 5 C6 · door 6 C31 | - |
| entities (2) | `bank_connections` C19 · `bank_accounts` C19 | - |
| account types (5) | checking C8 · savings C8 · credit_card C8 · line_of_credit C8 · other C8 | - |
| Plaid type pairs (9) | C8, table-driven over all 9 | - |
| account field mapping (11 cases) | C9, table-driven over all 11 | - |
| link-token request values (6) | country C2, C3 · products C2, C3 · days C2, C3 · language C2, C3 · client name C2, C3 · client user id C2, C3 | - |
| failure points after exchange (5) | accounts C15 · institution C15 · timeout C15 · database write C16 · audit C16 | - |
| failure points before exchange (2) | `INVALID_INPUT` C14 · other Plaid error C15 | - |
| DB constraints (5) | type C20 · item id C20 · business-institution C20 · account id C20 · connection FK C20 | - |
| settings (5) | `TOKEN_ENCRYPTION_KEYS` C30 · `PLAID_CLIENT_ID` C31 · `PLAID_SECRET` C31 · `PLAID_ENV` C31 · `PLAID_ENV` values C31 | - |
| startup config: Plaid client and keys (3 assemblies) | app via `get_plaid_client` C21 · unit tests via override and conftest C6 · Playwright API via `.env.local` C41 | - |
| connect action outcomes (6) | 201 C38 · 409 C38 · 400 C38 · 502 C38 · 500 C38 · rejected C38 | - |
| connect view outcomes (5) | success C39 · duplicate C39 · error C39 · Link error C39 · Link closed C39 | - |
| step 3 page states (6) | connect view C33 · no business C33, C42 · businesses fail C33 · link token fails C33 · loading C34 · unauthorised C44 | - |
| step 2 redirects (2) | 201 C32 · 409 C32 | - |

- Claims naming a status code, route or response shape (C1, C5, C6, C12, C14-C18, C22-C27) are proven through `TestClient` at the HTTP boundary; C13 asserts at the service layer because two simultaneous requests cannot be ordered through `TestClient`; C3 and C4 assert the adapter against a mocked SDK because unit tests never call Plaid, and C21 crosses the real Plaid boundary for the happy path
- The unauthorised state of step 3 is the existing `auth.protect()` rule; `tests/auth-protect.test.ts` (spec 10 C34) walks every page and covers the new one, and C44 runs `auth.spec.ts`
- No other check claims more than the single case its proof exercises

## Swept

- validation: C18 (body), C26 (path), C30, C31 (settings), C20 (database)
- failure modes: C15, C16, C17 (nothing stored, item removed, orphan logged); C33, C38, C39 (web)
- idempotency: C12 (same bank again is `409`, not a second connection); C37 (no double submit from the button)
- authorization: C22, C23, C24 (membership and owner role); C25 (token, AD-022)
- concurrency: C13 (two connects at once, settled by `uq_bank_connections_business_id_plaid_institution_id`)
- data lifecycle: n/a - no deletion or refresh in this spec; disconnect is spec 17 and balance refresh spec 14
- dependency failure: C4, C5, C14, C15, C17 (Plaid errors and timeouts); C33 (API down, seen from the web)
- state transitions: C32, C41, C42 (step 2 -> step 3 -> `/`; step 3 without a business -> step 2)
- observability: C29 (`bank_connection.created`), C17 (`bank_connection.orphaned`), C11 (audit entry)

## Handoff

- S1-S5 touch about 40 files: 107 KB existing (`wc -c` on `main.py`, `auth.py`, `settings.py`, `audit.py`, `log.py`, `problems.py`, `migrations/env.py`, `conftest.py`, `test_settings.py`, `test_migrations.py`, `test_auth.py`, the step 2 page and action, the onboarding components, `en.json`, the four onboarding e2e files, three web tests, `openapi.json`, `schema.d.ts`) plus about 95 KB new (the five `bank_sync` files and `plaid.py`, the migration, three pytest files, the step 3 page, view and action, four web test files, one e2e spec, `proofs.sh`) = 202 KB / 4 = ~51k tokens, under the 150k budget - one builder
- Mechanism: one builder
- **Boundary:** C1-C46 green at the web commit (API `011e49c`)
- **Settled mid-build:** doors 7 and 8 (public tokens in the redaction pattern; any key containing `body` redacted) came from C28, whose first run found FastAPI's raw `body_bytes` in a Sentry event for the `500` path. Spec 11's tests change with AC 24: `create-business-action` (C31 there) now expects `/onboarding/bank` for `201`; `onboarding.spec.ts` C34 and C37 there land on step 3, and C34 then opens `/` within the same 120 s bound; `completeBusinessStep` waits for step 3 and `global.setup.ts` opens `/` after it. Spec 11's businesses migration test downgrades to `07f1bcba78b6` instead of `-1`, which now undoes this spec's migration. The step 3 view reads keys as `Bank.*` under the `Onboarding` namespace (the step 2 pattern, and what `onboarding-copy.test.ts` resolves). `plaid-python` ships no `py.typed`, so `pyproject.toml` has a mypy override for `plaid.*`. The sandbox institution is TD Canada Trust (`ins_42`, not OAuth); Plaid Link's sandbox flow is: Continue without phone number, search, TD Canada Trust, `user_good` / `pass_good`, Continue, Finish without saving
- **Abandoned:** printing the leaking log line from inside the test (pytest's captured output lost it); a throwaway Playwright spec that mapped the Plaid Link screens, deleted before commit
