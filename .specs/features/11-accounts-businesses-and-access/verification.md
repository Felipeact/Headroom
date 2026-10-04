# 11 - Businesses and access verification

**Verdict**: PASS
**Profile**: light
**Diff range**: e41a687..78b5790 (fix diff for this round: bf48b28..78b5790)
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

Round 1 (`bf48b28`) failed C26. The fix commit `78b5790` changes only three test files:
- `frontend/tests/business-form.test.tsx`
- `services/core/tests/test_businesses.py` (+4 lines after line 412)
- `frontend/e2e/onboarding.spec.ts` (+4 lines after line 110)

No source file changed. Every proof re-ran in full at `78b5790`. C26, C14 and C37 were re-judged against the fix diff. Citations in the three touched files were refreshed. The judgment on every other check is `carried from bf48b28`, with its proof re-run green at `78b5790`. 41/41 checks are proven.

## Binding sources

Not run: profile is `light`, so step 1 does not run. The plan marks `design/mockups/onboarding-2-business.dc.html` as binding, but under `light` it was not opened or compared. This line is carried from bf48b28.

## Checks

Proofs re-run at `78b5790`. Each named test was shown individually as PASSED or ok:

- API: `uv run pytest tests/test_businesses.py tests/test_migrations.py tests/test_auth.py -v -k "<24-name alternation>"`: 58 passed, 37 deselected, exit 0
- Web unit: `npx vitest run tests/app-layout.test.tsx tests/onboarding-page.test.tsx tests/business-form.test.tsx tests/create-business-action.test.ts tests/onboarding-copy.test.ts --reporter=verbose -t "<12-pattern alternation>"`: 26 passed, exit 0
- Playwright (ports 3000 and 8100 confirmed free first): `npx playwright test e2e/onboarding.spec.ts -g "new user creates a business|user with a business skips onboarding|quebec shows not available|layout keyboard and axe" --reporter=list`: 6 passed (2 setup + C34-C37), exit 0
- `bash .specs/features/11-accounts-businesses-and-access/proofs.sh c39`: 39 passed, `PASS c39`, exit 0

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | 201, exact key set, echoed values, CA/CAD/owner, uuid id | `test_create_returns_business` PASSED | `services/core/tests/test_businesses.py:151` `response.status_code == 201`; `:153` `set(body) == BUSINESS_KEYS`; `:157-160` country `"CA"`, currency `"CAD"`, role `"owner"`, `uuid.UUID(body["id"])` (carried from bf48b28; lines unchanged) | PASS |
| C2 | 1 business row + 1 owner membership | `test_create_stores_business_and_owner` PASSED | `test_businesses.py:173` `len(businesses) == 1`; `:174` `[(str(m.business_id), m.role) ...] == [(business_id, "owner")]` (carried from bf48b28) | PASS |
| C3 | name trimmed in response and storage | `test_name_is_trimmed` PASSED | `test_businesses.py:182` response name; `:183` `stored(...).name == "Harbor Street Plumbing"` (carried from bf48b28) | PASS |
| C4 | "", "   ", 101 chars -> 422 loc name, no row; 100 -> 201 | `test_name_bounds_rejected[3]`, `test_name_bounds_100_accepted` PASSED | `test_businesses.py:188` `error_for(..., "name")` (422, problem+json, `loc[-1]` at `:138-141`); `:189` `counts(caller.id) == (0, 0)`; `:193` `status_code == 201` (carried from bf48b28) | PASS |
| C5 | 4 bad provinces -> 422; 12 codes -> 201, new user each | `test_province_values_rejected[4]`, `test_province_values_accepted[12]` PASSED | `test_businesses.py:201` `error_for(caller.post(body), "province")`; `:207` `status_code == 201` (carried from bf48b28) | PASS |
| C6 | QC -> 422 type/msg exact, 0 rows | `test_quebec_refused` PASSED | `test_businesses.py:214` `error["type"] == "province_not_available"`; `:215` msg exact; `:216` `counts(caller.id) == (0, 0)` (carried from bf48b28) | PASS |
| C7 | 4 bad zones -> 422; 8 zones -> 201 | `test_time_zone_values_rejected[4]`, `test_time_zone_values_accepted[8]` PASSED | `test_businesses.py:224` `error_for(..., "time_zone")`; `:230` `status_code == 201` (carried from bf48b28) | PASS |
| C8 | second create -> 409 exact detail, still 1/1 | `test_second_business_conflicts` PASSED | `test_businesses.py:239` `== 409`; `:241` `detail == "You already own a business."`; `:242` `counts == (1, 1)` (carried from bf48b28) | PASS |
| C9 | concurrent service creates: one ok, one conflict, 1/1, no orphan | `test_concurrent_creates` PASSED | `test_businesses.py:277` `len(created) == 1`; `:278` `len(conflicts) == 1`; `:279` `counts == (1, 1)`; `:280` `orphan_businesses() == orphans_before` (carried from bf48b28) | PASS |
| C10 | exact columns, PKs, FKs, partial unique index, downgrade, alembic check | `test_businesses_and_memberships_upgrade_downgrade_and_check` PASSED | `services/core/tests/test_migrations.py:187` column set; `:201` PK/FK set; `:220-222` index `WHERE (role = 'owner'::text)`; `:231-232` tables gone; `:235-237` `check` returncode 0 (carried from bf48b28) | PASS |
| C11 | 7 constraint violations raise IntegrityError naming the constraint | `test_database_constraints_businesses[5]`, `test_database_constraints_memberships` PASSED | `test_businesses.py:329` `constraint in _violates(...)` (`pytest.raises(IntegrityError)` `:310`); `:341` `ck_memberships_role`; `:345` `uq_memberships_owner_user_id` (carried from bf48b28) | PASS |
| C12 | list as A: exactly A, C1 shape; none -> `{"items": []}` | `test_list_only_own` PASSED | `test_businesses.py:360` `== 200`; `:362` ids `== [business_a]`; `:363` `set(items[0]) == BUSINESS_KEYS`; `:364` `== {"items": []}` (carried from bf48b28) | PASS |
| C13 | oldest membership first | `test_list_oldest_membership_first` PASSED | `test_businesses.py:399` `names == ["Older", "Newer"]` (carried from bf48b28) | PASS |
| C14 | member GET -> 200, C1 shape, A's values | `test_member_reads_business` PASSED | Re-judged at 78b5790: `test_businesses.py:407` `response.status_code == 200`; `:409` `set(body) == BUSINESS_KEYS`; `:410-416` `body["id"] == business_a`, name `"Harbor Street Plumbing"`, province `"ON"`, time_zone `"America/Toronto"`, country `"CA"`, currency `"CAD"`, role `"owner"`. The round-1 precision gap is closed | PASS |
| C15 | non-member GET/PATCH -> 404 problem+json exact detail; equals random-uuid body minus instance | `test_non_member_gets_404` PASSED | Citations refreshed: `test_businesses.py:434` `foreign.status_code == 404`; `:435` problem+json; `:436` `detail == "Business not found."`; `:438` dict equality excluding `instance` (carried from bf48b28) | PASS |
| C16 | not-a-uuid -> 422 loc business_id | `test_malformed_business_id` PASSED | `test_businesses.py:444`, `:445` `error_for(..., "business_id")` (refreshed; carried from bf48b28) | PASS |
| C17 | non-owner role -> 403 exact; owner -> 200 | `test_role_not_allowed_gets_403` PASSED | `test_businesses.py:475` `== 403`; `:477` `detail == "You don't have permission to do this."`; `:478` `allowed.status_code == 200` (refreshed; carried from bf48b28) | PASS |
| C18 | PATCH updates only fields sent; fresh GET matches | `test_owner_patches_business` PASSED | `test_businesses.py:487-489` new name, ON/Toronto kept; `:493-495` name kept, BC/Vancouver; `:497` `a.get(path).json() == moved.json()` (refreshed; carried from bf48b28) | PASS |
| C19 | invalid PATCH -> 422 per field; row unchanged | `test_invalid_patch_changes_nothing` PASSED | `test_businesses.py:505-508` `error_for` x3 and `quebec["type"] == "province_not_available"`; `:511` stored tuple equals `before` (refreshed; carried from bf48b28) | PASS |
| C20 | B's PATCH of A -> 404, name unchanged | `test_non_member_patch_changes_nothing` PASSED | `test_businesses.py:526` `== 404`; `:527` `stored(business_a).name == "Harbor Street Plumbing"` (refreshed; carried from bf48b28) | PASS |
| C21 | every `{business_id}` route has require_member; walk catches a missing one | `test_every_business_route_requires_member` PASSED | `test_businesses.py:573` `walked == documented`; `:574` `business_routes_missing_member(app) == []`; `:584` careless route reported (refreshed; carried from bf48b28) | PASS |
| C22 | 4 new route-methods -> 401 via existing walk | `test_every_v1_route_requires_token` PASSED | `services/core/tests/test_auth.py:206` `response.status_code == 401` over every `/v1` OpenAPI path; `contracts/openapi.json` lists `/v1/businesses` [get, post] and `/v1/businesses/{business_id}` [get, patch]. Precision note (unchanged): the four pairs are not named in the test (carried from bf48b28) | PASS |
| C23 | layout: redirect when empty; name in header; error state; Bearer | vitest `businesses > *` (5) PASSED | `frontend/tests/app-layout.test.tsx:74` `redirect('/onboarding/business')`; `:84` header text `'Harbor Street Plumbing'`; `:88` `api.GET` with `Authorization: 'Bearer tok_test'`; `:98-99`, `:117-118` errorTitle, no content (carried from bf48b28) | PASS |
| C24 | onboarding page: redirect '/'; form; error state | vitest `onboarding page > *` (4) PASSED | `frontend/tests/onboarding-page.test.tsx:61` `expect(redirect).toHaveBeenCalledWith('/')`; `:70` heading not null; `:79-80`, `:88-89` errorTitle and no form (carried from bf48b28) | PASS |
| C25 | loading.tsx aria-busy + States.loading label | vitest `loading state` PASSED | `onboarding-page.test.tsx:100-101` `getByLabelText(messages.States.loading)`, `aria-busy` `'true'` (carried from bf48b28) | PASS |
| C26 | page renders wordmark, Step 2 of 5, 5-segment aria-hidden bar (2 accent), heading, intro, 3 labelled controls, 2 hints, Continue, in that document order | vitest `renders the mockup` PASSED | Re-judged at 78b5790. `renderPage()` (`frontend/tests/business-form.test.tsx:64-75`) now renders `BusinessStepPage` itself (`app/onboarding/business/page.tsx`) with `GET /v1/businesses` answering `{items: []}`. The test no longer writes any of the asserted markup. `:101` `await renderPage()`; `:103-114` order list from the wordmark to `copy.continue`; `:117` every part present, `:118` `[...positions].sort(...)).toEqual(positions)`; `:120` `getByRole('heading', { level: 1, name: copy.title })`; `:121` `getByText(copy.intro).tagName).toBe('P')`; `:124` bar `aria-hidden`; `:126-127` 5 segments, 2 `bg-accent`. The round-1 gap is closed | PASS |
| C27 | 13 provinces in order, none selected | vitest `province options` PASSED | `business-form.test.tsx:138` trigger `== copy.provincePlaceholder`; `:139-153` 13 names in order (refreshed; carried from bf48b28) | PASS |
| C28 | 8 zones in order; Winnipeg preselected; London none | vitest `time zone options` PASSED | `business-form.test.tsx:160` `'Central Time (Winnipeg)'`; `:161-170` 8 names; `:175` `copy.timeZonePlaceholder` (refreshed; carried from bf48b28) | PASS |
| C29 | Quebec error, text-danger-text, aria-describedby; Ontario removes | vitest `quebec message` PASSED | `business-form.test.tsx:185` `toContain('text-danger-text')`; `:186` `describedBy(provinceField())).toContain(holder?.id)`; `:190` `queryByText(errors.quebec)).toBeNull()` (refreshed; carried from bf48b28) | PASS |
| C30 | 4 cases: 0 action calls, message linked, focus first error | vitest `client validation: *` (4) PASSED | `business-form.test.tsx:211` `not.toHaveBeenCalled()`; `:216` `describedBy(control)).toContain(message?.id)`; `:218` `document.activeElement).toBe(control)` (refreshed; carried from bf48b28) | PASS |
| C31 | action outcomes, exact body, Bearer | vitest `create business action > *` (5) PASSED | `frontend/tests/create-business-action.test.ts:45-49` redirect '/' + exact body and header; `:57`; `:73-76` `{ fieldErrors: { province: 'quebec' } }`; `:82-83`, `:89-90` `{ formError: true }` (carried from bf48b28) | PASS |
| C32 | form error above Continue, values kept | vitest `save error keeps values` PASSED | `business-form.test.tsx:241` `toBe(errors.saveFailed)`; `:242-243` DOCUMENT_POSITION_FOLLOWING; `:245-247` name, Ontario, Eastern Time (refreshed; carried from bf48b28) | PASS |
| C33 | pending: aria-busy, disabled, 1 call | vitest `pending state` PASSED | `business-form.test.tsx:261` `aria-busy` `'true'`; `:262` `disabled).toBe(true)`; `:267` `toHaveBeenCalledTimes(1)` (refreshed; carried from bf48b28) | PASS |
| C34 | new user: onboarding -> / with name in header < 120000 ms | Playwright `C34 new user creates a business` ok | `frontend/e2e/onboarding.spec.ts:46` `toBe(STEP)`; `:50` `toBe('/')`; `:51` `toContainText('Harbor Street Plumbing')`; `:54` `toBeLessThan(120_000)` (carried from bf48b28; lines unchanged) | PASS |
| C35 | user with business -> / | Playwright `C35 user with a business skips onboarding` ok | `onboarding.spec.ts:128` `expect.poll(() => pathOf(page)).toBe('/')` (refreshed; carried from bf48b28) | PASS |
| C36 | Quebec message; stays; no business | Playwright `C36 quebec shows not available` ok | `onboarding.spec.ts:63`, `:65` `QUEBEC_ERROR` visible; `:66` `toBe(STEP)`; `:71-72` after reload still STEP with heading (carried from bf48b28) | PASS |
| C37 | 375 no overflow; column <= 480 centred; >= 44px; keyboard only incl. arrow keys; axe 0 | Playwright `C37 layout keyboard and axe` ok | Re-judged at 78b5790: `onboarding.spec.ts:79` `scrollWidth <= 375`; `:82` `axe.violations).toEqual([])`; `:91` `height >= 44`; `:96` width `<= 480`; `:99` `abs(left - right) <= 1`; `:111-114` `press('ArrowDown')` then `'Prince Edward Island'` `toBeFocused()`, `press('ArrowUp')` then `'Ontario'` `toBeFocused()`; `:121` `pathOf(page)).toBe('/')`. The keyboard path now covers Tab, typing, arrow keys and Enter. The round-1 precision note is closed | PASS |
| C38 | no literal copy; every key exists | vitest `no literal copy in onboarding, and every key exists` PASSED | `frontend/tests/onboarding-copy.test.ts:63` literals `toEqual([])`; `:66` unresolved keys `toEqual([])` (carried from bf48b28) | PASS |
| C39 | existing shell/home/auth/api-check specs pass with setup giving the user a business | `proofs.sh c39` 39 passed, `PASS c39`, exit 0 | `.specs/features/11-accounts-businesses-and-access/proofs.sh:14-16` runs the four files, `--grep-invert "C42"`, fails on non-zero. Precision gap (unchanged, open with the user): the claim says "unchanged in their assertions", but `frontend/e2e/shell.spec.ts` spec 07 C11 now asserts the business name. The checks.md Handoff records this as settled mid-build; the approved claim text was not amended (carried from bf48b28) | PASS |
| C40 | one created + one updated log line with ids; no name | `test_business_logs` PASSED | `test_businesses.py:603-604` `len(created) == 1`, `len(updated) == 1`; `:606-607` business_id and `user_id == str(caller.id)`; `:608` `"Secret Name Plumbing" not in text_out` (refreshed; carried from bf48b28) | PASS |
| C41 | no clerk_user_id; no foreign business id | `test_no_foreign_fields` PASSED | `test_businesses.py:636` `"clerk_user_id" not in set(_keys(...))`; `:638` `business_b not in response.text` (refreshed; carried from bf48b28) | PASS |

Level judgment (carried from bf48b28): status and shape claims are asserted at the HTTP boundary through `TestClient`. C9, C13 and C17 sit at the service or dependency layer, as checks.md declares. C26 now renders the real route component, which is the level its claim names. No level gaps.

## Swept existing

Carried from bf48b28. The fix diff touches no source file, so nothing these rows cite has changed.
- 401 walk: `services/core/tests/test_auth.py:193-206`. Present.
- `auth.protect()`: in `frontend/app/onboarding/layout.tsx` and `frontend/app/onboarding/business/page.tsx:10`; `tests/auth-protect.test.ts` passed. Present.
- `require_member`: `services/core/app/auth.py:88-110`. Present.
- Logs: `services/core/app/modules/accounts/service.py:101` and `:142` carry ids only. Present.
- data lifecycle `n/a`: approved policy.

## Gate

`python .claude/skills/tlc-spec-lean/scripts/validate_verification.py 11-accounts-businesses-and-access` exits 0 with `validate_verification: 0 error(s), 0 warning(s) across [11-accounts-businesses-and-access]`. Proofs at `78b5790`: 58 pytest, 26 vitest, 4 Playwright (plus 2 setup) and 39 Playwright (c39). All passed, 0 failed.
