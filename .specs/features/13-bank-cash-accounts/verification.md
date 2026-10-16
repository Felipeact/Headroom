# 13-bank-cash-accounts verification

**Verdict**: PASS
**Profile**: light
**Diff range**: ed7529b..84a16bf29c0c75b3208735de66d72f4af38e9170
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

## Binding sources

Not owed under `light` (step 1 runs under `ui`). `context/specs/13-bank-cash-accounts.md` and `design/mockups/onboarding-3-choose-accounts.dc.html` were not compared element by element against the checks; no contradiction or coverage claim is made here. The `Coverage` recompute and fault injection were also not run (not owed under `light`), and no fault was injected.

## Checks

All proofs run by the verifier at `84a16bf`. API batch: `uv run pytest tests/test_bank_accounts.py tests/test_plaid_client.py tests/test_migrations.py tests/test_bank_connect.py tests/test_auth.py -k "<32 names>" -q -p no:logging -rA` - 46 passed, each listed individually as PASSED. Web batch: `npx vitest run tests/connect-bank-action.test.ts tests/accounts-page.test.tsx tests/choose-accounts.test.tsx tests/update-account-action.test.ts tests/onboarding-copy.test.ts lib/format.test.ts --reporter=verbose` - 6 files, 48 tests passed, each listed. Playwright `npx playwright test e2e/choose-accounts.spec.ts` - 4 passed (setup x2, C49, C50). `proofs.sh c31 c52` - `PASS c31`, `PASS c52`; `proofs.sh c51` - 46 passed, `PASS c51` (second run, see notes); `proofs.sh c53` - `PASS c53`.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | six accounts, only CAD checking included | pytest `test_connect_includes_cad_checking_only` PASSED | `services/core/tests/test_bank_accounts.py:211` - `assert returned == expected`; `:212` - rows `== expected` (A checking True, five others False) | PASS |
| C2 | `available_cents` half-even cents; real client carries `available` | pytest `test_available_cents_mapping[20000.0-2000000]`, `[1234.565-123456]`, `[None-None]`, `test_plaid_client.py::test_available_balance[150.25]`, `[None]` PASSED | `services/core/tests/test_bank_accounts.py:230` - `body["accounts"][0]["available_cents"] == expected`; `:231` row; `services/core/tests/test_plaid_client.py:154` - `accounts.accounts[0].available == available` | PASS |
| C3 | include excluded CAD savings and checking -> 200, row true | pytest `test_include_cash_account` PASSED | `services/core/tests/test_bank_accounts.py:255` - `status_code == 200`; `:258` - `body["included"] is True`; `:259` - `rows(...)[name].included is True` | PASS |
| C4 | credit card / line of credit -> 409 problem+json, exact detail, no row changes | pytest `test_include_not_cash[include_credit_conflicts-card]`, `[...-line]` PASSED | `services/core/tests/test_bank_accounts.py:288-291` - `== 409`, content-type `== "application/problem+json"`, `detail == detail` (`NOT_CASH_CREDIT`), `snapshot(business_id) == before` | PASS |
| C5 | `other` -> 409 exact detail, no row | pytest `test_include_not_cash[include_other_conflicts]` PASSED | `services/core/tests/test_bank_accounts.py:290` - `response.json()["detail"] == detail` (`NOT_CASH_OTHER`); `:291` snapshot unchanged | PASS |
| C6 | USD checking and savings -> 409 currency detail | pytest `test_include_not_cash[include_non_cad_conflicts-checking]`, `[...-savings]` PASSED | `services/core/tests/test_bank_accounts.py:290` - detail `== NOT_CASH_CURRENCY`; `:291` snapshot unchanged | PASS |
| C7 | exclude non-primary -> 200 false, row false | pytest `test_exclude_non_primary` PASSED | `services/core/tests/test_bank_accounts.py:309` - `response.json()["included"] is False`; `:310` - row `.included is False` | PASS |
| C8 | direct UPDATE included=true raises IntegrityError naming `ck_bank_accounts_included_cash` | pytest `test_included_cash_constraint` PASSED | `services/core/tests/test_bank_accounts.py:319` - `pytest.raises(IntegrityError, match="ck_bank_accounts_included_cash")` over Visa, Money market, US chequing | PASS |
| C9 | migration columns, checks, partial index, backfill, downgrade, check | pytest `test_bank_accounts_cash_columns_upgrade_backfill_downgrade_and_check` PASSED | `services/core/tests/test_migrations.py:453` - `index.endswith("WHERE is_primary")`; `:454` - `backfilled == {...High checking: (True, True, None)...}`; `:469` - `not {"included","is_primary","available_cents"} & remaining` | PASS |
| C10 | first-connect primary by balance, null last, name; savings never wins | pytest `test_first_connect_primary[largest_balance]`, `[null_last_then_name]`, `[tie_by_name]` PASSED | `services/core/tests/test_bank_accounts.py:356` - primaries in body `== [expected]`; `:357` - `primaries(business_id) == [expected]` | PASS |
| C11 | savings + credit card -> 0 primary | pytest `test_no_included_no_primary` PASSED | `services/core/tests/test_bank_accounts.py:370` - `primaries(business_id) == []` | PASS |
| C12 | second connect keeps primary | pytest `test_second_connect_keeps_primary` PASSED | `services/core/tests/test_bank_accounts.py:382` - new accounts `== [False]`; `:383` - `primaries == ["First"]` | PASS |
| C13 | move primary | pytest `test_move_primary` PASSED | `services/core/tests/test_bank_accounts.py:400` - `primary is True`; `:401` - `snapshot == {"Main": (True, False), "Ops": (True, True)}` | PASS |
| C14 | include and make primary in one call | pytest `test_include_and_make_primary` PASSED | `services/core/tests/test_bank_accounts.py:420` - `(included, primary) == (True, True)`; `:421` - previous primary `(True, False)` | PASS |
| C15 | primary on excluded -> 409 exact detail | pytest `test_primary_requires_included` PASSED | `services/core/tests/test_bank_accounts.py:437-439` - `== 409`, `detail == PRIMARY_NOT_INCLUDED`, snapshot unchanged | PASS |
| C16 | exclude primary -> 409 exact detail | pytest `test_exclude_primary_conflicts` PASSED | `services/core/tests/test_bank_accounts.py:455-457` - `== 409`, `detail == EXCLUDE_PRIMARY`, snapshot unchanged | PASS |
| C17 | first include with no primary becomes primary | pytest `test_first_include_becomes_primary` PASSED | `services/core/tests/test_bank_accounts.py:476` - `(True, True)`; `:477` - `primaries == ["Reserve"]` | PASS |
| C18 | unique primary index and primary-included check; one per business allowed | pytest `test_primary_constraints` PASSED | `services/core/tests/test_bank_accounts.py:497` - other business `[True]`; `:519` - `pytest.raises(IntegrityError, match=constraint)` for `uq_bank_accounts_primary_business_id` and `ck_bank_accounts_primary_included` | PASS |
| C19 | two concurrent primary moves -> exactly 1 primary | pytest `test_concurrent_primary_moves` PASSED | `services/core/tests/test_bank_accounts.py:573` - `errors == []`; `:575` - `len(primaries(...)) == 1`; `:576` - in `{"Ops","Spare"}` | PASS |
| C20 | two concurrent first connects -> 2 connections, 1 primary | pytest `test_concurrent_connects_one_primary` PASSED | `services/core/tests/test_bank_accounts.py:615` - `count == 2`; `:616` - `len(primaries(...)) == 1` | PASS |
| C21 | list connections shape and order; empty `{"items": []}` | pytest `test_list_connections` PASSED | `services/core/tests/test_bank_accounts.py:626` - `empty.json() == {"items": []}`; `:638` - ids `== [first, second]`; `:640` key set; `:641` - names `== ["Alpha","Zed"]` | PASS |
| C22 | account keys exactly nine on GET/PATCH/POST; no Plaid ids in bodies | pytest `test_account_json_keys`, `test_bank_connect.py::test_connect_returns_connection` PASSED | `services/core/tests/test_bank_accounts.py:658` - `all(set(a) == ACCOUNT_KEYS ...)`; `:662` - `not any(pid in body ...)`; `services/core/tests/test_bank_connect.py:298` - `[set(a) ...] == [ACCOUNT_KEYS] * 3` | PASS |
| C23 | non-member -> 404 "Business not found." | pytest `test_non_member_gets_404` PASSED | `services/core/tests/test_bank_accounts.py:679-681` - `== 404`, `detail == "Business not found."`, snapshot unchanged | PASS |
| C24 | non-owner role -> 403 exact detail on both routes | pytest `test_non_owner_gets_403` PASSED | `services/core/tests/test_bank_accounts.py:702-704` - `== 403`, `detail == "You don't have permission to do this."`, snapshot unchanged | PASS |
| C25 | foreign or random account -> 404 "Account not found." | pytest `test_foreign_account_gets_404` PASSED | `services/core/tests/test_bank_accounts.py:721-723` - `== 404`, `detail == "Account not found."`, snapshot unchanged | PASS |
| C26 | route walk lists both routes; no route missing member | pytest `test_account_routes_require_member` PASSED | `services/core/tests/test_bank_accounts.py:733-735` - both tuples `in walked`; `business_routes_missing_member(app) == []` | PASS |
| C27 | both routes 401 without token | pytest `test_auth.py::test_every_v1_route_requires_token` PASSED | `services/core/tests/test_auth.py:206` - `response.status_code == 401, (method, path)` over every `/v1` path in `app.openapi()`, which holds both new paths (C52) | PASS |
| C28 | invalid bodies and malformed ids -> 422 with `errors`, no row change | pytest `test_patch_validation[empty]`, `[extra]`, `[primary_false]`, `[primary_null]`, `[included_not_bool]`, `test_patch_validation_malformed_ids` PASSED | `services/core/tests/test_bank_accounts.py:760-762` - `== 422`, `errors` truthy, snapshot unchanged; `:782` - `e["loc"][-1] == param` | PASS |
| C29 | audit rows exact; unchanged and 409 write none | pytest `test_update_audited` PASSED | `services/core/tests/test_bank_accounts.py:810` - `entry.details == {"included": True}`; `:819` - `[{"included": True, "primary": True}]`; `:825` - `len(updated_audits(...)) == 2` | PASS |
| C30 | one JSON log line, no names/masks/balances | pytest `test_update_logged` PASSED | `services/core/tests/test_bank_accounts.py:847-850` - `len(events) == 1`, ids, `included is True`; `:852` - `secret not in out` | PASS |
| C31 | two sandbox banks, 2 items, one primary | `bash proofs.sh c31` - 1 passed, `PASS c31` | `services/core/tests/test_bank_accounts_sandbox.py:53` - institution names `== list(BANKS.values())` (TD `ins_42`, RBC `ins_39`); `:55` currency set; `:56` - `sum(a["primary"] ...) == 1`; `:65` removes items | PASS |
| C32 | connect action 201 redirects to `/onboarding/accounts` | vitest `connect bank action > 201 redirects to choosing accounts...` and five other outcomes passed | `frontend/tests/connect-bank-action.test.ts:42` - `expect(redirect).toHaveBeenCalledWith('/onboarding/accounts')`; `:56`, `:63`, `:70` - `not.toHaveBeenCalled()` | PASS |
| C33 | page redirects, view, bearer token, five failure states | vitest `accounts page > no business`, `no connection`, `a business with a connection`, five `... error state, no Continue button` passed | `frontend/tests/accounts-page.test.tsx:108` - `'/onboarding/business'`; `:116` - `'/onboarding/bank'`; `:128-131` - GET with `Authorization: 'Bearer tok_test'`; `:167-168` - `States.errorTitle` shown, `continueButton()` null | PASS |
| C34 | no `loading.tsx` under accounts | vitest `uses the onboarding loading state` passed | `frontend/tests/accounts-page.test.tsx:173` - `existsSync('app/onboarding/accounts/loading.tsx')).toBe(false)` | PASS |
| C35 | mockup order, header bar 3 of 5, icon, no institution heading | vitest `renders the mockup`, `header: the wordmark, step 3 of 5...` passed | `frontend/tests/choose-accounts.test.tsx:107` - `inOrder(nodes)` (heading, intro, 3 cards, note, connect, continue); `:109` - no `h2`; `frontend/tests/accounts-page.test.tsx:149` - `bg-accent` segments `toHaveLength(3)` | PASS |
| C36 | two banks intro and headings in order | vitest `two banks` passed | `frontend/tests/choose-accounts.test.tsx:119` - headings `== ['Harbor Community Bank','RBC Royal Bank']`; `:120` - `inOrder(...)` | PASS |
| C37 | card header mask, type labels, money formats | vitest `card header` passed | `frontend/tests/choose-accounts.test.tsx:137` - `'••2381 · Checking'`; `:145` - `'US$1,200'`; `:146` - no `$` for null balance | PASS |
| C38 | checking switch aria-checked and name | vitest `checking switch` passed | `frontend/tests/choose-accounts.test.tsx:155` - `aria-checked` `'true'`; `:158` - `'false'` | PASS |
| C39 | savings two-option group reflects `included` | vitest `savings segmented` passed | `frontend/tests/choose-accounts.test.tsx:169` - `[yes, no] aria-checked == ['false','true']`; `:172-173` reversed for included (see note 3) | PASS |
| C40 | credit shows available, note, no controls | vitest `credit card and line of credit` passed | `frontend/tests/choose-accounts.test.tsx:187` - `'$20,000'`; `:192` - balance `'$812'` absent; `:193` no amount; `:196-198` no switch/radiogroup/radio | PASS |
| C41 | other and non-CAD notes, no controls | vitest `cannot count: other type and non-CAD` passed | `frontend/tests/choose-accounts.test.tsx:212-214` - `otherNote`, `currencyNote` x2; `:217-219` no controls | PASS |
| C42 | primary radio only on included; one group; one checked | vitest `primary radio` passed | `frontend/tests/choose-accounts.test.tsx:227` - `toHaveLength(2)`; `:228` checked `'true'`; `:230` savings none; `:232` - `groups.size == 1` | PASS |
| C43 | update action ids, bodies, bearer, revalidate; error outcomes | vitest `update account action` 8 cases passed | `frontend/tests/update-account-action.test.ts:46-51` - PATCH with `{business_id, account_id}`, `body`, `Authorization: 'Bearer tok_test'`, `revalidatePath('/onboarding/accounts')`; `:59-60` - `{error:'saveFailed'}`, not revalidated | PASS |
| C44 | view calls action, disables during save, error alert, reverts | vitest `saves changes` passed | `frontend/tests/choose-accounts.test.tsx:242` - `{ included: false }`; `:251` - every control `disabled` true; `:271-272` alert `saveFailed` above buttons; `:274` - switch back to `'true'` | PASS |
| C45 | connect another bank: token, open once, outcomes | vitest `connect another bank` passed | `frontend/tests/choose-accounts.test.tsx:280` token; `:282` - `open` called once; `:286` - `connectBank(BUSINESS,'public-sandbox-2')`; `:287`, `:291`, `:298` alerts; `:294` - `''` on `onExit(null)` | PASS |
| C46 | Continue navigates or shows none-included alert | vitest `continue`, `continue with nothing included` passed | `frontend/tests/choose-accounts.test.tsx:304` - `push('/')`; `:312-313` - not pushed, alert `noneIncluded` | PASS |
| C47 | no literal copy; every key exists | vitest `no literal copy in onboarding, and every key exists` passed | `frontend/tests/onboarding-copy.test.ts:63` - literals `toEqual([])`; `:66` - unresolved keys `toEqual([])` | PASS |
| C48 | `formatMoney` USD and CAD | vitest `formatMoney > spec 13 C48 other currencies` passed | `frontend/lib/format.test.ts:25-27` - `'US$1,200'`, `'$3,200'`, `'$3,200'` | PASS |
| C49 | e2e two banks, include savings, move primary, reload, Continue | Playwright `C49 owner chooses cash accounts across two banks` ok (36.3s) | `frontend/e2e/choose-accounts.spec.ts:46` - one checked primary; `:53` - RBC heading; `:73-74` - after reload `aria-checked` `'true'`; `:78` - path `'/'` | PASS |
| C50 | 375px layout, 44px targets, 1280 column, keyboard, axe | Playwright `C50 layout keyboard and axe` ok (22.6s) | `frontend/e2e/choose-accounts.spec.ts:86` - `scrollWidth <= 375`; `:94` order; `:107` - `height >= 44`; `:116` - `axe.violations == []`; `:140`, `:143` column | PASS |
| C51 | spec 12 step 3 now lands on accounts; existing e2e pass | `bash proofs.sh c51` - 46 passed, `PASS c51` (run 2; see note 1) | `frontend/e2e/bank-connect.spec.ts:42` - path `'/onboarding/accounts'`; `:44` - then `'/'`; `:46` - `< 120_000` | PASS |
| C52 | generated files current; both paths present | `bash proofs.sh c52` - `PASS c52`, `git status` clean after | `.specs/features/13-bank-cash-accounts/proofs.sh:39` - `git diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts`; `:43` - grep for both paths | PASS |
| C53 | all AGENTS.md checks | `bash proofs.sh c53` - ruff format/check clean, mypy no issues, pytest 277 passed, vitest 185 passed, build succeeded, `PASS c53` | `.specs/features/13-bank-cash-accounts/proofs.sh:51-55` - the full command chain | PASS |

## Level and sampling

- HTTP-shaped claims (C3-C7, C13-C17, C21-C25, C28) are asserted through `TestClient` at the route; C19/C20 at the service layer and C8/C18 against the database, as `checks.md` states. No level gap found.
- C27's proof is a test this feature did not touch, but it walks `app.openapi()` paths, which now contain both new routes (C52 confirms), so it exercises the new behaviour.
- C34 is a file-existence assertion; adequate for "the onboarding loading state is the one in force".
- Sampling: C10 covers the three ordering keys plus the savings exclusion in one case; C28 covers all five bodies and three malformed ids. No claim found proven on fewer cases than it names.

## Swept existing

- Unauthorised page state (Coverage note): `frontend/tests/auth-protect.test.ts:24-27` walks every `page|layout.tsx` under `app/` and requires `await auth.protect()`; `frontend/app/onboarding/accounts/page.tsx:11` has it. Constraint present.
- C27 "existing walk": present at `services/core/tests/test_auth.py:193-206`.
- No other `Swept` row cites an existing constraint; the rest point to checks above.

## Handoff decisions judged

- Spec 12 test edits (`test_bank_connect.py`, `test_migrations.py`, `connect-bank-action.test.ts`, `bank-connect.spec.ts`): diffs only widen `ACCOUNT_KEYS` by the three new fields, pin spec 12's migration test to its own revision `5db30d28e759` (it still ends with `upgrade head` + `check`), change the redirect target to `/onboarding/accounts`, and move the Plaid helpers into `onboarding-steps.ts` while adding a `Continue` step before the `/` assertion. No assertion removed or loosened.
- Segmented control asserted via `aria-checked` (radiogroup) rather than the mockup's `aria-pressed`: the selected state is still asserted exactly; noted as a precision gap in C39's wording ("pressed"), not a failing one.
- Primary `RadioGroup` `tabIndex={-1}`: removes only the group root as a tab stop; Radix roving focus keeps the checked item tabbable. C50's keyboard assertions still run and pass.
- `c51` excludes spec 07's `no sentry without dsn`: same exclusion as spec 12's verified `c44`; that test needs an empty DSN and is not part of this feature.

## Notes

1. `proofs.sh c51` first run: 45 passed, 1 failed - `e2e/auth.spec.ts:99` `C26 auth pages 375 keyboard axe`, axe `color-contrast` on `/sign-up` (fg `#fdfbfb` on `#ffffff`, a Clerk element mid-render). That file and the sign-in/up pages are untouched in this range; the second run passed 46/46. Flaky test outside the diff.
2. A single combined Playwright invocation of `choose-accounts.spec.ts` plus the six c51 specs took 21.7 min and failed C49, C50 and spec 12's C41 with a server-side `network error` in `BankStepPage` under parallel load. Run as the checks prescribe (separate invocations) all passed. Load sensitivity of the sandbox e2e suite, not a defect in the claimed behaviour.
3. C39 wording says "buttons ... pressed"; the shipped control is a Radix radiogroup with `aria-checked`, a builder decision recorded in Handoff and not asked of the user. Binding-source comparison is not owed under `light`; flagged for the user's attention.

## Gate

`python3 .claude/skills/tlc-spec-lean/scripts/validate_verification.py 13-bank-cash-accounts` - exit 0, "0 error(s), 0 warning(s)". Proof totals at HEAD: pytest 46/46 targeted + 277 full; vitest 48/48 targeted + 185 full; Playwright 4/4 (choose-accounts) + 46/46 (c51 run 2).
