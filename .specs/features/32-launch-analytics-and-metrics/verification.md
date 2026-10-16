# Spec 32: Analytics and the weekly metrics report verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 856e7eb..HEAD (45c34c3)
**Round**: 2 - scoped (round 1 kept below; C33 and C34 superseded by Round 2)
**Verifier**: independent sub-agent (author != verifier)

Why FAIL: C1-C32 pass; C33 and C34 are GATED and unproven, and the gate does not accept a PASS over a non-PASS row.

C1-C32 are proven with located evidence. C33 and C34 are GATED (not run, not PASS): they need the user's go-ahead and credentials (`railway config apply/plan`, a live PostHog walk-through). The FAIL is only the two gated rows; there is no product defect behind it. The code-level verdict for C1-C32 is PASS; AC 23 and AC 24 stay open until the user runs the two gated checks.

## Checks

Web proofs ran from `frontend` as one `npx vitest run` over the five files (41 passed, each named test listed individually). API proofs ran from `services/core` as one `pytest` over the five files (25 passed). Every named test also exists in the tree (line hits below).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `captureImmediate` once with Clerk user id, event, exact properties; client built with key and host | vitest `analytics.test.ts` "captures with the Clerk user id and never identifies" passed | `tests/analytics.test.ts:44-52` - `toHaveBeenCalledWith('phc_test', objectContaining({ host: 'https://eu.i.posthog.test' }))`, `toHaveBeenCalledWith({ distinctId: 'user_clerk_1', event: 'business_created', properties: { business_id: 'b1' } })`, `identify` not called | PASS |
| C2 | per-event key table; extra keys send nothing and Sentry holds no value | "event keys are fixed", "rejects a property outside the allowlist" passed | `analytics.test.ts:57` - `expect(EVENT_KEYS).toEqual({...8 events...})`; `:78-80` - `captureImmediate` not called, `captureMessage` called 5 times, JSON of calls `not.toContain('secret-value')` | PASS |
| C3 | no key: resolves, no client, no call | "no key means no call" passed | `analytics.test.ts:89-91` - `resolves.toBeUndefined()`, `PostHog` and `captureImmediate` `not.toHaveBeenCalled()` | PASS |
| C4 | rejecting capture resolves; Sentry gets the error without the properties | "a failed capture is reported not thrown" passed | `analytics.test.ts:98-99` - `captureException` `toHaveBeenCalledWith(boom)`; serialized args `not.toContain('a1')` | PASS (see precision gap P1) |
| C5 | never-settling capture resolves at 2000 ms, not before | "gives up after 2 seconds" passed | `analytics.test.ts:112-115` - after 1999 ms `done` is `false`; after +1 ms `done` is `true` | PASS |
| C6 | `/welcome` 307 to `/`, `?next` same-site only, protect first; sign-up page `forceRedirectUrl` | `welcome-route.test.ts`, 9 tests passed | `welcome-route.test.ts:28-31` - `order` equals `['protect','capture']`, `capture` called with `('sign_up_completed', {})`, status `307`, location `https://app.example.test/`; `:37` location `/invite/abc`; refusals at `:42-43`; `:57` - `signUp.forceRedirectUrl` `toBe(expected)` | PASS (see note N1) |
| C7 | create business 201 sends `business_created` with `business_id` `b1`; 409/422/500 send nothing | "create business" 4 tests passed | `analytics-events.test.ts:54` - `capturing` `toHaveBeenCalledExactlyOnceWith('business_created', { business_id: 'b1' })`, after `rejects.toThrow(NEXT_REDIRECT)` at `:51`; `:60` `not.toHaveBeenCalled()` | PASS |
| C8 | connect bank 201 sends `bank_connected`, both return paths; 409/500 nothing | "connect bank" 4 tests passed | `analytics-events.test.ts:68` - `toHaveBeenCalledExactlyOnceWith('bank_connected', { business_id: 'b1' })` after redirect throw at `:67`; `:74` `not.toHaveBeenCalled()` | PASS |
| C9 | save minimum 200 sends `minimum_balance_set`; 422/500 nothing | "save minimum balance" 3 tests passed | `analytics-events.test.ts:82` - `toHaveBeenCalledExactlyOnceWith('minimum_balance_set', { business_id: 'b1' })`; `:88` `not.toHaveBeenCalled()` | PASS |
| C10 | dismiss 200 sends `alert_dismissed` with both ids; 409/500 nothing | "dismiss alert" 3 tests passed | `analytics-events.test.ts:96` - `toHaveBeenCalledExactlyOnceWith('alert_dismissed', { business_id: 'b1', alert_id: 'a1' })`; `:102` `not.toHaveBeenCalled()` | PASS |
| C11 | create payment 201 sends `expected_payment_added`; 409/500 nothing; update/delete nothing | "expected payment" 4 tests passed | `analytics-events.test.ts:110` - `toHaveBeenCalledExactlyOnceWith('expected_payment_added', { business_id: 'b1' })`; `:116` and `:124` `not.toHaveBeenCalled()` | PASS |
| C12 | dashboard sends `business_id` and role (owner, bookkeeper); nothing without a business | "dashboard viewed" 3 tests passed | `analytics-pages.test.tsx:43` - `toHaveBeenCalledExactlyOnceWith('dashboard_viewed', { business_id: 'biz-1', role })` (parametrized over both roles); `:52` `not.toHaveBeenCalled()` | PASS |
| C13 | found alert sends the three keys; unknown sends nothing and calls `notFound()` | "alert opened" 2 tests passed | `analytics-pages.test.tsx:63` - `toHaveBeenCalledExactlyOnceWith('alert_opened', {...})`; `:73-74` - `rejects.toThrow('NEXT_NOT_FOUND')`, `capture` `not.toHaveBeenCalled()` | PASS |
| C14 | rejecting capture still returns `{ ok: true }` | "a failing capture does not change the result" passed | `analytics-events.test.ts:135` - `expect(await createExpectedPayment('b1', BODY)).toEqual({ ok: true })` | PASS |
| C15 | server-only import, no `posthog-js`, no `NEXT_PUBLIC_POSTHOG`, no `identify(` | `analytics-source.test.ts` passed | `analytics-source.test.ts:19-28` - `startsWith('import "server-only"')` `toBe(true)`; manifest keys `not.toContain('posthog-js')`; each file `not.toContain('NEXT_PUBLIC_POSTHOG')` and `not.toMatch(/\.identify\(/)` over app, components, lib and `.env.example` | PASS |
| C16 | URL, Bearer header, HogQL body, 15 s timeout, int from first cell | pytest `test_request_shape` passed | `test_posthog_query.py:36` `== 7`; `:40-42` URL `https://us.posthog.test/api/projects/667024/query/`, `Authorization == f"Bearer {KEY}"`, body `{"query":{"kind":"HogQLQuery",...}}`; `:45` `request.extensions["timeout"] == {"connect": 15, ...}` | PASS |
| C17 | timeout, 401, 429, 500, malformed each raise `PostHogError` with `error_type` only; no key or body in message | pytest `test_failures_raise_posthog_error` passed | `test_posthog_query.py:69-72` - `raised.value.error_type == error_type` over the 5 cases at `:58-62`; `KEY not in message`; `BODY_MARKER not in message` | PASS |
| C18 | weekly-active query text and bounds; figure is the fake's number | pytest `test_weekly_active_query` passed | `test_metrics.py:49` `weekly_active_businesses == 12`; `:51-53` `count(distinct properties.business_id)`, `timestamp >= toDateTime('2026-10-19 00:00:00', 'UTC')`, `timestamp < toDateTime('2026-10-26 00:00:00', 'UTC')`; query selected by containing `dashboard_viewed` at `:50` | PASS |
| C19 | alerts-opened query text and bounds | pytest `test_alerts_opened_query` passed | `test_metrics.py:61` `alerts_opened == 4`; `:63-65` `count(distinct properties.alert_id)` and the same two bounds; selected by `alert_opened` at `:62` | PASS |
| C20 | cohort A-G gives 2 of 5 = 40% | pytest `test_activation_cohort` passed | `test_metrics.py:88` - `(report.signups, report.activated, report.activation_percent) == (5, 2, 40)`; A 23:59, B 24:00, C 24:01, D, E, F, G built at `:71-85` | PASS |
| C21 | no sign-ups: `None`, email says "no sign-ups", never `0%` | pytest `test_activation_without_signups`; email half `test_empty_week_says_so` | `test_metrics.py:95-96` - `(signups, activated) == (0, 0)`, `activation_percent is None`; `test_metrics_email.py:75,77` - `"no sign-ups" in body`, `re.search(r"(?<![0-9])0%", body) is None` | PASS |
| C22 | mean 15.0 over 2 businesses; null, horizon-1 and other-week rows left out | pytest `test_forecast_error_mean` passed | `test_metrics.py:115-116` - `forecast_error_percent == 15.0`, `forecast_error_businesses == 2` | PASS |
| C23 | no record or only null percents: `None`, "no data yet" | pytest `test_forecast_error_none`; email half `test_empty_week_says_so` | `test_metrics.py:121,125-126` - `is None` twice, `forecast_error_businesses == 0`; `test_metrics_email.py:76` `"no data yet" in body` | PASS |
| C24 | PostHog down: activation and error still reported, two figures `None`, `metrics.posthog_failed` with `error_type` only, email says "unavailable" twice | pytest `test_posthog_failure_still_reports`, `test_posthog_failure_says_unavailable_twice` | `test_metrics.py:137-139` - both `None`, `signups == 1`; `:145-148` - `error_type` list `["http_500","http_500"]` and log keys limited to `timestamp, level, logger, event, error_type`; `test_metrics_email.py:87` `text.count("unavailable") == 2` | PASS |
| C25 | sends at Tue 12:00 and 12:59 UTC; nothing and no query at the four other times | pytest `test_only_tuesday_at_noon_utc` passed | `test_weekly_metrics_job.py:46` `== {"metrics_reports": 2}` for both due times; `:49` `sent == 4`; `:57-59` `{"metrics_reports": 0}` for 11:59, 13:00, Mon, Wed; `len(mail.sender.sent) == sent`; `len(fake.queries) == queried` | PASS |
| C26 | report week Oct 19-25 at Oct 27 and Oct 26-Nov 1 at Nov 3; dates in subject and text | pytest `test_report_week_is_the_week_before` (both files) passed | `test_weekly_metrics_job.py:68-71` - subject `"Headroom metrics, Oct 19 to Oct 25"` and `"Oct 26 to Nov 1"`, text holds `Mon, Oct 19`/`Sun, Oct 25` and `Mon, Oct 26`/`Sun, Nov 1`; `test_metrics.py:161` `report_week(NOW) == (WEEK, date(2026, 10, 25))` | PASS |
| C27 | two trimmed recipients get 2 emails; unset or empty sends 0 and logs `metrics.report_skipped` | pytest `test_recipients` passed | `test_weekly_metrics_job.py:82-83` - `{"metrics_reports": 2}`, `[e.to ...] == ["a@example.test","b@example.test"]`; `:90-93` empty and blank: 0 sent, `"metrics.report_skipped" in events`; `:97` unset: `{"metrics_reports": 0}` | PASS (see precision gap P2) |
| C28 | no business name or UUID; four figures, one definition each, week days | pytest `test_aggregates_only` passed | `test_metrics_email.py:50-52` - `"Harbor Street" not in body`, `UUID.search(body) is None`, `str(business_id) not in body` for subject, text and html; `:53-56` the four figure lines; `:63-65` definitions in text and html; dates | PASS |
| C29 | second run in the same hour sends 2 per recipient and changes no row counts | pytest `test_second_run_repeats_without_state` passed | `test_weekly_metrics_job.py:115-116` - `len(mail.sender.sent) == 4`, `counts() == before` (every table in `Base.metadata.sorted_tables`) | PASS |
| C30 | `JOBS` order; `metrics_reports` count; no shared counts key | pytest `test_registered_in_jobs` passed | `test_weekly_metrics_job.py:122-128` - names equal the five jobs in order; `:132` `summary["weekly_metrics"] == {"metrics_reports": 2}`; `:134` `len(keys) == len(set(keys))` | PASS |
| C31 | `app/metrics.py` imports only `service` modules; no table or event | pytest `test_imports_only_services` passed | `test_metrics.py:178,180,182-183` - names equal `["service"]`, `parts[-1] == "service"`, no `Base` subclass, `"subscribe(" not in source` | PASS |
| C32 | settings load without the four; recipients parse to a list of 2; one `get_settings()` | pytest `test_metrics_settings.py`, 4 tests passed | `test_metrics_settings.py:33-36` - the three settings `is None`, recipients `== []`; `:41` `Settings().metrics_report_recipients == [...]`; `:59` `module.get_settings is get_settings` | PASS |
| C33 | `.railway/railway.ts` lists the variables; `railway config plan --detailed-exit-code` exits 0 after `apply` | NOT RUN - gated on the user's go-ahead | Static read only: `.railway/railway.ts:57-60` api `preserve()`, `:79-80` web `POSTHOG_KEY`/`POSTHOG_HOST` `preserve()`, `:114-117` jobs `${{api.NAME}}`. The plan exit code is not proven | GATED in round 1, superseded: PASS by attestation in round 2 |
| C34 | live PostHog walk-through, `posthog_events.py` exits 0 | NOT RUN - gated on credentials and the user's staging walk-through; PostHog was not called | script present at `.specs/features/32-launch-analytics-and-metrics/posthog_events.py`; nothing executed | GATED in round 1, superseded: PASS by attestation in round 2 |

## Coverage

Light profile: sets are not recomputed. The checks' own join was spot-read against the code and the plan.

- All 8 event names have a proof (C6-C13). Property keys are table-driven in C2 (`analytics.test.ts:57`).
- The plan's one route `GET /welcome` has its `307` and four `next` inputs in C6. Every plan Landing door (1-8) and every AC 1-22 maps to a check that ran green. AC 23 maps to C33 and AC 24 to C34, both gated.
- Level gap, already declared in `checks.md`: C18 and C19 prove the HogQL text against a fake. Whether PostHog answers it correctly is only proven by C34 and the first real report.
- Known failures outside this feature, not counted against it (full `services/core` suite: 1060 passed, 28 failed, all in this list): `tests/test_weekly_digest.py` (24, DetachedInstanceError in spec 30's helper), `tests/test_bookkeeper_access.py::test_bookkeeper_can_read` and `tests/test_bookkeeper_alert_emails.py::test_digest_owners_only` (2 bookkeeper tests), `tests/test_health.py::test_unavailable_body_leaks_nothing`, `tests/test_migrations.py::test_businesses_and_memberships_upgrade_downgrade_and_check`.

## Secret scan

`git grep -n "phc_\|phx_"` over tracked files returns only fake test values: `frontend/tests/analytics.test.ts:25,45` (`phc_test`), `frontend/tests/analytics-events.test.ts:130` (`phc_test`), `services/core/tests/test_posthog_query.py:10` (`phx_secret_personal_key`). No real key is tracked. No key or token was printed or used in this run.

## Gaps and notes (none block PASS for C1-C32)

- P1, precision gap, C4: the "no properties in Sentry" assertion checks only that `'a1'` is absent (`analytics.test.ts:99`). It does not check `'b1'`, though the property set `{business_id:'b1', alert_id:'a1'}` is the target. A regression leaking only `business_id` would pass.
- P2, precision gap, C27: the unset-setting case (`test_weekly_metrics_job.py:97`) asserts 0 sent but not the `metrics.report_skipped` log. Only the empty and blank cases assert the log (`:93`).
- N1, check wording, C6: the check says the sign-up page passes `/welcome` when `redirect_url` is not a path. The test and the plan's door 7 expect `/welcome?next=%2F` (`welcome-route.test.ts:57`, cases `undefined` and `//evil.test`). The behavior is safe and matches door 7; the checks text is the stale part.
- N2, C7: "before the redirect" is proven only indirectly (the capture assertion runs after the redirect throw is caught), which holds because the capture must already have happened.
- N3, tests ran as whole files, not `-t` filtered. Each named test still appears individually as passed.
- N4, C33 wording says POSTHOG_KEY/HOST on `web` as `${{api.NAME}}`; the code uses `preserve()` on `web` (correct, since only `web` holds the key). Checks text is imprecise, code is right.
- Not walked: AC 23 (`railway config plan --detailed-exit-code` after `apply`) and AC 24 (all eight events seen live in PostHog). The user must run C33 and C34 before go-live. The `phx_` personal key and the recipients list are still needed (open question 1).

## Gate

`npx vitest run` (5 files) - 41 passed, 0 failed; `uv run pytest` (5 feature files) - 25 passed, 0 failed; full `services/core` suite - 1060 passed, 28 failed (all 28 in the known outside-the-feature list above).

## Round 2 - scoped

Verified at 88ab052. Scope: C33 and C34, the two rows that were not PASS. C1-C32 are carried from round 1 (verified at 45c34c3); no proof was re-run for them. I did not run Railway or call PostHog.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C33 | `.railway/railway.ts` lists the variables; `railway config plan --detailed-exit-code` exits 0 after `apply` | not run (the user's session); static read plus the user's recorded result | `.railway/railway.ts:57-60` api `POSTHOG_APP_HOST`, `POSTHOG_PROJECT_ID`, `POSTHOG_PERSONAL_API_KEY`, `METRICS_REPORT_RECIPIENTS` all `preserve()`; `.railway/railway.ts:79-80` web `POSTHOG_KEY`, `POSTHOG_HOST` `preserve()`; `.railway/railway.ts:114-117` jobs the same four as `"${{api.NAME}}"`. `.specs/STATE.md:141` (Handoff): "C33 done 2026-10-15 (variables set on api and web, `railway config apply --yes`, then `config plan --detailed-exit-code` exit 0 ...)" | PASS (by attestation of the user's session; I did not run railway) |
| C34 | live PostHog walk-through, `posthog_events.py` exits 0 | not run; PostHog not called | `.specs/STATE.md:134` AD-127: the user went through the eight steps on staging against the real PostHog project and confirmed the eight events arrive (user statement 2026-10-15); `posthog_events.py` output was not shown to the agent. The script exists at `.specs/features/32-launch-analytics-and-metrics/posthog_events.py` | PASS (by user attestation) |

Findings carried, not blocking:

1. Both rows are attestations. The `plan` exit code and the claim that all eight events arrive with only `business_id`, `alert_id`, `role` keys were not seen by the Verifier. C34's "exits 0" clause is replaced by the user's confirmation (AD-127).
2. `.specs/STATE.md:141` records that `railway config apply` also created `jobs.RESEND_API_KEY`, a reference to an api variable that does not exist. The jobs process sends the metrics email, so this is worth a look before go-live.
3. Round 1 notes P1, P2 and N1-N4 stand. Open items from STATE: set `METRICS_REPORT_RECIPIENTS`, push `development`.
4. The round 1 Result cells of C33 and C34 were annotated "superseded in round 2" in place; nothing else in round 1 was changed except the Verdict and Round header lines.

## Gate (round 2)

No proofs re-run (the two rows are attestations). The round 1 gate stands: `npx vitest run` (5 files) 41 passed; `uv run pytest` (5 feature files) 25 passed.
