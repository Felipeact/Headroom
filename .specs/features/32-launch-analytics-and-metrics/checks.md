# Spec 32: Analytics and the weekly metrics report checks

Profile: light
Plan: `.specs/features/32-launch-analytics-and-metrics/plan.md`

34 checks in 3 slices · 6 one-way doors · 1 open, which blocks go-live (credentials, now supplied for the project; the recipients are still missing)

Unless noted, `uv run` proofs run from `services/core` and `npx vitest` proofs from `frontend`. API tests that touch the database use the real local Postgres from `tests/conftest.py` (`isolated_database`, as `tests/test_weekly_digest.py` does) and spec 28's `FakeEmailSender` (`tests/email_support.py`). The PostHog query is replaced by a `FakePostHogQuery` (new, `tests/metrics_support.py`) that returns numbers set by the test and records the call; the HTTP client is proven separately with `httpx.MockTransport`. Web tests mock `posthog-node` and `@/lib/api/client` the way `tests/create-business-action.test.ts` does. No unit test calls PostHog, Clerk, Plaid or Resend.

New test files: `tests/analytics.test.ts`, `tests/analytics-events.test.ts`, `tests/analytics-pages.test.tsx`, `tests/welcome-route.test.ts`, `tests/analytics-source.test.ts` (web); `tests/test_posthog_query.py`, `tests/test_metrics.py`, `tests/test_weekly_metrics_job.py`, `tests/test_metrics_email.py`, `tests/test_metrics_settings.py` (API).

## Checks

### S1 - Product events · 17 files · 70 KB · ~20k

**C1** - `capture("business_created", { business_id: "b1" })` with `POSTHOG_KEY` and `POSTHOG_HOST` set calls `captureImmediate` once with `distinctId` equal to the Clerk user ID from `auth()`, `event` `business_created` and `properties` exactly `{ business_id: "b1" }`; the client is built with that key and host (AC 1-8, doors 2, 3)
Proof: `npx vitest run tests/analytics.test.ts -t "captures with the Clerk user id"`

**C2** - Allowlist: a table over the 8 events fixes each one's keys (`business_id` on all but `sign_up_completed`; `alert_id` only on `alert_opened` and `alert_dismissed`; `role` only on `dashboard_viewed` and `alert_opened`), and `capture` called with any other key (`amount_cents`, `description`, `email`, `name`) sends nothing and reports to Sentry without the value (AC 10, door 1)
Proof: `npx vitest run tests/analytics.test.ts -t "event keys are fixed"` and `npx vitest run tests/analytics.test.ts -t "rejects a property outside the allowlist"`

**C3** - With `POSTHOG_KEY` unset, `capture` resolves, builds no client and makes no network call (AC 11)
Proof: `npx vitest run tests/analytics.test.ts -t "no key means no call"`

**C4** - When `captureImmediate` rejects, `capture` still resolves, `Sentry.captureException` receives the error, and no Sentry argument contains the event's properties (AC 12)
Proof: `npx vitest run tests/analytics.test.ts -t "a failed capture is reported not thrown"`

**C5** - When `captureImmediate` never settles, `capture` resolves after 2000 ms on fake timers, not before (AC 12)
Proof: `npx vitest run tests/analytics.test.ts -t "gives up after 2 seconds"`

**C6** - `GET /welcome` signed in sends `sign_up_completed` with no properties and answers `307` to `/`; with `?next=/invite/abc` it answers `307` to `/invite/abc`; `?next=//evil.test`, `?next=https://evil.test` and `?next=` each answer `307` to `/`; it calls `auth.protect()` first. The sign-up page passes `forceRedirectUrl` `/welcome?next=<its own redirect_url>` when that is a path, and `/welcome` otherwise (AC 1, door 2)
Proof: `npx vitest run tests/welcome-route.test.ts`

**C7** - `createBusiness` with `201` (body `{ id: "b1" }`) sends `business_created` with `business_id` `b1` before the redirect to `/onboarding/bank`; `409`, `422` and `500` send nothing (AC 2, 9)
Proof: `npx vitest run tests/analytics-events.test.ts -t "create business"`

**C8** - `connectBank` with `201` sends `bank_connected` with the `businessId` argument before it redirects, for both return paths; `409` and `500` send nothing (AC 3, 9)
Proof: `npx vitest run tests/analytics-events.test.ts -t "connect bank"`

**C9** - `saveMinimumBalance` with `200` sends `minimum_balance_set` with `business_id`; `422` and `500` send nothing (AC 4, 9)
Proof: `npx vitest run tests/analytics-events.test.ts -t "save minimum balance"`

**C10** - `dismissAlert` with `200` sends `alert_dismissed` with `business_id` and `alert_id`; `409` and `500` send nothing (AC 7, 9)
Proof: `npx vitest run tests/analytics-events.test.ts -t "dismiss alert"`

**C11** - `createExpectedPayment` with `201` sends `expected_payment_added` with `business_id`; `409` and `500` send nothing; `updateExpectedPayment` and `deleteExpectedPayment` send nothing (AC 8, 9)
Proof: `npx vitest run tests/analytics-events.test.ts -t "expected payment"`

**C12** - `DashboardContent` for a business with role `bookkeeper` sends `dashboard_viewed` with that `business_id` and `role` `bookkeeper`; with role `owner` it sends `owner`; with no business it sends nothing (AC 5)
Proof: `npx vitest run tests/analytics-pages.test.tsx -t "dashboard viewed"`

**C13** - The alert page for a found alert sends `alert_opened` with `business_id`, `alert_id` and `role`; for `not_found` it sends nothing and still calls `notFound()` (AC 6)
Proof: `npx vitest run tests/analytics-pages.test.tsx -t "alert opened"`

**C14** - A failing capture does not change the result of an action: `createExpectedPayment` with `201` and a rejecting capture still returns `{ ok: true }` (AC 12)
Proof: `npx vitest run tests/analytics-events.test.ts -t "a failing capture does not change the result"`

**C15** - `frontend/lib/analytics.ts` starts with `import "server-only"`; `package.json` has no `posthog-js`; no file under `app`, `components`, `lib` or `.env.example` contains `NEXT_PUBLIC_POSTHOG`; `identify(` appears nowhere under `frontend/app`, `components` or `lib` (AC 13, doors 2, 3)
Proof: `npx vitest run tests/analytics-source.test.ts`

### S2 - The weekly report · 14 files · 80 KB · ~22k

**C16** - The `PostHogHttpQuery` client posts to `{POSTHOG_APP_HOST}/api/projects/667024/query/` (project ID from the setting) with header `Authorization: Bearer <key>`, a JSON body `{"query": {"kind": "HogQLQuery", "query": "<sql>"}}` and a 15-second timeout, and returns the first cell of the first result row as an int (AC 15, 16, door 4)
Proof: `uv run pytest tests/test_posthog_query.py -k "request_shape"`

**C17** - Failure modes of the client: a timeout, `401`, `429`, `500` and a `200` whose body is not the expected JSON each raise `PostHogError` carrying only `error_type`; the message holds neither the key nor the response body (AC 19, door 4)
Proof: `uv run pytest tests/test_posthog_query.py -k "failures_raise_posthog_error"`

**C18** - For the report week Mon 2026-10-19 to Sun 2026-10-25, the weekly-active query sent to the fake holds `dashboard_viewed`, `count(distinct properties.business_id)` and the bounds `2026-10-19 00:00:00` inclusive to `2026-10-26 00:00:00` exclusive in UTC; the figure is the number the fake returns (AC 15)
Proof: `uv run pytest tests/test_metrics.py -k "weekly_active_query"`

**C19** - The alerts-opened query holds `alert_opened`, `count(distinct properties.alert_id)` and the same bounds; the figure is the number the fake returns (AC 16)
Proof: `uv run pytest tests/test_metrics.py -k "alerts_opened_query"`

**C20** - Activation, with sign-ups in the week of: A (owner, connection 23 h 59 min after signing up), B (owner, connection exactly 24 h after), C (owner, connection 24 h 1 min after), D (owner, no connection), E (only a `bookkeeper` membership), F (no membership), and G (owner with a connection in 1 h, but signed up the week before): the figure is 2 of 5 = 40%. E and G are not in the cohort; F is (AC 17)
Proof: `uv run pytest tests/test_metrics.py -k "activation_cohort"`

**C21** - With no sign-ups in the week the activation figure is `None` and the email says "no sign-ups"; it never says `0%` (AC 17)
Proof: `uv run pytest tests/test_metrics.py -k "activation_without_signups"`

**C22** - Forecast error: horizon-4 records for target week 2026-10-19 with percents 10.0, 20.0 and a null (actual 0), plus a horizon-1 record and a horizon-4 record for target week 2026-10-12, give mean 15.0 over 2 businesses (AC 18)
Proof: `uv run pytest tests/test_metrics.py -k "forecast_error_mean"`

**C23** - With no horizon-4 record for the report week the error is `None` and the email says "no data yet"; with only null percents it is also `None` (AC 18)
Proof: `uv run pytest tests/test_metrics.py -k "forecast_error_none"`

**C24** - When the fake PostHog query raises `PostHogError`, `compute` still returns activation and error, marks weekly active and alerts opened `None`, logs `metrics.posthog_failed` with `error_type` only, and the sent email says "unavailable" twice (AC 19)
Proof: `uv run pytest tests/test_metrics.py -k "posthog_failure_still_reports"`

**C25** - The job at each of Tue 2026-10-27 12:00, 12:59 UTC sends; at Tue 11:59, Tue 13:00, Mon 12:05, Wed 12:05 UTC it sends nothing and queries nothing (AC 14)
Proof: `uv run pytest tests/test_weekly_metrics_job.py -k "only_tuesday_at_noon_utc"`

**C26** - At Tue 2026-10-27 12:05 UTC the report week is Mon 2026-10-19 to Sun 2026-10-25, and the subject and text hold both dates. At Tue 2026-11-03 12:05 UTC it is 2026-10-26 to 2026-11-01 (AC 14, 21)
Proof: `uv run pytest tests/test_weekly_metrics_job.py -k "report_week_is_the_week_before"`

**C27** - With `METRICS_REPORT_RECIPIENTS` `" a@example.test, b@example.test "` the fake sender holds 2 emails, to `a@example.test` and `b@example.test`; with the setting unset or empty it holds 0 and the log holds `metrics.report_skipped` (AC 14, 20)
Proof: `uv run pytest tests/test_weekly_metrics_job.py -k "recipients"`

**C28** - A report built over a database that holds a business named "Harbor Street Plumbing" and its IDs contains neither the name nor any UUID in subject, text or HTML; it holds the four figures, one definition line each, and the week's first and last day (AC 21)
Proof: `uv run pytest tests/test_metrics_email.py -k "aggregates_only"`

**C29** - Running the job twice in the same hour sends 2 emails per recipient and leaves every table's row count unchanged (AC 22)
Proof: `uv run pytest tests/test_weekly_metrics_job.py -k "second_run_repeats_without_state"`

**C30** - `JOBS` is `(nightly_bank_sync, forecast_accuracy, weekly_metrics, weekly_digest, email_retries)`, and `run_due` at the due time logs `jobs.run_finished` with `metrics_reports` equal to the number of emails sent and no key that another job also returns (door 5)
Proof: `uv run pytest tests/test_weekly_metrics_job.py -k "registered_in_jobs"`

**C31** - Every import in `app/metrics.py` of `app.modules.*` names a `service` module, and the file defines no table or event (door 6)
Proof: `uv run pytest tests/test_metrics.py -k "imports_only_services"`

**C32** - Settings load with none of `POSTHOG_APP_HOST`, `POSTHOG_PROJECT_ID`, `POSTHOG_PERSONAL_API_KEY`, `METRICS_REPORT_RECIPIENTS` set; `METRICS_REPORT_RECIPIENTS=a@x.test,b@x.test` parses to a list of 2; the job and the API read them through the one `get_settings()` (config)
Proof: `uv run pytest tests/test_metrics_settings.py`

### S3 - Staging wiring · 3 files · 10 KB · ~3k

**C33** - `.railway/railway.ts` lists `POSTHOG_KEY` and `POSTHOG_HOST` on `web` and the four API settings on `jobs` as `${{api.NAME}}` references (and `preserve()` on `api`), and `railway config plan --detailed-exit-code` exits 0 after `railway config apply`. Gated: `apply` and `railway variable set` change the live staging environment and need the user's go-ahead (AC 23)
Proof: `env _=<railway.exe> <railway.exe> config plan --detailed-exit-code` (AD-007)

**C34** - After going through the eight steps in the app against the real PostHog project, `uv run python ../../.specs/features/32-launch-analytics-and-metrics/posthog_events.py` queries PostHog and exits 0 only if all eight event names appear in the last 24 hours and every property key seen is in `business_id`, `alert_id`, `role`. Gated: the walk-through is the user's, on staging, which needs the branch pushed and deployed (AC 24)
Proof: `uv run python ../../.specs/features/32-launch-analytics-and-metrics/posthog_events.py`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| product events (8) | `sign_up_completed` C6 · `business_created` C7 · `bank_connected` C8 · `minimum_balance_set` C9 · `dashboard_viewed` C12 · `alert_opened` C13 · `alert_dismissed` C10 · `expected_payment_added` C11 | - |
| allowed property keys (3) | `business_id` C2 · `alert_id` C2 · `role` C2, table-driven over the 8 events | - |
| steps that must send nothing on an API error (5 actions) | create business C7 · connect bank C8 · save minimum C9 · dismiss C10 · create payment C11 | - |
| report figures (4) | weekly active C18 · alerts opened C19 · activation C20 · forecast error C22 | - |
| report figure edge cases (4) | no sign-ups C21 · no error data C23 · PostHog down C24 · cohort exclusions (bookkeeper, other week) C20 | - |
| job due times (6) | Tue 12:00 C25 · Tue 12:59 C25 · Tue 11:59 C25 · Tue 13:00 C25 · Mon 12:05 C25 · Wed 12:05 C25 | - |
| PostHog client failures (5) | timeout C17 · `401` C17 · `429` C17 · `500` C17 · malformed body C17 | - |
| `GET /welcome` statuses (1) | `307` C6, with four `next` inputs | - |
| recipients (3 states) | two addresses C27 · unset C27 · empty C27 | - |
| one-way doors (6) | 1 names and properties C2, C6-C13 · 2 identity C1, C15 · 3 delivery C3, C15 · 4 PostHog read C16, C17 · 5 schedule and delivery C25, C26, C30 · 6 composition C31 | - |
| startup config: PostHog settings (2 assemblies) | `api` app and `jobs` process share `get_settings()` C32 · `web` reads `POSTHOG_KEY` per call C3 | - |

- Claims naming a status code or a route: C6 (`307`), C16 (URL and header) - each proof crosses the boundary (the route handler is called; the HTTP client runs over `httpx.MockTransport`)
- Level gap: C18 and C19 prove the HogQL text and the figure plumbing against a fake. Whether PostHog answers that text correctly is proven only by C34 on the real project, and the first real report
- No other check claims more than the single case its proof exercises

## Swept

- validation: C2 (event keys), C6 (`next` path), C27 (recipient parsing), C32 (settings)
- failure modes: C4, C5, C14 (capture), C24 (PostHog down), C17 (client errors)
- idempotency: C29 (a repeated run repeats the email and changes no state; AC 22 accepts it)
- authorization: C6 (`auth.protect()` on `/welcome`), C1 (the key is server-only, C15); the report has no HTTP route
- concurrency: n/a - events are independent writes to PostHog, and the report job changes no stored state, so two overlapping runs only send twice (C29)
- data lifecycle: n/a - no table or retained data is added; PostHog holds the events, and the report is aggregates only (C28)
- dependency failure: C3, C4, C5 (PostHog from the web), C17, C24 (PostHog from the job)
- state transitions: n/a - no entity with states is added
- observability: C24 (`metrics.posthog_failed`), C27 (`metrics.report_skipped`), C30 (`jobs.run_finished` count)

## Handoff

- S1 = ~20k in `frontend` (17 files, 70 KB), S2 = ~22k in `services/core` (14 files, 80 KB), S3 = ~3k; total ~45k, under the 150k budget - one builder
- Mechanism: one builder
