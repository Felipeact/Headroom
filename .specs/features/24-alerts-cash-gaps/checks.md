# 24 - Cash gap alerts checks

Profile: light
Plan: `.specs/features/24-alerts-cash-gaps/plan.md`

32 checks in 5 slices · 5 one-way doors · 0 open

All API proofs run from `services/core`. Test files: `tests/test_alert_gaps.py` (pure: gaps and explanations), `tests/test_alert_check.py` (the handler, on hand-built forecasts), `tests/test_alerts_api.py` (routes), `tests/test_alerts_sample.py` (the sample end to end), `tests/test_migrations.py` (tables).

## Checks

### S1 - A gap in the forecast becomes one alert that names its payments · ~25k

**C1** - Gap finding, table-driven over week ends against a minimum of 500000: none below → 0 gaps; one week at 499999 → 1 gap; a week at exactly 500000 is not below; weeks 3–5 below → 1 gap of 3 weeks; weeks 2 and 5 below with 3–4 above → 2 gaps; all 13 below → 1 gap (AC 1)
Proof: `uv run pytest tests/test_alert_gaps.py -k test_finds_gaps`

**C2** - A gap of weeks starting 2026-11-02 and 2026-11-09, ending at 300000 and 200000 against 500000, has `starts_on` 2026-11-02, `ends_on` 2026-11-15, `lowest_balance_cents` 200000, `lowest_week_starts_on` 2026-11-09, `shortfall_cents` 300000. With two weeks tied at the lowest, `lowest_week_starts_on` is the earlier one (AC 2)
Proof: `uv run pytest tests/test_alert_gaps.py -k test_gap_fields`

**C3** - For a gap 2026-11-09..2026-11-15, the window is 2026-11-02..2026-11-15. With window money out of 1000000 (estimates included), an outgoing item of -200000 is a cause and one of -199999 isn't. An `estimate` of -500000 isn't a cause but counts in the 1000000. An item on 2026-11-01 isn't a cause, one on 2026-11-02 is, and incoming items never are. Causes are ordered by date, then amount (AC 4)
Proof: `uv run pytest tests/test_alert_gaps.py -k test_causes`

**C4** - For a gap ending 2026-11-15, `arrives_after` is the single largest non-estimate incoming item dated 2026-11-16..2026-11-22: an item on 2026-11-22 counts and one on 2026-11-23 doesn't. A larger `estimate` is ignored. On equal amounts the earlier date wins. With no such item there is none (AC 5)
Proof: `uv run pytest tests/test_alert_gaps.py -k test_arrives_after`

**C5** - Each explanation item carries the forecast item's `date`, `amount_cents`, `currency`, `description`, `counterparty`, `source` and `schedule` unchanged (AC 6)
Proof: `uv run pytest tests/test_alert_gaps.py -k test_item_fields`

**C6** - A check on a forecast with one gap and a minimum stores exactly 1 alert in `state` `open`, and publishes exactly 1 `alert.created` whose payload is exactly `{"alert_id": "<that id>"}`. A new session opened inside the event's subscriber already sees the row (AC 3)
Proof: `uv run pytest tests/test_alert_check.py -k test_new_gap_creates_one_alert`

**C7** - Sample (seed 0, clock 2026-09-26) loaded, then `PUT` minimum 500000: `GET .../alerts` returns exactly 1 alert, `open`, `starts_on` 2026-11-09, `ends_on` 2026-11-15, `lowest_balance_cents` 315000, `minimum_cents` 500000, `shortfall_cents` 185000. Its items are exactly [cause 2026-11-12 -1450000 "Coastal Supply Co, quarterly order", cause 2026-11-13 -1120000 "Payroll", arrives_after 2026-11-17 +960000 "Birch & Co, invoice 1057"] (AC 7, Done when 1)
Proof: `uv run pytest tests/test_alerts_sample.py -k test_sample_gap_alert`

**C8** - With a forecast but no minimum, or a minimum but no forecast, a check stores no alert and publishes no event (AC 8)
Proof: `uv run pytest tests/test_alert_check.py -k test_nothing_without_forecast_or_minimum`

### S2 - Re-checking never duplicates, and small changes stay quiet · ~20k

**C9** - Running the check a second time on the same forecast and minimum leaves the alert count at 1, leaves every alert column (`updated_at` included) and every item unchanged, and publishes 0 events (AC 9, Done when 2)
Proof: `uv run pytest tests/test_alert_check.py -k test_same_forecast_twice`

**C10** - When the gap moves from the week of 2026-11-09 to weeks 2026-11-02..2026-11-09, the same alert ID is updated (`starts_on` 2026-11-02) and the count stays 1. The same holds for a gap that grows from 1 week to 3 (AC 10)
Proof: `uv run pytest tests/test_alert_check.py -k test_overlapping_gap_is_the_same_alert`

**C11** - Table-driven over a notified shortfall: 185000 → 285001 (by more than $1,000) publishes 1 `alert.updated` and sets `notified_shortfall_cents` 285001. 100000 → 120001 (by more than 20%) publishes 1 `alert.updated` (AC 11)
Proof: `uv run pytest tests/test_alert_check.py -k test_growth_announced`

**C12** - Table-driven: 600000 → 700000 (exactly $1,000, under 20%), 400000 → 480000 (exactly 20%, under $1,000), and 185000 → 100000 (a shrink) each update `shortfall_cents` and publish 0 events, with `notified_shortfall_cents` unchanged (AC 12, Done when 2)
Proof: `uv run pytest tests/test_alert_check.py -k test_small_change_silent`

**C13** - On a synced business with a stored forecast, the owner's `PUT .../minimum-balance` to above every week end creates exactly 1 `open` alert. The forecast snapshot is unchanged (the same `id` as before the PUT) (AC 13)
Proof: `uv run pytest tests/test_alert_check.py -k test_minimum_change_rechecks`

**C14** - With a minimum written directly (no event), publishing `forecast_inputs.changed` with `source` `expected_payments` creates no alert. Publishing it with `source` `minimum_balance` creates 1 (AC 14)
Proof: `uv run pytest tests/test_alert_check.py -k test_other_sources_ignored`

**C15** - Two checks of the same business started at once on 2 threads leave exactly 1 alert and publish exactly 1 `alert.created` (AC 15)
Proof: `uv run pytest tests/test_alert_check.py -k test_concurrent_checks_one_alert`

### S3 - Alerts move between open, dismissed and resolved · ~15k

**C16** - An `open` alert, and separately a `dismissed` one, whose gap leaves the forecast becomes `resolved` with `resolved_at` set, and exactly 1 `alert.resolved` with payload `{"alert_id": ...}` is published for each (AC 16, Done when 3)
Proof: `uv run pytest tests/test_alert_check.py -k test_gap_gone_resolves`

**C17** - After an alert is resolved, a gap in the same weeks creates a second alert with a new ID and publishes `alert.created`. The resolved one stays `resolved` (AC 17)
Proof: `uv run pytest tests/test_alert_check.py -k test_resolved_never_reused`

**C18** - The owner's `POST .../alerts/{id}/dismiss` on an `open` alert returns `200` with `state` `dismissed` and a non-null `dismissed_at`. The row's `notified_shortfall_cents` equals its `shortfall_cents`, and no event is published (AC 18)
Proof: `uv run pytest tests/test_alerts_api.py -k test_dismiss_open`

**C19** - A `dismissed` alert dismissed at shortfall 185000 whose gap grows to 285001 becomes `open` with `dismissed_at` null and publishes 1 `alert.updated` (D2) (AC 19)
Proof: `uv run pytest tests/test_alert_check.py -k test_dismissed_grows_reopens`

**C20** - A `dismissed` alert whose shortfall moves 185000 → 200000 stays `dismissed`, its `shortfall_cents` becomes 200000, and no event is published (AC 20)
Proof: `uv run pytest tests/test_alert_check.py -k test_dismissed_small_change_stays`

**C21** - Dismissing a `resolved` alert returns `409` problem details with detail "This alert is already resolved." and the row is unchanged. Dismissing a `dismissed` alert returns `200` with the same `dismissed_at` as before (AC 21)
Proof: `uv run pytest tests/test_alerts_api.py -k test_dismiss_resolved_or_dismissed`

### S4 - The alerts API · ~20k

**C22** - `GET .../alerts` returns `200` with keys exactly `items`. Each alert's keys are exactly `id`, `state`, `starts_on`, `ends_on`, `lowest_week_starts_on`, `lowest_balance_cents`, `minimum_cents`, `shortfall_cents`, `currency`, `created_at`, `updated_at`, `dismissed_at`, `resolved_at`, `items`, and each item's are exactly `kind`, `date`, `amount_cents`, `currency`, `description`, `counterparty`, `source`, `schedule`. With 1 open, 1 dismissed and 1 resolved alert, no `state` returns only the open one, and `state=dismissed` / `state=resolved` return only theirs. Two open alerts come by `starts_on`, and causes come before `arrives_after` (AC 22)
Proof: `uv run pytest tests/test_alerts_api.py -k test_list`

**C23** - `GET .../alerts/{id}` returns `200` with the `Alert` for each of an open, a dismissed and a resolved alert (AC 23)
Proof: `uv run pytest tests/test_alerts_api.py -k test_get_one`

**C24** - `GET .../alerts?state=closed` returns `422` `application/problem+json` (AC 24)
Proof: `uv run pytest tests/test_alerts_api.py -k test_bad_state`

**C25** - An unknown alert ID, and an alert of another business, return `404` with detail "Alert not found." on both `GET .../alerts/{id}` and dismiss (AC 25)
Proof: `uv run pytest tests/test_alerts_api.py -k test_alert_not_found`

**C26** - A caller who isn't a member gets `404` "Business not found." on all 3 routes. With `get_membership` patched to role `viewer`, dismiss returns `403` and the alert stays `open` (AC 26). *Amended while building, 2026-10-09, pending the user's confirmation: v1 has only the `owner` role (`Role` = `{OWNER}`), so `require_member(*Role)` refuses any non-owner, and "their GETs SHALL succeed" can't hold until spec 31 adds `bookkeeper`, as AD-088 already records for the minimum balance GET.*
Proof: `uv run pytest tests/test_alerts_api.py -k test_access`

**C27** - Every amount in the `Alert` JSON is an `int` next to a `currency` of "CAD", and each of `alert.created`, `alert.updated` and `alert.resolved` carries a payload whose keys are exactly `{"alert_id"}` (AC 27)
Proof: `uv run pytest tests/test_alerts_api.py -k test_money_and_payloads`

### S5 - Doors and the contract · ~15k

**C28** - The migration creates `alerts` and `alert_items`: inserting `state` "closed" fails on `ck_alerts_state`, `shortfall_cents` 0 fails on `ck_alerts_shortfall_positive`, item `kind` "other" fails on `ck_alert_items_kind`, and deleting an alert deletes its items; downgrade drops both tables, and `alembic check` is clean at head (door 1)
Proof: `uv run pytest tests/test_migrations.py -k test_alerts_upgrade_downgrade_and_check`

**C29** - `SUBSCRIPTIONS[4]` is `("forecast.updated", alerts.service.check_cash_gaps)` and `SUBSCRIPTIONS[5]` is `("forecast_inputs.changed", alerts.service.check_cash_gaps)`, after the existing 4 (door 4)
Proof: `uv run pytest tests/test_alert_check.py -k test_subscriptions`

**C30** - The regenerated contract has `get` on `/v1/businesses/{business_id}/alerts` and `/v1/businesses/{business_id}/alerts/{alert_id}`, and `post` on `.../alerts/{alert_id}/dismiss`. Regenerating `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` leaves no diff (door 5)
Proof: `uv run pytest tests/test_alerts_api.py -k test_contract_paths`
Proof: `uv run python -m app.export_openapi && (cd ../../frontend && npm run api:types) && git diff --exit-code -- ../../contracts/openapi.json ../../frontend/lib/api/schema.d.ts`

**C31** - Every route of this spec answers `401` without a token (the existing walk over every `/v1` route)
Proof: `uv run pytest tests/test_auth.py -k test_every_v1_route_requires_token`

**C32** - Every AGENTS.md check passes: API `ruff format --check`, `ruff check`, `mypy app`, `pytest`; web `lint`, `typecheck`, `test`, `build`
Proof: `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest`
Proof: `cd ../../frontend && npm run lint && npm run typecheck && npm test && npm run build`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET .../alerts` statuses (4) | 200 C22 · 401 C31 · 404 C26 · 422 C24 | - |
| `GET .../alerts/{alert_id}` statuses (3) | 200 C23 · 401 C31 · 404 C25, C26 | - |
| `POST /v1/businesses/{business_id}/alerts/{alert_id}/dismiss` statuses (5) | 200 C18, C21 · 401 C31 · 403 C26 · 404 C25, C26 · 409 C21 | - |
| alert states (3) | `open` C6 · `dismissed` C18 · `resolved` C16 | - |
| transitions (6) | new → open C6 · open → dismissed C18 · dismissed → open C19 · open → resolved C16 · dismissed → resolved C16 · resolved → never reused C17 | - |
| events (3) | `alert.created` C6, C27 · `alert.updated` C11, C19, C27 · `alert.resolved` C16, C27 | - |
| triggers (3) | `forecast.updated` C6 · `forecast_inputs.changed` minimum_balance C13, C14 · other sources C14 | - |
| growth rule edges (5) | >$1,000 C11 · >20% C11 · exactly $1,000 C12 · exactly 20% C12 · shrink C12 | - |
| item kinds (2) | `cause` C3, C7 · `arrives_after` C4, C7 | - |
| cause window edges (4) | day before window C3 · window's first day C3 · 20% exactly C3 · just under 20% C3 | - |
| Landing doors (5) | 1 tables C28 · 2 same gap C10, C15, C17 · 3 events C27 · 4 subscriptions C29 · 5 routes C22–C26, C30 | - |
| `state` query values (4) | `open` (default) C22 · `dismissed` C22 · `resolved` C22 · other C24 | - |

- Claims naming a status code, route or response shape (C18, C21–C26, C30, C31) are proven through `TestClient` with signed tokens. C1–C5 prove the gap and explanation rules at their own layer, pure. C7 and C13 are the only proofs that run the whole path from a sync and a `PUT` to the API.

## Swept

- validation: C24 (the `state` query); dismiss takes no body
- failure modes: existing - AD-047: a raising handler is logged `event.handler_failed` and its transaction rolls back; the check commits once (C6 sees the committed row)
- idempotency: C9 (same forecast twice), C21 (dismissing twice)
- authorization: C26, C25 (another business's alert)
- concurrency: C15
- data lifecycle: C17 (resolved alerts are kept and never reused); C28 (items are deleted with their alert)
- dependency failure: n/a - no external service; the forecast and minimum are read in-process through `forecasting.service`
- state transitions: C6, C16, C17, C18, C19, C20, C21
- observability: n/a - no logging requirement in the spec; events carry only `alert_id` (C27)

## Handoff

- S1–S5 ≈ 95k: new module `alerts` (~6 files, ~25 KB written), migration, 5 test files (~45 KB), `subscriptions.py`, `main.py`, `forecasting/service.py` read in part (~40 KB), contract regeneration. Under the 150k budget - one builder
