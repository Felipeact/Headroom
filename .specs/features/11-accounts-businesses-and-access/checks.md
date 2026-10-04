# 11 - Businesses and access checks

Profile: light
Plan: `.specs/features/11-accounts-businesses-and-access/plan.md`

41 checks in 5 slices · 6 one-way doors · 0 open

Commands run from `services/core/` (`uv run pytest ...`) or `frontend/` (`npx vitest run <file> -t "<name>"`, `npx playwright test <file> -g "<name>"`). `bash .specs/features/11-accounts-businesses-and-access/proofs.sh <cNN>` runs from anywhere in the repo. DB-backed pytest tests use the `migrated_database` fixture and need a Postgres on `localhost:5432` (CI has one; locally a portable Postgres in the scratchpad). API tests sign tokens with the per-session test key (`tests/tokens.py`) and never call Clerk. Playwright starts the web app on 3000 and the API on 8100; the existing test user comes from `E2E_CLERK_USER_USERNAME`, and the onboarding user is created per run through the Clerk Backend API on the dev instance.

## Checks

### S1 - An owner creates a business through the API · 9 files · 45 KB · ~11k

**C1** - `POST /v1/businesses` with `{"name": "Harbor Street Plumbing", "province": "ON", "time_zone": "America/Toronto"}` from a user who owns no business returns `201` with JSON keys exactly `id`, `name`, `province`, `time_zone`, `country`, `currency`, `role`, `created_at`, where the three sent values are echoed, `country` is `CA`, `currency` is `CAD`, `role` is `owner`, and `id` parses as a UUID (AC 1, door 4)
Proof: `uv run pytest tests/test_businesses.py -k "create_returns_business"`

**C2** - After C1's create, the database holds exactly `1` `businesses` row with the response `id` and exactly `1` `memberships` row for (that business, that user) with `role` `owner` (AC 2, doors 1, 2)
Proof: `uv run pytest tests/test_businesses.py -k "create_stores_business_and_owner"`

**C3** - `name` `"  Harbor Street Plumbing  "` is returned and stored as `"Harbor Street Plumbing"` (AC 3)
Proof: `uv run pytest tests/test_businesses.py -k "name_is_trimmed"`

**C4** - `name` `""`, `"   "` and a 101-character string each return `422` problem details with an `errors` item whose `loc` ends in `"name"` and store no row; a 100-character name returns `201` (AC 4)
Proof: `uv run pytest tests/test_businesses.py -k "name_bounds"`

**C5** - `province` `"XX"`, `"on"`, `"Ontario"` and a missing `province` each return `422` with an `errors` item whose `loc` ends in `"province"`; each of `AB`, `BC`, `MB`, `NB`, `NL`, `NS`, `NT`, `NU`, `ON`, `PE`, `SK`, `YT` returns `201` (table-driven, 12 cases, a new user each) (AC 5, door 1)
Proof: `uv run pytest tests/test_businesses.py -k "province_values"`

**C6** - `province` `"QC"` returns `422` with an `errors` item whose `loc` ends in `"province"`, `type` `"province_not_available"` and `msg` exactly `"Headroom isn't available in Quebec yet."`, and leaves `0` `businesses` and `0` `memberships` rows for that user (AC 6)
Proof: `uv run pytest tests/test_businesses.py -k "quebec_refused"`

**C7** - `time_zone` `"America/New_York"`, `"UTC"`, `""` and a missing `time_zone` each return `422` with an `errors` item whose `loc` ends in `"time_zone"`; each of `America/St_Johns`, `America/Halifax`, `America/Toronto`, `America/Winnipeg`, `America/Regina`, `America/Edmonton`, `America/Vancouver`, `America/Whitehorse` returns `201` (table-driven, 8 cases) (AC 7, door 1)
Proof: `uv run pytest tests/test_businesses.py -k "time_zone_values"`

**C8** - A second `POST /v1/businesses` by a user who already owns one returns `409` problem details with `detail` exactly `"You already own a business."`, and the user still has exactly `1` business and `1` membership (AC 8, door 2)
Proof: `uv run pytest tests/test_businesses.py -k "second_business_conflicts"`

**C9** - Two threads released by one barrier each call `accounts.service.create_business` with their own session for the same new user; exactly one returns a business and the other raises the service's "already owns a business" error, and the database holds exactly `1` `businesses` row and `1` `memberships` row created for that user, with no `businesses` row lacking a membership (AC 9, door 2)
Proof: `uv run pytest tests/test_businesses.py -k "concurrent_creates"`

**C10** - After `alembic upgrade head` on an empty database: table `businesses` has columns exactly `id` (`uuid`, primary key), `name`, `province`, `time_zone`, `country`, `currency` (all `text`, not null), `created_at`, `updated_at` (`timestamp with time zone`, not null); table `memberships` has columns exactly `business_id`, `user_id` (`uuid`, not null), `role` (`text`, not null), `created_at` (`timestamp with time zone`, not null), primary key `pk_memberships` on `(business_id, user_id)`, foreign keys to `businesses.id` and `users.id`, and the unique index `uq_memberships_owner_user_id` on `user_id` with predicate `role = 'owner'`; `alembic downgrade -1` removes both tables; `alembic check` reports no differences at head (doors 1, 2, AD-003)
Proof: `uv run pytest tests/test_migrations.py -k "businesses_and_memberships"`

**C11** - Direct inserts that break each constraint raise `IntegrityError`: `country` `US` (`ck_businesses_country`), `currency` `USD` (`ck_businesses_currency`), `province` `QC` (`ck_businesses_province`), `time_zone` `UTC` (`ck_businesses_time_zone`), `name` `""` (`ck_businesses_name_length`), `role` `bookkeeper` (`ck_memberships_role`), and a second `owner` membership for the same user in another business (`uq_memberships_owner_user_id`) (doors 1, 2)
Proof: `uv run pytest tests/test_businesses.py -k "database_constraints"`

### S2 - Only members reach a business · 6 files · 35 KB · ~9k

**C12** - With user A owning business A and user B owning business B: `GET /v1/businesses` as A returns `200` with `items` holding exactly one entry, business A, in the C1 shape; as a user with no business it returns `200` `{"items": []}` (AC 10, door 5)
Proof: `uv run pytest tests/test_businesses.py -k "list_only_own"`

**C13** - Inside one transaction that drops `uq_memberships_owner_user_id` and is rolled back afterwards, a user with two memberships created at `2026-01-02` and `2026-01-01` gets them from the list function in `accounts.service` ordered `2026-01-01` first (AC 10)
Proof: `uv run pytest tests/test_businesses.py -k "list_oldest_membership_first"`

**C14** - `GET /v1/businesses/{A}` as A returns `200` with the C1 shape and A's values (AC 11)
Proof: `uv run pytest tests/test_businesses.py -k "member_reads_business"`

**C15** - As user B, `GET` and `PATCH /v1/businesses/{A}` each return `404` `application/problem+json` with `detail` exactly `"Business not found."`; the same two calls with a random UUID return a body equal to it in every key except `instance` (AC 12, door 3)
Proof: `uv run pytest tests/test_businesses.py -k "non_member_gets_404"`

**C16** - `GET` and `PATCH /v1/businesses/not-a-uuid` each return `422` problem details with an `errors` item whose `loc` ends in `"business_id"` (AC 13)
Proof: `uv run pytest tests/test_businesses.py -k "malformed_business_id"`

**C17** - A test route declared with `require_member(Role.OWNER)`, called by a member whose membership lookup (`accounts.service.get_membership`, patched) reports a role other than `owner`, returns `403` problem details with `detail` exactly `"You don't have permission to do this."`; the same route called by the owner returns `200` (AC 14, door 3)
Proof: `uv run pytest tests/test_businesses.py -k "role_not_allowed_gets_403"`

**C18** - As owner A: `PATCH` with `{"name": "Harbor Street Plumbing Ltd"}` returns `200` with the new name and the old `province` and `time_zone`; `PATCH` with `{"province": "BC", "time_zone": "America/Vancouver"}` returns `200` with both changed and the name kept; a fresh `GET` returns the same values (AC 15)
Proof: `uv run pytest tests/test_businesses.py -k "owner_patches_business"`

**C19** - As owner A, `PATCH` with `{"name": "   "}`, `{"province": "QC"}` (with `type` `"province_not_available"`), and `{"time_zone": "UTC"}` each return `422` with the `errors` `loc` ending in that field, and a fresh read of business A shows every field unchanged (AC 16)
Proof: `uv run pytest tests/test_businesses.py -k "invalid_patch_changes_nothing"`

**C20** - After B's `PATCH /v1/businesses/{A}` with `{"name": "Taken"}` (which returns `404`), a fresh read of business A shows its name unchanged (AC 17)
Proof: `uv run pytest tests/test_businesses.py -k "non_member_patch_changes_nothing"`

**C21** - Every OpenAPI path containing `{business_id}` (at least `/v1/businesses/{business_id}`) has, for each method, the `require_member` dependency in its route's dependency tree; a route added in the test without it is reported by the same walk (AC 18, door 3)
Proof: `uv run pytest tests/test_businesses.py -k "every_business_route_requires_member"`

**C22** - Every new route-method pair (`POST /v1/businesses`, `GET /v1/businesses`, `GET /v1/businesses/{business_id}`, `PATCH /v1/businesses/{business_id}`) returns `401` without a token, through the existing walk over all `/v1` paths (Surface 401s, AD-022)
Proof: `uv run pytest tests/test_auth.py -k "every_v1_route_requires_token"`

### S3 - Onboarding step 2 · 16 files · 90 KB · ~23k

**C23** - `(app)/layout.tsx` with `GET /v1/businesses` answering `200` `{"items": []}` calls `redirect("/onboarding/business")`; answering `200` with one item named `"Harbor Street Plumbing"` renders the page content and passes that name to `AppHeader` (visible in the header); answering `500` or rejecting renders `States.errorTitle` and not the page content; the call carries `Authorization: Bearer <token>` (AC 19, AC 35)
Proof: `npx vitest run tests/app-layout.test.tsx -t "businesses"`

**C24** - The onboarding page with `GET /v1/businesses` answering one item calls `redirect("/")`; answering `{"items": []}` renders the form; answering `500` or rejecting renders `States.errorTitle` and no form (AC 20, AC 30)
Proof: `npx vitest run tests/onboarding-page.test.tsx -t "onboarding page"`

**C25** - `app/onboarding/loading.tsx` (or `app/onboarding/business/loading.tsx`) renders an element with `aria-busy="true"` and the label `States.loading` (AC 31)
Proof: `npx vitest run tests/onboarding-page.test.tsx -t "loading state"`

**C26** - The form renders, from `messages/en.json`: the wordmark, `Step 2 of 5`, a five-segment `aria-hidden` bar with exactly 2 segments in `bg-accent`, the heading `Tell us about your business`, the line `Your time zone decides when alerts and your weekly email arrive.`, labels `Business name`, `Province or territory`, `Time zone` each linked to its control, hints `Headroom isn't available in Quebec yet.` and `Filled in from your device. Change it if it's wrong.`, and a `Continue` button, in that document order (AC 21, door 6)
Proof: `npx vitest run tests/business-form.test.tsx -t "renders the mockup"`

**C27** - The province control offers exactly 13 options in this order: Alberta, British Columbia, Manitoba, New Brunswick, Newfoundland and Labrador, Northwest Territories, Nova Scotia, Nunavut, Ontario, Prince Edward Island, Quebec, Saskatchewan, Yukon; none is selected on first render (AC 22)
Proof: `npx vitest run tests/business-form.test.tsx -t "province options"`

**C28** - The time zone control offers exactly 8 options in this order: Newfoundland Time (St. John's), Atlantic Time (Halifax), Eastern Time (Toronto), Central Time (Winnipeg), Saskatchewan Time (Regina), Mountain Time (Edmonton), Pacific Time (Vancouver), Yukon Time (Whitehorse); with the device zone mocked to `America/Winnipeg` it shows `Central Time (Winnipeg)` selected, and with `Europe/London` none is selected (AC 23)
Proof: `npx vitest run tests/business-form.test.tsx -t "time zone options"`

**C29** - Choosing Quebec, before Continue is pressed, shows `Headroom isn't available in Quebec yet. You can't set up a business there for now.` in an element with class `text-danger-text` whose `id` is in the province control's `aria-describedby`; choosing Ontario afterwards removes it (AC 24)
Proof: `npx vitest run tests/business-form.test.tsx -t "quebec message"`

**C30** - Pressing Continue with (a) an empty name, (b) no province, (c) no time zone, and (d) Quebec each calls the server action `0` times, shows that field's message from `messages/en.json` next to it, and moves focus to the first field in error (table-driven, 4 cases) (AC 25)
Proof: `npx vitest run tests/business-form.test.tsx -t "client validation"`

**C31** - The server action, with `POST /v1/businesses` mocked: `201` calls `redirect("/")`; `409` calls `redirect("/")`; `422` with `errors` `[{"loc": ["body", "province"], "type": "province_not_available", ...}]` returns the province field error key and does not redirect; `500` and a rejected call each return the form-level error and do not redirect; the request body is exactly `name`, `province`, `time_zone` and the call carries `Authorization: Bearer <token>` (AC 26, 27, 28)
Proof: `npx vitest run tests/create-business-action.test.ts -t "create business action"`

**C32** - With the form-level error returned, the form shows `We couldn't save your business. Try again.` above Continue and keeps the entered name, province and time zone (AC 28)
Proof: `npx vitest run tests/business-form.test.tsx -t "save error keeps values"`

**C33** - While the server action is pending, the Continue button has `aria-busy="true"` and is disabled, and a second click calls the action no more times (`1` call total) (AC 29)
Proof: `npx vitest run tests/business-form.test.tsx -t "pending state"`

**C34** - Playwright, a Clerk user created for this run with no business: visiting `/` ends on `/onboarding/business`; filling `Harbor Street Plumbing`, Ontario, Eastern Time (Toronto) and pressing Continue ends on `/` with `Harbor Street Plumbing` in the header; the time from the first `page.goto` to the header assertion is under `120000` ms (AC 19, 26, 33, 35; Done when 1)
Proof: `npx playwright test e2e/onboarding.spec.ts -g "new user creates a business"`

**C35** - Playwright, the existing test user (who has a business after setup): visiting `/onboarding/business` ends on `/` (AC 20)
Proof: `npx playwright test e2e/onboarding.spec.ts -g "user with a business skips onboarding"`

**C36** - Playwright, the per-run user: choosing Quebec shows the C29 message, and pressing Continue stays on `/onboarding/business` and `GET /v1/businesses` still returns no business for that user (AC 24, AC 25; Done when 3)
Proof: `npx playwright test e2e/onboarding.spec.ts -g "quebec shows not available"`

**C37** - Playwright on `/onboarding/business`: at 375px wide `document.documentElement.scrollWidth` is at most `375`; at 1280px the form column is at most `480` px wide and horizontally centred (left and right gaps within 1px); every input, select trigger and button is at least `44` px tall; the form is completed with the keyboard alone (Tab, typing, arrow keys, Enter) and lands on `/`; axe reports `0` violations (AC 32)
Proof: `npx playwright test e2e/onboarding.spec.ts -g "layout keyboard and axe"`

**C38** - No JSX text node or string attribute (`placeholder`, `aria-label`, `title`, `alt`) in `app/onboarding/**` or `components/onboarding/**` is a literal English string; every message key those files use exists in `messages/en.json` (AC 34)
Proof: `npx vitest run tests/onboarding-copy.test.ts -t "no literal copy"`

**C39** - With `e2e/global.setup.ts` giving the existing test user a business, the existing specs `shell`, `home`, `auth`, `api-check` pass unchanged in their assertions (Impact: web routing)
Proof: `bash .specs/features/11-accounts-businesses-and-access/proofs.sh c39` (runs `npx playwright test e2e/shell.spec.ts e2e/home.spec.ts e2e/auth.spec.ts e2e/api-check.spec.ts` without spec 07's C42, which needs `NEXT_PUBLIC_SENTRY_DSN` empty and is run as its own proof says; C39 is a regression claim over those whole files)

### S4 - The shell shows the business · covered by C23 (unit) and C34 (end to end)

### S5 - Nothing about a business leaks · 3 files · 15 KB · ~4k

**C40** - Creating and then patching a business named `Secret Name Plumbing` writes exactly one `business.created` and one `business.updated` JSON log line, each with `business_id` equal to the business and `user_id` equal to the caller's `users.id`; no captured log line contains `Secret Name Plumbing` (AC 36)
Proof: `uv run pytest tests/test_businesses.py -k "business_logs"`

**C41** - No response body from the four business routes (C1, C12, C14, C18 calls) contains the key `clerk_user_id` at any depth, and user A's list and reads never contain business B's `id` anywhere in the body (AC 37)
Proof: `uv run pytest tests/test_businesses.py -k "no_foreign_fields"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST /v1/businesses` statuses (4) | 201 C1 · 401 C22 · 409 C8 · 422 C4 | - |
| `GET /v1/businesses` statuses (2) | 200 C12 · 401 C22 | - |
| `GET /v1/businesses/{business_id}` statuses (4) | 200 C14 · 401 C22 · 404 C15 · 422 C16 | - |
| `PATCH /v1/businesses/{business_id}` statuses (4) | 200 C18 · 401 C22 · 404 C15 · 422 C19 | - |
| province codes (13) | AB C5 · BC C5 · MB C5 · NB C5 · NL C5 · NS C5 · NT C5 · NU C5 · ON C5 · PE C5 · SK C5 · YT C5 · QC C6 | - |
| time zones (8) | St_Johns C7, C28 · Halifax C7, C28 · Toronto C7, C28 · Winnipeg C7, C28 · Regina C7, C28 · Edmonton C7, C28 · Vancouver C7, C28 · Whitehorse C7, C28 | - |
| `name` bounds (4 edges) | empty C4 · whitespace only C4 · 100 chars C4 · 101 chars C4 | - |
| one-way doors (6) | door 1 C10 · door 2 C9 · door 3 C17 · door 4 C1 · door 5 C12 · door 6 C26 | - |
| entities (2) | `businesses` C10 · `memberships` C10 | - |
| DB constraints (7) | country C11 · currency C11 · province C11 · time_zone C11 · name C11 · role C11 · owner index C11 | - |
| `require_member` outcomes (3) | member allowed C14 · non-member C15 · role not allowed C17 | - |
| server action outcomes (5) | 201 C31 · 409 C31 · 422 C31 · other status C31 · rejected call C31 | - |
| client validation cases (4) | empty name C30 · no province C30 · no time zone C30 · Quebec C30 | - |
| onboarding page states (5) | form C24 · has business C24 · load error C24 · loading C25 · unauthorised C39 | - |
| shell outcomes (3) | no business C23 · has business C23 · load error C23 | - |

- Claims naming a status code, route or response shape (C1, C4-C8, C12, C14-C20, C22, C41) are proven through `TestClient` at the HTTP boundary; C9, C13 and C17 assert at the service or dependency layer because the case cannot be reached through HTTP (concurrency, a second membership, a second role)
- The unauthorised state of the onboarding page is the existing `auth.protect()` rule; `tests/auth-protect.test.ts` (spec 10 C34) walks every page and covers the new one, and C39 runs `auth.spec.ts`
- No other check claims more than the single case its proof exercises

## Swept

- validation: C4, C5, C6, C7 (API); C30 (web); C11 (database)
- failure modes: C2 and C9 (business and membership in one transaction, no orphan row); C31, C32 (save fails); C23, C24 (load fails)
- idempotency: C8 (a repeated create is `409`, not a second business); C31 (the web treats `409` as done)
- authorization: C15, C17, C20, C21 (membership and role); C22 (token, AD-022)
- concurrency: C9 (two creates at once, settled by `uq_memberships_owner_user_id`); C33 (no double submit from the form)
- data lifecycle: n/a - no deletion, archival or backfill is specified; existing users simply have no business until they onboard
- dependency failure: C23, C24, C31 (API down or erroring, seen from the web)
- state transitions: C23, C24, C34, C35 (no business -> onboarding -> has business -> shell; back to onboarding is refused)
- observability: C40 (`business.created`, `business.updated` with ids, no name)

## Handoff

- S1-S5 touch about 25 existing and new files: 59 KB existing (`wc -c` on `auth.py`, `main.py`, the five `accounts` files, `test_migrations.py`, `test_auth.py`, `(app)/layout.tsx`, `app-layout.test.tsx`, `global.setup.ts`, `test-user.ts`, `playwright.config.ts`, `en.json`, `app-header.tsx`, the `select`, `input`, `button`, `label` components, `auth-protect.test.ts`, `shell.spec.ts`) plus 9 KB generated (`openapi.json`, `schema.d.ts`) plus about 70 KB new (migration, `test_businesses.py`, the onboarding page, form, action, step indicator, loading, five test files, `proofs.sh`) = 138 KB / 4 = ~35k tokens, under the 150k budget - one builder
- Mechanism: one builder
- **Boundary:** C1-C41 green at the web commit (API `4853182`)
- **Settled mid-build:** spec 07's e2e C11 ("no business yet") asserted the header has no business label until spec 11; since this spec gives the test user a business it now asserts the business name in the header (AC 35). The business name is user content, so it carries `data-user-content` like the user's name, which spec 07's C20 copy check skips. The users-table migration test downgrades to `99b26f739028` instead of `-1`, which now undoes this spec's migration. C36's "no business for that user" is observed through the page: a reload of `/onboarding/business` still shows the form, and that page sends any user with a business to `/` after its own `GET /v1/businesses`. The onboarding Clerk user is created per test through the Backend API (Open question 1), so no `E2E_CLERK_ONBOARDING_USERNAME` exists. Door 7 corrects door 6's colour token and row arrangement
- **Abandoned:** prefilling the time zone with `useEffect` + `setState` (the React lint rule rejects it); `useSyncExternalStore` reads the device zone on the client with an empty server snapshot instead
