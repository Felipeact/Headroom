# 25 - Suggested fixes verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 71d6587..f839b7e
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

Under `light`, step 1 (binding sources), the `Coverage` recompute, the `Test policy` verdicts and fault injection do not run. `checks.md` carries no `Test policy` section. The mockup `design/mockups/alert.dc.html` was opened anyway: its "Ways to fix it" section (lines 71-102) shows $12,750, $17,650 and $5,150, a $14,500 Coastal payment moved to Nov 19, Birch's $9,600 pulled from Nov 17 to Nov 10, and $2,000 drawn of $20,000 available. These match C9's literals (1275000, 1765000, 515000, -1450000, 960000, 200000, 2000000). No contradiction.

## Checks

All targeted proofs ran in one invocation from `services/core`: `uv run pytest tests/test_alert_fixes.py tests/test_alerts_sample.py tests/test_alert_check.py tests/test_alerts_api.py tests/test_migrations.py tests/test_auth.py -v -k "<the 22 names below>"`. Result: 31 passed, 73 deselected, exit 0. Each named test appears individually as PASSED in that output. Every test file except `test_auth.py` is in the feature diff. `test_auth.py`, `test_access`, `test_alert_not_found`, `test_bad_state` and `test_dismiss_resolved_or_dismissed` are spec 24 proofs that C18 reruns by design.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `pay_early` from the arrives_after item, 7 days earlier, and none without one | `test_pay_early` PASSED | `services/core/tests/test_alert_fixes.py:84` - `assert fix.date == date(2026, 11, 10)` (exactly one fix via `(fix,) =` at :80); `:90` - `assert of_kind(fixes([COASTAL], []), "pay_early") == []` | PASS |
| C2 | the largest cause moves 7 days later, the earliest on a tie, and none without causes | `test_move_payment` PASSED | `services/core/tests/test_alert_fixes.py:98` - `assert fix.date == date(2026, 11, 19)`; `:108` - `assert fix.original_date == date(2026, 11, 10)` (tie); `:111` - `assert of_kind(fixes([BIRCH], []), "move_payment") == []` | PASS |
| C3 | line qualification over 6 cases, the choice and tie-break by name, and `repay_on` | `test_draw_credit[lines0..lines5]` + `test_draw_credit_choice_and_repay` PASSED | `services/core/tests/test_alert_fixes.py:117-122` parametrization (200000, 185000, then None for 184999, USD, null and no line); `:132` - `assert fix.amount_cents == drawn`; `:129` - `assert found == []`; `:135` - `assert fix.repay_on == date(2026, 11, 17)`; `:148` - `assert fix.description == "A line"`; `:153-154` - `"B line"` and `repay_on == date(2026, 11, 16)` | PASS |
| C4 | `financing` without a qualifying line, never with one | `test_financing` PASSED | `services/core/tests/test_alert_fixes.py:160` - `assert fix.amount_cents == 200000`; `:163` - `assert fix.repay_on == date(2026, 11, 16)`; `:170` - `assert of_kind(found, "financing") == []` | PASS |
| C5 | rounds the shortfall up to a whole 100000 for both ways to borrow | `test_borrow_rounding[1-100000, 185000-200000, 200000-200000, 200001-300000]` PASSED | `services/core/tests/test_alert_fixes.py:190` - `assert draw.amount_cents == borrowed`; `:192` - `assert financing.amount_cents == borrowed` | PASS |
| C6 | new lowest balance over 13 weeks, including a move past the last week | `test_new_lowest` PASSED | `services/core/tests/test_alert_fixes.py:202` - `assert found == {"move_payment": 1765000, "pay_early": 1275000, "draw_credit": 515000}`; `:210` - `== 1000000`; `:225` - `assert move.new_lowest_balance_cents == 550000` | PASS |
| C7 | a fix with no gain is dropped | `test_no_gain_dropped` PASSED | `services/core/tests/test_alert_fixes.py:239` - `assert of_kind(found, "move_payment") == []` | PASS |
| C8 | kind order | `test_order` PASSED | `services/core/tests/test_alert_fixes.py:245` - `== ["pay_early", "move_payment", "draw_credit"]`; `:250` - with `financing`; `:255` - `== ["move_payment", "financing"]` | PASS |
| C9 | the sample's 3 fixes through `PUT` and `GET` | `test_sample_fixes` PASSED | `services/core/tests/test_alerts_sample.py:68` - `] == [("pay_early", "Birch & Co, invoice 1057", 960000, "2026-11-17", "2026-11-10", None, None, 1275000), ("move_payment", ..., -1450000, "2026-11-12", "2026-11-19", ..., 1765000), ("draw_credit", "Line of credit", 200000, None, "2026-11-09", "2026-11-17", 2000000, 515000)]` | PASS |
| C10 | fixes are stored in the alert's transaction and visible from a new session in the `alert.created` subscriber | `test_fixes_stored_with_alert` PASSED | `services/core/tests/test_alert_check.py:537` - `assert seen == [expected]` (expected built from `gaps.fixes` at :535, kinds asserted at :536) | PASS |
| C11 | a second check leaves everything unchanged and publishes nothing | `test_fixes_same_twice` PASSED | `services/core/tests/test_alert_check.py:552` - `assert (columns(again), items_of(again.id), fixes_of(again.id)) == before`; `:553` - `assert sent == []` | PASS |
| C12 | a credit drop swaps `draw_credit` for `financing`, moves `updated_at`, no event | `test_credit_drop_switches_to_financing` PASSED | `services/core/tests/test_alert_check.py:578` - `assert [f[0] for f in fixes_of(after.id)] == ["pay_early", "move_payment", "financing"]`; `:583` - `assert after.updated_at == later`; `:587` - `assert sent == []` | PASS |
| C13 | a resolved alert keeps its fixes | `test_resolved_keeps_fixes` PASSED | `services/core/tests/test_alert_check.py:600` - `assert after.state == "resolved"`; `:601` - `assert fixes_of(after.id) == before` | PASS |
| C14 | `fixes` on all 3 routes, the exact keys, int cents with CAD, `[]` when there are none, and `ALERT_KEYS` gains `fixes` | `test_fixes_shape` + `test_list` PASSED | `services/core/tests/test_alerts_api.py:318` - `assert set(fix) == FIX_KEYS`; `:319` - `fix["currency"] == "CAD"`; `:321` - `assert type(fix[key]) is int`; `:330` - `["fixes"] == []`; `:183` - `assert all(set(a) == ALERT_KEYS for a in found)` (`ALERT_KEYS` holds `"fixes"` at :57) | PASS |
| C15 | the `alert_fixes` migration: kind check, cascade, downgrade, `alembic check` | `test_alert_fixes_upgrade_downgrade_and_check` PASSED | `services/core/tests/test_migrations.py:1114` - `assert "ck_alert_fixes_kind" in str(raised.value)`; `:1118` - `assert left == 0`; `:1127-1128` - `"alert_fixes" not in names` and `"alerts" in names`; `:1134` - the `check` returncode is 0 | PASS |
| C16 | the contract has `Alert.fixes` of `Fix` with 4 kinds, and regenerating leaves no diff | `test_contract_fixes` PASSED; `uv run python -m app.export_openapi && (cd ../../frontend && npm run api:types) && git diff --exit-code -- ../../contracts/openapi.json ../../frontend/lib/api/schema.d.ts` exit 0 | `services/core/tests/test_alerts_api.py:338` - `assert fixes["items"] == {"$ref": "#/components/schemas/Fix"}`; `:339` - `["kind"]["enum"] == ["pay_early", "move_payment", "draw_credit", "financing"]` | PASS |
| C17 | every AGENTS.md check passes | API: `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest` (see Gate); web: `npm run lint && npm run typecheck && npm test && npm run build` exit 0 | ruff: "134 files already formatted", "All checks passed!"; mypy: "Success: no issues found in 55 source files"; web: Vitest "Test Files 37 passed (37)", "Tests 287 passed (287)", build route table printed, exit 0. Test-level evidence is C1-C16 and C18, for example `services/core/tests/test_alert_fixes.py:202` | PASS |
| C18 | the 3 routes' error statuses are unchanged | `test_every_v1_route_requires_token`, `test_access`, `test_alert_not_found`, `test_bad_state`, `test_dismiss_resolved_or_dismissed` PASSED | `services/core/tests/test_auth.py:206` - `assert response.status_code == 401`; `services/core/tests/test_alerts_api.py:252` - `is_problem(response, 404)` (non-member); `:260` - `is_problem(dismiss(...), 403)`; `:236` - `is_problem(response, 404)` (unknown alert); `:223` - `is_problem(response, 422)`; `:161` - `is_problem(response, 409)` | PASS |

## Level and sampling notes

These are findings about the checks. None of them makes a check fail, and the profile `light` does not recompute coverage, so they do not change the verdict. They are recorded for the orchestrator.

1. **AC 4's account-type filter is not proven by any check.** `services/core/app/modules/alerts/service.py:107` (`if a.type == "line_of_credit"`) is what keeps a credit card out of `draw_credit`. C10 to C13 monkeypatch `credit_lines`. C9 is the only check that exercises the real function, and the sample's other credit account, `Business Visa` (`services/core/app/fixtures/harbor_street.py:172`), has `available_cents` None, so it would not qualify even without the filter. If the filter were removed, every check would still pass. This is a sampling gap: no check uses a credit card with available credit.
2. **C14 never shows a `draw_credit` fix through a route.** `test_fixes_shape` builds a business with no line, so `available_cents` is only ever asserted as `None` at the route level (`services/core/tests/test_alerts_api.py:322`). An integer `available_cents` on the wire is shown only by C9's equality at `services/core/tests/test_alerts_sample.py:68`, and equality does not check the type. This is a small precision gap against AC 15 ("money only as integer cents").
3. **C15 proves the `ON DELETE CASCADE` and the kind check, but not the primary key `(alert_id, position)`.** Door 1's other columns are held by `alembic check` (`services/core/tests/test_migrations.py:1134`, autogenerate shows no drift against the models), not by a direct assertion. This is acceptable for `light`.
4. **AC 1, "only when a gap exists" (Flow step 2, reading credit lines once per check), has no check.** It is a cost property, not an acceptance criterion, so it is noted only.
5. **Every AC from 1 to 15 maps to at least one check:** AC 1 C10; AC 2 C1; AC 3 C2; AC 4 and AC 5 C3, C5; AC 6 C4, C5; AC 7 C6; AC 8 C7; AC 9 C4, C8; AC 10 C9; AC 11 C11; AC 12 C12; AC 13 C12; AC 14 C13; AC 15 C14. Nothing in the criteria is unchecked, apart from the weakly sampled points in notes 1 and 2.
6. **The spec file `context/specs/25-alerts-suggested-fixes.md` still says "Status: In progress", and its two "Done when" items are not ticked.** That is expected before verification, but the orchestrator owes the Done update.

## Swept existing

- failure modes (AD-047, one transaction): consistent with C10. The subscriber reads fixes from a fresh session after the commit (`services/core/tests/test_alert_check.py:537`).
- authorization: `test_access` and `test_alert_not_found` were rerun green (C18).
- concurrency: the `test_concurrent_checks_one_alert` test is cited. It ran in the full API suite (C17) and was not re-read in detail.
- observability: `test_money_and_payloads` is cited. It ran in the full API suite.

## Gate

`uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest` (services/core, at f839b7e) - 856 passed, 0 failed, 5 deselected by the project's default `-m 'not plaid_sandbox'` filter, exit 0 in 279.56s

`npm run lint && npm run typecheck && npm test && npm run build` (frontend) - 287 passed, 0 failed, exit 0

Targeted proofs C1-C16 and C18 - 31 passed, 0 failed
