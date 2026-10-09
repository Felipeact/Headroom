# 25 - Suggested fixes checks

Profile: light
Plan: `.specs/features/25-alerts-suggested-fixes/plan.md`

18 checks in 3 slices · 2 one-way doors · 0 open

All API proofs run from `services/core`. Test files: `tests/test_alert_fixes.py` (new, pure: the fix rules over hand-built gaps, items, weeks and credit lines), `tests/test_alert_check.py` (the handler on hand-built forecasts), `tests/test_alerts_api.py` (routes), `tests/test_alerts_sample.py` (the sample end to end), `tests/test_migrations.py` (the table). Unless a check says otherwise, the pure checks use a gap 2026-11-09..2026-11-15 with `lowest_balance_cents` 315000 and `shortfall_cents` 185000 against a minimum of 500000.

## Checks

### S1 - Each alert offers the fixes its rules allow · ~30k

**C1** - With an `arrives_after` item +960000 "Birch & Co, invoice 1057" on 2026-11-17, there is exactly one `pay_early` fix: `amount_cents` 960000, `original_date` 2026-11-17, `date` 2026-11-10, and the item's `description` and `counterparty`. Without an `arrives_after` item there is no `pay_early` fix (AC 2)
Proof: `uv run pytest tests/test_alert_fixes.py -k test_pay_early`

**C2** - With causes -1450000 on 2026-11-12 and -1120000 on 2026-11-13, the one `move_payment` fix is the -1450000 item: `original_date` 2026-11-12, `date` 2026-11-19, with its `description` and `counterparty`. With two causes of -1000000 on 2026-11-12 and 2026-11-10, it is the one on 2026-11-10. Without causes there is no `move_payment` fix (AC 3)
Proof: `uv run pytest tests/test_alert_fixes.py -k test_move_payment`

**C3** - Line-of-credit qualification, table-driven at shortfall 185000: available 2000000 CAD → `draw_credit` of 200000; available exactly 185000 → `draw_credit` of 185000 (capped); available 184999 → none; available 2000000 in `USD` → none; available null → none; no line → none. With lines "B line" 500000 and "A line" 2000000, it draws on "A line"; with two lines of 500000, it draws on the one first by name. The fix has `date` 2026-11-09 (`starts_on`), `description` the account name, `counterparty` null, `available_cents` the line's, and `repay_on` the `arrives_after` date 2026-11-17, or 2026-11-16 without one (AC 4, AC 5, Done when 2)
Proof: `uv run pytest tests/test_alert_fixes.py -k test_draw_credit`

**C4** - With no qualifying line, there is exactly one `financing` fix: `amount_cents` 200000, `date` 2026-11-09, `repay_on` 2026-11-16, `description`, `counterparty` and `available_cents` null. With a qualifying line there is no `financing` fix, so never both (AC 6, AC 9)
Proof: `uv run pytest tests/test_alert_fixes.py -k test_financing`

**C5** - The borrowed amount rounds the shortfall up to a whole 100000: shortfall 1 → 100000, 185000 → 200000, 200000 → 200000, 200001 → 300000, for both `draw_credit` (ample credit) and `financing` (AC 4, AC 6)
Proof: `uv run pytest tests/test_alert_fixes.py -k test_borrow_rounding`

**C6** - New lowest balance over 13 hand-built weeks (week of 2026-11-09 at 315000, week of 2026-12-07 at 1795319, the rest at 3000000): moving -1450000 from 2026-11-12 to 2026-11-19 gives 1765000; paying +960000 on 2026-11-10 instead of 2026-11-17 gives 1275000; borrowing 200000 from 2026-11-09 to 2026-11-17 gives 515000. With the week of 2026-12-07 at 1000000 instead, the move gives 1000000 (another week stays the lowest). Moving -100000 from 2026-12-23 to 2026-12-30 (after the last week) raises the week of 2026-12-21 by 100000 (AC 7)
Proof: `uv run pytest tests/test_alert_fixes.py -k test_new_lowest`

**C7** - A fix whose new lowest is not above the alert's lowest is left out: in a 2-week gap (weeks of 2026-11-09 at 400000 and 2026-11-16 at 315000), moving a cause from 2026-11-12 to 2026-11-19 leaves the lowest at 315000, so there is no `move_payment` fix (AC 8)
Proof: `uv run pytest tests/test_alert_fixes.py -k test_no_gain_dropped`

**C8** - Fixes come in kind order: with every rule applying, [`pay_early`, `move_payment`, `draw_credit`]; with no qualifying line, [`pay_early`, `move_payment`, `financing`]; with only a cause, [`move_payment`, `financing`] (AC 9)
Proof: `uv run pytest tests/test_alert_fixes.py -k test_order`

**C9** - Sample (seed 0, clock 2026-09-26) loaded, then `PUT` minimum 500000: the one alert's `fixes` are exactly [`pay_early` "Birch & Co, invoice 1057" +960000 2026-11-17 → 2026-11-10, new lowest 1275000; `move_payment` "Coastal Supply Co, quarterly order" -1450000 2026-11-12 → 2026-11-19, new lowest 1765000; `draw_credit` "Line of credit" 200000 on 2026-11-09, `repay_on` 2026-11-17, `available_cents` 2000000, new lowest 515000] (AC 10, Done when 1)
Proof: `uv run pytest tests/test_alerts_sample.py -k test_sample_fixes`

**C10** - A check on a forecast with one gap, an `arrives_after` item and a qualifying line stores the alert with its fixes: a new session opened inside the `alert.created` subscriber reads the same fixes the pure rules return for that gap (AC 1)
Proof: `uv run pytest tests/test_alert_check.py -k test_fixes_stored_with_alert`

### S2 - Fixes stay in step with their alert · ~15k

**C11** - Running the check a second time on the same forecast, minimum and credit lines leaves the alert's `updated_at`, its items and its fixes unchanged, and publishes 0 events (AC 11)
Proof: `uv run pytest tests/test_alert_check.py -k test_fixes_same_twice`

**C12** - With the forecast and minimum unchanged, lowering the line's `available_cents` from 2000000 to 100000 and re-checking at a later clock replaces `draw_credit` with `financing`, sets `updated_at` to the later clock, keeps every other alert column, and publishes 0 events (AC 12, AC 13)
Proof: `uv run pytest tests/test_alert_check.py -k test_credit_drop_switches_to_financing`

**C13** - When an alert's gap leaves the forecast and the alert is resolved, its stored fixes are exactly those it had before the resolving check (AC 14)
Proof: `uv run pytest tests/test_alert_check.py -k test_resolved_keeps_fixes`

**C14** - `GET .../alerts`, `GET .../alerts/{id}` and `POST .../dismiss` each return `fixes` on the `Alert`. Each fix's keys are exactly `kind`, `amount_cents`, `currency`, `date`, `original_date`, `repay_on`, `description`, `counterparty`, `available_cents`, `new_lowest_balance_cents`, every amount is an `int` next to `currency` "CAD", and an alert with no fixes returns `"fixes": []`. Spec 24's `ALERT_KEYS` (read by `test_list` and `test_get_one`) gains `fixes` (the approved door 2 change) (AC 15)
Proof: `uv run pytest tests/test_alerts_api.py -k test_fixes_shape`
Proof: `uv run pytest tests/test_alerts_api.py -k test_list`

### S3 - Doors and the contract · ~10k

**C15** - The migration creates `alert_fixes`: a fix with `kind` "split" fails on `ck_alert_fixes_kind`, deleting an alert deletes its fixes, downgrade to the spec 24 revision drops the table and keeps `alerts`, and `alembic check` is clean at head (door 1)
Proof: `uv run pytest tests/test_migrations.py -k test_alert_fixes_upgrade_downgrade_and_check`

**C16** - The regenerated contract's `Alert` schema has a `fixes` array of `Fix`, and `Fix`'s `kind` enum is exactly `pay_early`, `move_payment`, `draw_credit`, `financing`. Regenerating `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` leaves no diff (door 2)
Proof: `uv run pytest tests/test_alerts_api.py -k test_contract_fixes`
Proof: `uv run python -m app.export_openapi && (cd ../../frontend && npm run api:types) && git diff --exit-code -- ../../contracts/openapi.json ../../frontend/lib/api/schema.d.ts`

**C17** - Every AGENTS.md check passes: API `ruff format --check`, `ruff check`, `mypy app`, `pytest`; web `lint`, `typecheck`, `test`, `build`
Proof: `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest`
Proof: `cd ../../frontend && npm run lint && npm run typecheck && npm test && npm run build`

**C18** - The 3 routes' error statuses are unchanged with `fixes` added: no token `401`, a non-member `404` and a non-owner dismiss `403`, an unknown alert `404`, a bad `state` `422`, dismissing a resolved alert `409` (spec 24's proofs, rerun)
Proof: `uv run pytest tests/test_auth.py -k test_every_v1_route_requires_token`
Proof: `uv run pytest tests/test_alerts_api.py -k "test_access or test_alert_not_found or test_bad_state or test_dismiss_resolved_or_dismissed"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /v1/businesses/{business_id}/alerts` statuses (4) | 200 C14 · 401 C18 · 404 C18 · 422 C18 | - |
| `GET /v1/businesses/{business_id}/alerts/{alert_id}` statuses (3) | 200 C14 · 401 C18 · 404 C18 | - |
| `POST /v1/businesses/{business_id}/alerts/{alert_id}/dismiss` statuses (5) | 200 C14 · 401 C18 · 403 C18 · 404 C18 · 409 C18 | - |
| fix kinds (4) | `pay_early` C1, C9 · `move_payment` C2, C9 · `draw_credit` C3, C9 · `financing` C4, C12 | - |
| line qualification (6) | enough C3 · exactly the shortfall C3 · one cent short C3 · other currency C3 · available null C3 · no line C3 | - |
| line choice (2) | most available C3 · tie by name C3 | - |
| `repay_on` (3) | line with arrives_after C3 · line without C3 · financing C4 | - |
| rounding edges (4) | 1 C5 · 185000 C5 · 200000 exact C5 · 200001 C5 | - |
| new lowest moves (4) | outgoing later C6 · incoming earlier C6 · borrow and repay C6 · past the last week C6 | - |
| fix changes on re-check (3) | none C11 · fixes only C12 · resolved frozen C13 | - |
| Landing doors (2) | 1 `alert_fixes` C15, C10 · 2 `Fix` JSON C14, C16 | - |

- The three routes' error statuses are unchanged by this spec. Their existing proofs (`test_dismiss_resolved_or_dismissed`, `test_bad_state`, `test_alert_not_found`, `test_access`, `test_every_v1_route_requires_token`) run in C17's `pytest`. C14 crosses the boundary for the new `fixes` shape. C1–C8 prove the rules at their own layer, pure. C9 is the only proof that runs the whole path, from a sync and a `PUT` to the API.

## Swept

- validation: n/a - no new input; the fixes are derived from stored data
- failure modes: existing - AD-047: a raising handler is logged `event.handler_failed` and the check's one transaction rolls back, so fixes and items never disagree (C10 reads both after one commit)
- idempotency: C11
- authorization: existing - `test_alert_not_found`, `test_access` (the routes are unchanged); the credit line is read for the event's business only (C3 fixtures are per business)
- concurrency: existing - `test_concurrent_checks_one_alert`: the fixes are written under the same alerts lock as the alert
- data lifecycle: C13 (a resolved alert keeps its fixes); C15 (fixes are deleted with their alert)
- dependency failure: n/a - no external service; the forecast and the accounts are read in-process through `forecasting.service` and `bank_sync.service`
- state transitions: C12 (`draw_credit` → `financing`), C13
- observability: n/a - no logging requirement in the spec; no event carries a fix (`test_money_and_payloads`)

## Handoff

- S1–S3 ≈ 55k: `alerts/gaps.py` (~6 KB) gains the rules, `alerts/service.py` (~11 KB), `models.py` (~3 KB), `repository.py` (~3 KB), `api.py` (~4 KB), one migration, a new pure test file and additions to 4 test files (~25 KB written), `bank_sync/service.py` read in part, contract regeneration. Under the 150k budget - one builder
