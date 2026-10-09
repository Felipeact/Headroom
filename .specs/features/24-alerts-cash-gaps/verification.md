# 24 - Cash gap alerts verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 0483643..5e20aecddda32e1b16ced6f6cc33151c88c40374
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

All proofs were run at `5e20aec`. Batched proof run (from `services/core`): `uv run pytest tests/test_alert_gaps.py tests/test_alert_check.py tests/test_alerts_api.py tests/test_alerts_sample.py tests/test_migrations.py tests/test_auth.py -v -k "<all 31 named tests or-ed>"`. Result: 40 passed, 49 deselected. Every named test appears in the output individually as PASSED; the parametrized ones appear once per case.

## Binding sources

Step 1 runs only under the `ui` profile. This feature is `light` and has no screen. I still compared the one design fact the checks rely on.

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| `design/mockups/alert.dc.html` (sample alert) | yes - read from the tree: "$5,000 minimum", "$3,150", "Week of Nov 9", "$1,850", Coastal Supply Co, Payroll, "Birch & Co, invoice 1057", and Coastal's "$14,500" in the fix text | none - C7 asserts minimum 500000, low 315000, shortfall 185000, causes -1450000 Coastal and -1120000 Payroll, and arrives_after +960000 Birch & Co | - |
| `context/specs/24-alerts-cash-gaps.md` (Build, Done when) | yes | none - Done when 1 maps to C7, Done when 2 to C9 and C12, and Done when 3 to C16. Done when 4 was ticked by 23a, as D1 decided | - |
| `.specs/features/24-alerts-cash-gaps/context.md` D1, D2 | yes | none - D2 (a dismissed alert that grows reopens) is C19 | - |

## Checks

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | maximal runs strictly below the minimum | `test_finds_gaps[below0..4]`, `test_finds_gaps_at_the_minimum` PASSED | `tests/test_alert_gaps.py:50` - `[(g.starts_on, g.ends_on) for g in found] == [...]` over 5 cases; `:57` - `find_gaps(weeks({7}, value=MINIMUM), MINIMUM) == []` | PASS |
| C2 | gap fields; the earliest week wins a tie | `test_gap_fields` PASSED | `tests/test_alert_gaps.py:69` - `gap == gaps.Gap(starts_on=2026-11-02, ends_on=2026-11-15, lowest_balance_cents=200000, lowest_week_starts_on=2026-11-09, shortfall_cents=300000)`; `:78` - `gap.lowest_week_starts_on == date(2026, 11, 2)` | PASS |
| C3 | 20% causes, window edges, estimates excluded but counted, ordering | `test_causes` PASSED | `tests/test_alert_gaps.py:107` - `causes(items) == [(date(2026,11,12), -200000)]`; `:109` - `== []` at -199999; `:115` - same-date ordering by amount, and 2026-11-02 included | PASS |
| C4 | largest non-estimate incoming item in the 7 days after; the earlier wins a tie | `test_arrives_after` PASSED | `tests/test_alert_gaps.py:132` - 2026-11-22 counted, 2026-11-23 not; `:135-142` - the larger estimate is ignored and the result is `[(2026-11-17, 960000)]`; `:143` - the earlier date wins; `:146` - `== []` | PASS |
| C5 | item fields carried unchanged | `test_item_fields` PASSED | `tests/test_alert_gaps.py:168` - `found == [gaps.Explanation(kind="cause", ..., schedule="biweekly"), gaps.Explanation(kind="arrives_after", ...)]` | PASS |
| C6 | 1 open alert, 1 `alert.created` with `{"alert_id"}`, the row visible inside the subscriber | `test_new_gap_creates_one_alert` PASSED | `tests/test_alert_check.py:217` - `alert.state == "open"`; `:218` - `payloads(sent) == [("alert.created", {"alert_id": str(alert.id)})]`; `:219` - `seen_rows == [1]` | PASS |
| C7 | the sample with a 500000 minimum gives exactly 1 alert with the mockup's numbers and 3 items | `test_sample_gap_alert` PASSED | `tests/test_alerts_sample.py:305` - `(alert,) = ...`; `:307-310` - dates, 315000, 500000, 185000; `:311-318` - items `== [("cause","2026-11-12",-1450000,"Coastal Supply Co, quarterly order"), ("cause","2026-11-13",-1120000,"Payroll"), ("arrives_after","2026-11-17",960000,"Birch & Co, invoice 1057")]` | PASS |
| C8 | no alert and no event without a forecast or without a minimum | `test_nothing_without_forecast_or_minimum` PASSED | `tests/test_alert_check.py:232` - `alerts_of(business_id) == []`; `:233` - `sent == []` | PASS |
| C9 | a second check changes no column (`updated_at` included) or item and publishes nothing | `test_same_forecast_twice` PASSED | `tests/test_alert_check.py:247` - `(columns(second), items_of(second.id)) == before`; `:248` - `sent == []`. Gap 1: see below | PASS |
| C10 | an overlapping gap keeps the same alert ID | `test_overlapping_gap_is_the_same_alert` PASSED | `tests/test_alert_check.py:261` - `moved.id == alert.id`; `:262` - `starts_on == date(2026,11,2)`; `:266-267` - `grown.id == alert.id`, span 11-02..11-22 | PASS |
| C11 | growth of more than $1,000 or more than 20% publishes `alert.updated` and sets the notified shortfall | `test_growth_announced[185000-285001]`, `[100000-120001]` PASSED | `tests/test_alert_check.py:281` - `payloads(sent) == [("alert.updated", {...})]`; `:283` - `(shortfall, notified) == (after, after)` | PASS |
| C12 | exactly $1,000, exactly 20%, or a shrink: silent, notified shortfall unchanged | `test_small_change_silent[3 cases]` PASSED | `tests/test_alert_check.py:298` - `sent == []`; `:300` - `(shortfall, notified) == (after, before)` | PASS |
| C13 | a minimum PUT re-checks without a new snapshot | `test_minimum_change_rechecks` PASSED | `tests/test_alert_check.py:315-316` - `(alert,) = ...; alert.state == "open"`; `:317` - `latest(business_id).id == snapshot.id` | PASS |
| C14 | only `source` `minimum_balance` triggers a check | `test_other_sources_ignored` PASSED | `tests/test_alert_check.py:335` - `== []` for `expected_payments`; `:337` - `len(...) == 1` for `minimum_balance` | PASS |
| C15 | 2 concurrent checks give 1 alert and 1 event | `test_concurrent_checks_one_alert` PASSED | `tests/test_alert_check.py:359` - `len(alerts_of(business_id)) == 1`; `:360` - `[e.name for e in sent] == ["alert.created"]`. Gap 4: see below | PASS |
| C16 | an open alert, or a dismissed one, resolves with 1 `alert.resolved` | `test_gap_gone_resolves[False]`, `[True]` PASSED | `tests/test_alert_check.py:377` - `gone.state == "resolved"`; `:378` - `resolved_at == NOW`; `:379` - `payloads(sent) == [("alert.resolved", {"alert_id": ...})]` | PASS |
| C17 | a resolved alert is never reused | `test_resolved_never_reused` PASSED | `tests/test_alert_check.py:393` - `len(both) == 2`; `:396-398` - `first.state == "resolved"`, `second.state == "open"`, new ID; `:399` - `alert.created` for the second | PASS |
| C18 | dismissing an open alert returns 200, sets `dismissed_at` and the notified shortfall, publishes nothing | `test_dismiss_open` PASSED | `tests/test_alerts_api.py:130` - `status_code == 200`; `:132-133` - `state == "dismissed"`, `dismissed_at is not None`; `:135` - `notified_shortfall_cents == shortfall_cents == 185000`; `:136` - `sent == []` | PASS |
| C19 | a dismissed alert that grows reopens and publishes `alert.updated` | `test_dismissed_grows_reopens` PASSED | `tests/test_alert_check.py:412` - `(state, dismissed_at) == ("open", None)`; `:413` - `alert.updated` payload | PASS |
| C20 | a small change keeps a dismissed alert dismissed, silently | `test_dismissed_small_change_stays` PASSED | `tests/test_alert_check.py:426` - `(state, shortfall) == ("dismissed", 200000)`; `:427` - `sent == []` | PASS |
| C21 | dismissing a resolved alert is 409 with the detail; dismissing a dismissed alert is 200 with the same `dismissed_at` | `test_dismiss_resolved_or_dismissed` PASSED | `tests/test_alerts_api.py:144-145` - `is_problem(response, 409)`, `detail == "This alert is already resolved."`; `:150-152` - 200, same `dismissed_at`, `updated_at` unchanged. Gap 1: see below | PASS |
| C22 | list keys, state filter, order, causes before `arrives_after` | `test_list` PASSED | `tests/test_alerts_api.py:159` - `set(body) == {"items"}`; `:160`, `:163` - one ID per state; `:164`, `:179`, `:181` - exact key sets; `:177` - `["2026-10-12", "2026-11-23"]`; `:180` - `["cause", "cause", "arrives_after"]` | PASS |
| C23 | `GET` one alert in each state | `test_get_one` PASSED | `tests/test_alerts_api.py:194` - `(body["id"], body["state"]) == (alert_id, state)` for open, dismissed and resolved | PASS |
| C24 | `state=closed` returns 422 problem details | `test_bad_state` PASSED | `tests/test_alerts_api.py:204` - `is_problem(response, 422)` | PASS |
| C25 | an unknown or foreign alert is 404 "Alert not found." on GET and on dismiss | `test_alert_not_found` PASSED | `tests/test_alerts_api.py:217-218` - `is_problem(response, 404)`, `detail == "Alert not found."` for both IDs and both routes; `:220` - the foreign alert stays `open` | PASS |
| C26 (amended) | a non-member gets 404 "Business not found." on all 3 routes; a non-owner role gets 403 on dismiss | `test_access` PASSED | `tests/test_alerts_api.py:233-234` - 404 and `"Business not found."` on 3 routes; `:241` - `is_problem(dismiss(...), 403)`; `:244` - `row.state == "open"`. Gap 2: see below | PASS |
| C27 | integer cents with "CAD"; every event payload has exactly the key `alert_id` | `test_money_and_payloads` PASSED | `tests/test_alerts_api.py:256-260` - created, updated, resolved; `:261` - `set(e.payload) == {"alert_id"}`; `:264`, `:267` - `type(...) is int`; `:265`, `:268` - `== "CAD"` | PASS |
| C28 | migration checks, cascade, downgrade, `alembic check` | `test_alerts_upgrade_downgrade_and_check` PASSED | `tests/test_migrations.py:1059` - `constraint in str(raised.value)` for `ck_alerts_state` and `ck_alerts_shortfall_positive`; `:1062` - `"ck_alert_items_kind" in ...`; `:1066` - `left == 0`; `:1074-1075` - both tables gone; `:1082` - `returncode == 0` for `check` | PASS |
| C29 | `SUBSCRIPTIONS[4]` and `[5]` | `test_subscriptions` PASSED | `tests/test_alert_check.py:432-439` - both tuples equal; `:440` - `len == 6` | PASS |
| C30 | contract paths; regeneration leaves no diff | `test_contract_paths` PASSED; `uv run python -m app.export_openapi && (cd ../../frontend && npm run api:types) && git diff --exit-code -- ...` exit 0 | `tests/test_alerts_api.py:275-277` - `"get" in paths[base]`, `"get" in paths[base + "/{alert_id}"]`, `"post" in paths[base + "/{alert_id}/dismiss"]`; the regeneration produced no diff, so nothing needed restoring | PASS |
| C31 | every route answers 401 without a token | `test_every_v1_route_requires_token` PASSED | `tests/test_auth.py:206` - `response.status_code == 401` for every method of every `/v1` path in `app.openapi()`. The test is older than this feature, but it builds its list from the live schema, which now holds the 3 routes (C30) | PASS |
| C32 | all AGENTS.md checks pass | API chain exit 0; web chain exit 0 on an isolated rerun | API: `132 files already formatted`, `All checks passed!`, `mypy: no issues found in 55 source files`, `831 passed, 5 deselected`. Web: lint and typecheck OK, `Tests 287 passed (287)`, build `Compiled successfully`. Gap 3: see below | PASS |

### Swept rows re-read against the code

- **Failure modes (existing, AD-047).** `app/events.py:48-57` catches a raising handler and logs `event.handler_failed` with the event name, handler and error type. `app/modules/alerts/service.py:204-210` rolls back and re-raises, so nothing is committed. The single `session.commit()` is at `:207`, and events are published only after it (`:211-217`). The cited mechanism is present.
- **Dependency failure** and **observability** are `n/a`, which is approved policy. One note: `service.py:212` also logs `name`, `business_id` and `alert_id`. That log carries no amount and no sensitive field.

### Judgment notes requested by the orchestrator

- **Module boundary.** It holds. `app/modules/alerts/*` imports from other modules only `app.modules.forecasting.service`, `app.modules.forecasting.events` (in `service.py`) and `app.modules.accounts.service.Role` (in `api.py`), all of them allowed surfaces. `repository.py` queries only `Alert` and `AlertItem`. The forecast and the minimum are read only through `forecasting_service.latest_forecast` and the new `forecasting_service.minimum_balance_amount`, which reads forecasting's own repository.
- **AC 9 idempotency.** It holds in the code. At `service.py:161-168`, a matched alert is written only if `grew`, a stored field differs from the new value, or the stored items (rebuilt as `Explanation`, `source_id` included) differ from the new explanation. Otherwise the loop `continue`s and nothing is written. A second check on the same snapshot and minimum therefore writes no row and sends no event.
- **AC 15 lock.** It holds. `repository.lock_alerts` (`repository.py:8-20`) runs `pg_advisory_xact_lock(hashtextextended('alerts:'||id, 0))` as the first statement of a fresh session's transaction (`service.py:203-206`), before any alert is read. The engine sets no isolation level, so Postgres uses READ COMMITTED, and the second check therefore sees the first one's committed rows. Dismiss takes the same lock (`service.py:282`).
- **C26 amendment.** It is honest. `accounts.service.Role` has a single member, `OWNER` (`app/modules/accounts/service.py:20-21`). That makes `require_member(*Role)` the same as owner-only, so "a non-owner member's GETs succeed" can't be expressed in v1. AD-088 records the same limitation for the minimum balance GET. The amendment is marked in both `checks.md` C26 and plan AC 26, as **pending the user's confirmation**. It is the user's call, and I flag it here rather than settle it.

## Gate

- Batched proofs: 40 passed, 0 failed (31 named tests, every case shown individually).
- C30 regeneration: `git diff --exit-code` exit 0, no diff.
- API: `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest` exit 0, with 831 passed, 0 failed, 5 deselected.
- Web: `npm run lint && npm run typecheck && npm test && npm run build` exit 0, with 287 tests passed, 0 failed, and the build compiled. The first web run happened while the API suite was running alongside it. In that run, `tests/expected-payment-dialog.test.tsx > C40 add dialog` hit the 5000 ms timeout. That test is outside this feature's diff, and it passed on the isolated rerun.
- The working tree's `git status --porcelain` matched the baseline after all runs.

### Ranked gaps (none fails a check under `light`; reported for the user)

1. **C9 and C21 can't tell a write from no write.** The "unchanged `updated_at`" and "same `dismissed_at`" assertions run under a frozen clock: `alerts_service.clock` and the API's `get_now` both return `NOW`. An implementation that rewrote the row on every check, or re-dismissed an already-dismissed alert, would write the same timestamp and still pass. Under `light` no fault was injected. The properties do hold in the code, by reading `service.py:161-168` and `:286-292`. A clock that advances between the two calls would make both proofs able to catch a regression. Locations: `tests/test_alert_check.py:247`, `tests/test_alerts_api.py:151-152`.
2. **C26 is amended, pending the user's confirmation.** The 403 is proven only by patching `get_membership` to a role, `viewer`, that doesn't exist in v1 (`tests/test_alerts_api.py:236-241`). The behaviour is right, but it is unreachable until spec 31 adds `bookkeeper`.
3. **The web suite has a timing flake.** `expected-payment-dialog.test.tsx` C40 timed out at 5 s under CPU contention. It is not part of this feature.
4. **C15 is a race test.** Two threads behind a barrier may not actually interleave on every run. The lock's correctness was confirmed by reading the code: the lock is taken before any read.
