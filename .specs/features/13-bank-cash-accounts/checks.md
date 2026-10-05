# 13 - Choose cash accounts checks

Profile: light
Plan: `.specs/features/13-bank-cash-accounts/plan.md`

53 checks in 5 slices · 5 one-way doors · 0 open

Commands run from `services/core/` (`uv run pytest ...`) or `frontend/` (`npx vitest run <file> -t "<name>"`, `npx playwright test <file> -g "<name>"`). `bash .specs/features/13-bank-cash-accounts/proofs.sh <cNN>` runs from anywhere in the repo. API unit tests use spec 12's fake `PlaidClient` and never call Plaid. The test marked `plaid_sandbox` calls the real Plaid sandbox and runs only through `proofs.sh`, which exports `services/core/.env.local` first. Playwright starts the web app on 3000 and the API on 8100, as in spec 12.

## Checks

### S1 - The cash rules hold in the API · 8 files · 90 KB · ~23k

**C1** - A connect whose fake returns six accounts - `checking` `CAD`, `savings` `CAD`, `credit_card` `CAD`, `line_of_credit` `CAD`, `other` `CAD`, `checking` `USD` - stores and returns `included` `true` for the `CAD` checking account only and `false` for the other five (AC 1, door 1)
Proof: `uv run pytest tests/test_bank_accounts.py -k "connect_includes_cad_checking_only"`

**C2** - `available_cents` is stored and returned as Plaid's `balances.available` in cents rounded half-even: `20000.0` -> `2000000`, `1234.565` -> `123456`, `None` -> `null` (table-driven); and the real `PlaidClient`, over a mocked `PlaidApi`, carries an account's `balances.available` `150.25` into the port's account as `150.25` and `None` as `None` (AC 2, door 2)
Proof: `uv run pytest tests/test_bank_accounts.py -k "available_cents_mapping"`
Proof: `uv run pytest tests/test_plaid_client.py -k "available_balance"`

**C3** - As the owner, `PATCH .../bank/accounts/{id}` with `{"included": true}` on an excluded `CAD` savings account, and separately on an excluded `CAD` checking account, returns `200` with that account's JSON holding `included` `true`, and the row now holds `included` `true` (AC 3)
Proof: `uv run pytest tests/test_bank_accounts.py -k "include_cash_account"`

**C4** - `{"included": true}` on a `credit_card` account and on a `line_of_credit` account each returns `409` `application/problem+json` with `detail` exactly `"Credit cards and lines of credit can't count as cash."`, and every `bank_accounts` row of the business is unchanged (AC 4)
Proof: `uv run pytest tests/test_bank_accounts.py -k "include_credit_conflicts"`

**C5** - `{"included": true}` on an `other` account returns `409` with `detail` exactly `"This type of account can't count as cash."` and changes no row (AC 5)
Proof: `uv run pytest tests/test_bank_accounts.py -k "include_other_conflicts"`

**C6** - `{"included": true}` on a `USD` checking account and on a `USD` savings account each returns `409` with `detail` exactly `"Only Canadian dollar accounts can count as cash for now."` and changes no row (AC 6)
Proof: `uv run pytest tests/test_bank_accounts.py -k "include_non_cad_conflicts"`

**C7** - `{"included": false}` on an included account that is not primary returns `200` with `included` `false`, and the row holds `false` (AC 7)
Proof: `uv run pytest tests/test_bank_accounts.py -k "exclude_non_primary"`

**C8** - A direct `UPDATE bank_accounts SET included = true` on a `credit_card` row, an `other` row, and a `USD` checking row each raises `IntegrityError` naming `ck_bank_accounts_included_cash` (AC 8, door 1)
Proof: `uv run pytest tests/test_bank_accounts.py -k "included_cash_constraint"`

**C9** - After `alembic upgrade head` on an empty database, `bank_accounts` has `included` (`boolean`, not null), `is_primary` (`boolean`, not null, default `false`), `available_cents` (`bigint`, null), checks `ck_bank_accounts_included_cash` and `ck_bank_accounts_primary_included`, and the partial unique index `uq_bank_accounts_primary_business_id` on `(business_id)` `WHERE is_primary`; rows inserted at the previous revision (business A: `CAD` checking at `5000` and `9000` cents, `CAD` savings, `credit_card`; business B: `USD` checking only) are, after the upgrade, `included` `true` only for A's two checking rows, `is_primary` `true` only for A's `9000` checking row, and `available_cents` null everywhere; `alembic downgrade -1` drops the three columns; `alembic check` reports no differences at head (doors 1, 2, 3; Impact stored data)
Proof: `uv run pytest tests/test_migrations.py -k "bank_accounts_cash_columns"`

### S2 - One primary account · 3 files · 50 KB · ~13k

**C10** - On a business's first connect, the primary account is chosen among the included accounts by largest `balance_cents`, null last, then `name`, then `id` (table-driven, 3 cases): checking `5000` / `9000` / `null` -> the `9000` one; checking `null` / `null` named `"B"`, `"A"` -> `"A"`; checking `7000` named `"Ops"` and `"Main"` -> `"Main"`; a `CAD` savings at `20000` never wins; exactly `1` row of the business has `primary` `true` (AC 9, door 3)
Proof: `uv run pytest tests/test_bank_accounts.py -k "first_connect_primary"`

**C11** - A first connect whose accounts are one `CAD` savings and one `credit_card` leaves `0` primary accounts (AC 9)
Proof: `uv run pytest tests/test_bank_accounts.py -k "no_included_no_primary"`

**C12** - A second connect (another institution) whose checking balance is larger than the current primary's leaves the primary account unchanged and the new accounts `primary` `false` (AC 10)
Proof: `uv run pytest tests/test_bank_accounts.py -k "second_connect_keeps_primary"`

**C13** - `{"primary": true}` on an included non-primary account returns `200` with `primary` `true`; afterwards that account is the business's only primary row and the previous primary holds `primary` `false` and `included` `true` (AC 11)
Proof: `uv run pytest tests/test_bank_accounts.py -k "move_primary"`

**C14** - `{"included": true, "primary": true}` on an excluded `CAD` savings account returns `200` with `included` `true` and `primary` `true`, and the previous primary is no longer primary (AC 12)
Proof: `uv run pytest tests/test_bank_accounts.py -k "include_and_make_primary"`

**C15** - `{"primary": true}` on an excluded account returns `409` with `detail` exactly `"Only an account that counts as cash can be primary."` and changes no row (AC 13)
Proof: `uv run pytest tests/test_bank_accounts.py -k "primary_requires_included"`

**C16** - `{"included": false}` on the primary account returns `409` with `detail` exactly `"Choose another primary account first."` and changes no row (AC 14)
Proof: `uv run pytest tests/test_bank_accounts.py -k "exclude_primary_conflicts"`

**C17** - On C11's business (no primary), `{"included": true}` on the savings account returns `200` with `included` `true` and `primary` `true` (AC 15)
Proof: `uv run pytest tests/test_bank_accounts.py -k "first_include_becomes_primary"`

**C18** - Direct writes raise `IntegrityError`: a second `is_primary = true` row for one business (`uq_bank_accounts_primary_business_id`), and `is_primary = true` on a row with `included = false` (`ck_bank_accounts_primary_included`); one primary row in each of two businesses is accepted (AC 16, door 3)
Proof: `uv run pytest tests/test_bank_accounts.py -k "primary_constraints"`

**C19** - Two threads released by one barrier each call the service's account update with their own session, making two different included accounts of one business primary; both return without error and the business has exactly `1` primary row afterwards, one of the two (AC 17)
Proof: `uv run pytest tests/test_bank_accounts.py -k "concurrent_primary_moves"`

**C20** - Two threads released by one barrier each call `connect_bank` with their own session for one business with no connection, two different institutions, each with one `CAD` checking account; both return a connection, the business has `2` connections and exactly `1` primary row afterwards (AC 18)
Proof: `uv run pytest tests/test_bank_accounts.py -k "concurrent_connects_one_primary"`

### S3 - Listing and updating are the owner's, for their business only · 4 files · 45 KB · ~11k

**C21** - `GET /v1/businesses/{business_id}/bank/connections` as the owner of a business with two connections returns `200` with keys exactly `items`; `items` holds both, older `created_at` first, each with keys exactly `id`, `institution_name`, `created_at`, `accounts`, and accounts ordered by `name`; for a business with no connection it returns `200` `{"items": []}` (AC 19, door 4)
Proof: `uv run pytest tests/test_bank_accounts.py -k "list_connections"`

**C22** - Every account object returned by `GET .../bank/connections`, by `PATCH .../bank/accounts/{id}` and by `POST .../bank/connections` has keys exactly `id`, `name`, `type`, `mask`, `currency`, `balance_cents`, `available_cents`, `included`, `primary`, and no response body contains the fake's `plaid_account_id` or `plaid_item_id` values (AC 20, door 5; amends spec 12 C6's key set)
Proof: `uv run pytest tests/test_bank_accounts.py -k "account_json_keys"`
Proof: `uv run pytest tests/test_bank_connect.py -k "connect_returns_connection"`

**C23** - With users A and B each owning a business, B calling `GET .../bank/connections` and `PATCH .../bank/accounts/{A's account}` on business A gets `404` with `detail` exactly `"Business not found."`, and A's rows are unchanged (AC 21)
Proof: `uv run pytest tests/test_bank_accounts.py -k "non_member_gets_404"`

**C24** - A member whose membership lookup (patched) reports a role other than `owner` gets `403` with `detail` exactly `"You don't have permission to do this."` from both new routes, and no row changes (AC 22)
Proof: `uv run pytest tests/test_bank_accounts.py -k "non_owner_gets_403"`

**C25** - B calling `PATCH /v1/businesses/{B's business}/bank/accounts/{A's account}`, and A calling it with a random UUID, each get `404` with `detail` exactly `"Account not found."`; A's account row is unchanged (AC 23)
Proof: `uv run pytest tests/test_bank_accounts.py -k "foreign_account_gets_404"`

**C26** - The route walk lists `("GET", "/businesses/{business_id}/bank/connections")` and `("PATCH", "/businesses/{business_id}/bank/accounts/{account_id}")`, and `business_routes_missing_member(app)` is `[]` (AC 24)
Proof: `uv run pytest tests/test_bank_accounts.py -k "account_routes_require_member"`

**C27** - Both new routes return `401` without a token, through the existing walk over every `/v1` path (Surface 401s, AD-022)
Proof: `uv run pytest tests/test_auth.py -k "every_v1_route_requires_token"`

**C28** - `PATCH` bodies `{}`, `{"included": true, "extra": 1}`, `{"primary": false}`, `{"primary": null}` and `{"included": "yes"}` each return `422` problem details with an `errors` item and change no row; `business_id` `not-a-uuid` on both routes and `account_id` `not-a-uuid` on `PATCH` return `422` with an `errors` item whose `loc` ends in that parameter (AC 25, Surface 422)
Proof: `uv run pytest tests/test_bank_accounts.py -k "patch_validation"`

**C29** - Audit entries (`audit_log` rows with `action` `bank_account.updated`): including an excluded savings account writes exactly `1` with that `business_id`, `actor_user_id` `str(users.id)`, `target_type` `bank_account`, `target_id` the account `id`, `details` exactly `{"included": true}`; C14's request writes exactly `1` with `details` exactly `{"included": true, "primary": true}`; `{"included": true}` on an already-included account returns `200` and writes `0`; a `409` writes `0` (AC 26)
Proof: `uv run pytest tests/test_bank_accounts.py -k "update_audited"`

**C30** - C29's first request writes exactly one JSON log line with `event` `bank_account.updated`, `business_id`, `account_id` and `included` `true`, and no captured log line contains the fake's account names, masks or balance values (AC 27)
Proof: `uv run pytest tests/test_bank_accounts.py -k "update_logged"`

### S4 - Two sandbox banks on one business · 2 files · 8 KB · ~2k

**C31** - Against the Plaid sandbox with the real `PlaidClient`: public tokens for two different Canadian sandbox institutions (TD Canada Trust `ins_42` and a second one found through `/institutions/search` at build time, written into the test) from `/sandbox/public_token/create`, each posted to `POST .../bank/connections` for one business, both return `201`; `GET .../bank/connections` returns `2` items with those two institution names, every account `currency` set, and exactly `1` account with `primary` `true`; the test removes both items at the end (AC 28; Done when 2)
Proof: `bash .specs/features/13-bank-cash-accounts/proofs.sh c31`

### S5 - Onboarding "choose accounts" step · 20 files · 130 KB · ~33k

**C32** - The connect server action, with `POST .../bank/connections` mocked to `201`, calls `redirect("/onboarding/accounts")`; its other outcomes stay as spec 12 C38 states (AC 29)
Proof: `npx vitest run tests/connect-bank-action.test.ts -t "connect bank action"`

**C33** - The accounts page: `GET /v1/businesses` `{"items": []}` calls `redirect("/onboarding/business")`; one business and `GET .../bank/connections` `{"items": []}` calls `redirect("/onboarding/bank")`; one business, one connection and the link-token call `200` renders the choose-accounts view with that connection list and link token, with the list request sent to that business's id with `Authorization: Bearer <token>`; `GET /v1/businesses` `500` or rejecting, `GET .../bank/connections` `500` or rejecting, and the link-token call `502` each render `States.errorTitle` and no `Continue` button (AC 30, AC 46)
Proof: `npx vitest run tests/accounts-page.test.tsx -t "accounts page"`

**C34** - The onboarding loading state (spec 11 C25) is the one in force: no `loading.tsx` exists under `app/onboarding/accounts/` (AC 47)
Proof: `npx vitest run tests/accounts-page.test.tsx -t "uses the onboarding loading state"`

**C35** - With one connection (`"Harbor Community Bank"`, accounts `Operating checking` / `Reserve savings` / `Line of credit`), the page renders from `messages/en.json`, in document order: the wordmark, `Step 3 of 5`, the `aria-hidden` bar with exactly 3 of 5 segments in `bg-accent`, the heading `Which accounts count as cash?`, `Harbor Community Bank is connected. Choose what Headroom counts as cash you can spend.`, the three cards in API order, `Expected payments you add go to your primary account unless you choose another.`, a `Connect another bank` button containing an `aria-hidden` icon, and a `Continue` button, with no institution heading (AC 31)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "renders the mockup"`
Proof: `npx vitest run tests/accounts-page.test.tsx -t "header"`

**C36** - With two connections, the intro reads exactly `Your banks are connected. Choose what Headroom counts as cash you can spend.` and each connection's cards follow a heading with its institution name, in API order (AC 32)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "two banks"`

**C37** - A card shows the account name and `••2381 · Checking`; types render `Checking`, `Savings`, `Credit` (credit card and line of credit), `Other`; with `mask` null the line is the type label alone; `balance_cents` `800000` `CAD` shows `$8,000`; `120000` `USD` shows `US$1,200`; `balance_cents` null shows no amount (AC 33)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "card header"`

**C38** - A `CAD` checking card shows `Counts as cash` and a `role="switch"` with `aria-checked` equal to `included` and accessible name `Operating checking counts as cash` (AC 34)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "checking switch"`

**C39** - A `CAD` savings card shows `Is this money you can spend?` and a group of two buttons `Yes, count it` / `No, keep it separate`; with `included` `false` only `No, keep it separate` is pressed, with `true` only `Yes, count it` (AC 35)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "savings segmented"`

**C40** - A `line_of_credit` card with `available_cents` `2000000` and a `credit_card` card each show `$20,000` (or their own available amount) with the caption `available`, not `balance_cents`; with `available_cents` null no amount; each shows `Credit never counts as cash. Headroom shows what's available, and may suggest it as a fix.` and has no switch, no segmented group and no radio (AC 36)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "credit card"`

**C41** - An `other` card shows `This type of account can't count as cash.`; a `USD` checking card and a `USD` savings card show `Only Canadian dollar accounts can count as cash for now.`; none has a switch, segmented group or radio (AC 37)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "cannot count"`

**C42** - Only included accounts show a `Primary account` radio; all radios share one `radiogroup`; only the account with `primary` `true` is checked (AC 38)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "primary radio"`

**C43** - The update server action, with `PATCH .../bank/accounts/{id}` mocked: the request goes to the business and account ids it was given with the body it was given (`{"included": false}`, `{"included": true}`, `{"primary": true}`, `{"included": true, "primary": true}`) and `Authorization: Bearer <token>`; `200` returns success and revalidates `/onboarding/accounts`; `409`, `404`, `500` and a rejected call each return the error result and do not revalidate (AC 39, AC 41)
Proof: `npx vitest run tests/update-account-action.test.ts -t "update account action"`

**C44** - In the view, with the action mocked: toggling an included checking switch calls it with `{"included": false}`; pressing `Yes, count it` on an excluded savings calls it with `{"included": true}`; choosing a `Primary account` radio calls it with `{"primary": true}`; while the call is pending every switch, segmented button, radio, `Connect another bank` and `Continue` is disabled; an error result shows `We couldn't save that change. Try again.` inside `role="alert"` above the buttons and the control shows its value from the props again (AC 39, AC 40, AC 41)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "saves changes"`

**C45** - With `usePlaidLink` mocked: it receives the page's link token; pressing `Connect another bank` while `ready` calls `open` once; `onSuccess("public-sandbox-2")` calls spec 12's connect action with that token; a duplicate result shows `This bank is already connected.`, a generic error result and `onExit` with an error show `We couldn't connect your bank. Try again.`, each inside `role="alert"`; `onExit(null)` shows no message (AC 42, AC 43)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "connect another bank"`

**C46** - Pressing `Continue` with at least one included account navigates to `/`; with none, it does not navigate and shows `Choose at least one account that counts as cash.` inside `role="alert"` (AC 44, AC 45)
Proof: `npx vitest run tests/choose-accounts.test.tsx -t "continue"`

**C47** - No JSX text node or string attribute in `app/onboarding/**` or `components/onboarding/**` (now including the accounts files) is a literal English string, and every message key they use exists in `messages/en.json` (AC 49)
Proof: `npx vitest run tests/onboarding-copy.test.ts -t "no literal copy"`

**C48** - `formatMoney(120000, "USD")` is `US$1,200`; `formatMoney(320000)` and `formatMoney(320000, "CAD")` are still `$3,200` (Impact web formatting)
Proof: `npx vitest run lib/format.test.ts -t "formatMoney"`

**C49** - Playwright, a Clerk user created for this run with no business: step 2, then step 3 with TD Canada Trust in the Plaid Link sandbox (`user_good` / `pass_good`) ends on `/onboarding/accounts` showing TD's accounts with exactly one primary radio checked; `Connect another bank` with C31's second institution stays on `/onboarding/accounts` and shows both institution headings; pressing `Yes, count it` on a savings account and then its `Primary account` radio, then reloading, shows that savings pressed `Yes` and its radio checked; `Continue` ends on `/` (AC 29, AC 39, AC 42, AC 44; Done when 2)
Proof: `npx playwright test e2e/choose-accounts.spec.ts -g "owner chooses cash accounts across two banks"`

**C50** - Playwright on `/onboarding/accounts` as a user with a connected sandbox bank, at 375px wide: `document.documentElement.scrollWidth` is at most `375`; the heading, the cards, the primary-account note, `Connect another bank` and `Continue` are stacked top to bottom in that order and the two buttons span the column width; every switch, segmented button, radio label and button is at least `44` px tall; a full-page screenshot is attached to the report for comparison with `onboarding-3-choose-accounts.dc.html`; at 1280px the column is at most `480` px wide and centred (gaps within 1px); Tab reaches the first switch and Space flips its `aria-checked`, and Tab reaches `Continue`; axe reports `0` violations (AC 48; Done when 3)
Proof: `npx playwright test e2e/choose-accounts.spec.ts -g "layout keyboard and axe"`

**C51** - With step 3 now landing on the new step: spec 12's `new user connects a sandbox bank` ends on `/onboarding/accounts`, then `Continue` lands on `/`, within the same `120000` ms bound; spec 12's `no business goes to step 2` and `layout keyboard and axe`, and the `onboarding`, `shell`, `home`, `auth`, `api-check` specs pass (Impact web onboarding)
Proof: `bash .specs/features/13-bank-cash-accounts/proofs.sh c51`

**C52** - The generated files match the API: rerunning the export and `npm run api:types` leaves `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` unchanged, and `openapi.json` holds both new paths (Impact API contract, AD-015, AD-016, AD-018)
Proof: `bash .specs/features/13-bank-cash-accounts/proofs.sh c52`

**C53** - All AGENTS.md checks for both areas pass: `ruff format --check`, `ruff check`, `mypy app`, `pytest` (default selection), `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
Proof: `bash .specs/features/13-bank-cash-accounts/proofs.sh c53`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /v1/businesses/{business_id}/bank/connections` statuses (5) | 200 C21 · 401 C27 · 403 C24 · 404 C23 · 422 C28 | - |
| `PATCH /v1/businesses/{business_id}/bank/accounts/{account_id}` statuses (6) | 200 C3 · 401 C27 · 403 C24 · 404 C23, C25 · 409 C4, C5, C6, C15, C16 · 422 C28 | - |
| one-way doors (5) | door 1 C8, C9 · door 2 C2, C9 · door 3 C18, C9 · door 4 C21 · door 5 C22 | - |
| entities (1) | `bank_accounts` C9 | - |
| account kinds for inclusion (6) | CAD checking C1, C3 · CAD savings C3 · credit_card C4 · line_of_credit C4 · other C5 · non-CAD C6 | - |
| `409` details (5) | credit C4 · other C5 · currency C6 · primary not included C15 · exclude primary C16 | - |
| primary choice order (3 keys) | balance C10 · null last C10 · name C10 | - |
| primary transitions (6) | set on first connect C10 · none when nothing included C11 · kept on later connect C12 · moved C13, C14 · set on first include C17 · cannot be excluded C16 | - |
| DB constraints (3) | `ck_bank_accounts_included_cash` C8 · `uq_bank_accounts_primary_business_id` C18 · `ck_bank_accounts_primary_included` C18 | - |
| `PATCH` bodies rejected (5) | `{}` C28 · extra field C28 · `primary` false C28 · `primary` null C28 · `included` not bool C28 | - |
| card variants (6) | checking C38 · savings C39 · credit card C40 · line of credit C40 · other C41 · non-CAD C41 | - |
| update action outcomes (5) | 200 C43 · 409 C43 · 404 C43 · 500 C43 · rejected C43 | - |
| connect-another outcomes (5) | success C45, C49 · duplicate C45 · error C45 · Link error C45 · Link closed C45 | - |
| accounts page states (8) | view C33 · no business C33 · no connection C33 · businesses fail C33 · connections fail C33 · link token fails C33 · loading C34 · unauthorised C53 | - |
| startup config: Plaid account `available` (2 assemblies) | real client C2 · fake used by unit tests C2 | - |

- Claims naming a status code, route or response shape (C3-C7, C13-C17, C21-C25, C28) are proven through `TestClient` at the HTTP boundary; C19 and C20 assert at the service layer because two simultaneous requests cannot be ordered through `TestClient`; C8 and C18 assert the database directly, because the API refuses those writes before they reach it
- The unauthorised state is the existing `auth.protect()` rule; `tests/auth-protect.test.ts` (spec 10 C34) walks every page, including the new one, and runs inside C53's `npm test`
- No other check claims more than the single case its proof exercises

## Swept

- validation: C28 (body and path), C4, C5, C6 (cash rules), C8, C18 (database)
- failure modes: C4-C6, C15, C16 change no row; C33 (page load fails), C44 (save fails), C45 (connect fails)
- idempotency: C29 (a `PATCH` that changes nothing returns `200` and writes no audit row); C44 (controls disabled while a save is pending, no double submit)
- authorization: C23, C24, C25, C26 (membership, owner role, account of another business); C27 (token, AD-022)
- concurrency: C19 (two primary moves), C20 (two connects choosing a primary), settled by `uq_bank_accounts_primary_business_id`
- data lifecycle: C9 (backfill of existing rows); deletion n/a - disconnect is spec 17
- dependency failure: C31 crosses the real Plaid sandbox; the new routes call no provider; C33 (API down, seen from the web)
- state transitions: C10-C17 (primary and inclusion transitions); C32, C46, C49 (step 3 -> choose accounts -> `/`)
- observability: C29 (audit), C30 (`bank_account.updated` log line)

## Handoff

- S1-S5 touch about 35 files: about 160 KB existing (`wc -c` on the six `bank_sync` files, `test_bank_connect.py`, `test_migrations.py`, `test_plaid_client.py`, `test_auth.py`, `en.json`, `connect-bank.tsx`, the step 3 page and action, `format.ts` and its test, `bank-connect.spec.ts`, `onboarding-steps.ts`, three web tests, the three shadcn components, `openapi.json`, `schema.d.ts` = 119 KB, plus `test_bank_connect.py` and `test_migrations.py` = 42 KB) plus about 90 KB new (the migration, `test_bank_accounts.py`, the accounts page, view and action, three web test files, one e2e spec, `proofs.sh`) = 250 KB / 4 = ~63k tokens, under the 150k budget - one builder
