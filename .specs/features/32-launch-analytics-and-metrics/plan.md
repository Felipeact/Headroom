# Spec 32: Analytics and the weekly metrics report

## Problem

The pilot is judged on three numbers (`context/Roadmap.md`): 60% of businesses still checking their forecast every week after eight weeks, 50% paying full price, and testimonials. Today nothing records who opens the dashboard or an alert, and the one number the product already stores, forecast error (spec 22), has no reader. The only way to answer "is the pilot working?" is to ask each client in the weekly check-in. The spec gives no figures beyond the targets in `context/project-overview.md`: 70%+ activation (connect a bank within 24 hours of signing up), 60%+ weekly use, forecast error within ±10%.

When this ships, eight product events reach PostHog from the web server, and every Tuesday the team gets one email with four figures for the week before: weekly active businesses, alerts opened, activation, and the 4-week forecast error. Nobody has to run a query.

## Flow

This reuses the `EmailSender` and Jinja templates of spec 28 (AD-110), the hourly `JOBS` runner of spec 15 (AD-056) with the digest's "due in one hour" rule (AD-118), `forecasting.service.accuracy_history` (AD-086), and the server actions that already make every change from the web app.

Events (web server only):

1. A server action or server component finishes a step -> `frontend/lib/analytics.ts` (new, door 1, 2, 3) -> `posthog-node` -> PostHog. The capture happens after the API answered with success; a capture failure never changes the user's result.
2. Sign-up: the sign-up page sends a new user to `GET /welcome?next=<where they were headed>` (new route handler, door 7) -> `sign_up_completed` -> redirect to `next`, or `/`.

Report (jobs service):

3. `run_due` -> `weekly_metrics` job (new, `JOBS` after `forecast_accuracy`, before `weekly_digest`) -> `app.metrics.compute` (new, door 6).
4. `app.metrics` -> `accounts.service.signup_cohort` (new function, exists module) and `bank_sync.service.first_connection_times` (new function, exists module) for activation; `forecasting.service.accuracy_history` (exists) for the error; PostHog Query API (door 4) for weekly active businesses and alerts opened.
5. `notifications.service.send_metrics_report` (new function, exists module, door 5) renders the `metrics_report` template and sends once per recipient through `EmailSender`; it writes no `email_deliveries` row.

## Impact

| Front | What changes |
| --- | --- |
| domain | new term: report week - the Monday to Sunday (UTC) that ended the day before the report is sent |
| domain | new term: weekly active business - a business with at least one `dashboard_viewed` in the report week, from any member |
| domain | new term: activation - a new owner's business has a bank connection created within 24 hours of the user's `users.created_at` |
| domain | existing: `accuracy_history` (AD-086) gets its first reader; it is read across businesses, as AD-086 planned |
| events | `JOBS` gains `weekly_metrics`; its counts key is `metrics_reports` so it does not collide with the other jobs' keys in `jobs.run_finished` |
| web | every action and page named in AC 1-9 gains one capture call; no new screen and no UI text, so `messages/en.json` is unchanged; the report's text lives in the email template (AD-110) |
| config | new optional settings `POSTHOG_APP_HOST`, `POSTHOG_PROJECT_ID`, `POSTHOG_PERSONAL_API_KEY`, `METRICS_REPORT_RECIPIENTS` on the API (door 8); `POSTHOG_KEY`, `POSTHOG_HOST` on `web`; `.railway/railway.ts` lists them with `preserve()` (AD-054 pattern); the sign-up page (`forceRedirectUrl`) points at `/welcome` |
| auth | `/welcome` is behind `auth.protect()` like every other route handler outside `/healthz` (AD-026); the only change to sign-up is the redirect prop |
| docs | the privacy policy of spec 35 must name PostHog and what is sent |
| stored data | nothing to migrate; no table is added |

## Relations

None - no stored-data shape change

## Surface

Only routes this adds or whose signature changes.

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `GET /welcome` (web) | Clerk session | redirect to `/` | `307` |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. Event names and properties | `sign_up_completed`, `business_created`, `bank_connected`, `minimum_balance_set`, `dashboard_viewed`, `alert_opened`, `alert_dismissed`, `expected_payment_added`; property keys only `business_id`, `alert_id`, `role` (`owner` or `bookkeeper`); `alert_id` only on the two alert events; `business_id` on all but `sign_up_completed` | Dotted names such as `alert.opened`: AGENTS.md fixes the in-process bus events as six dotted names, and these are not bus events. Any amount, description or counterparty property: AGENTS.md and the spec forbid it |
| 2. Identity | PostHog `distinctId` = the Clerk user ID from `auth()`; no `identify`, no person properties, no group analytics | `identify` with name or email: PII belongs in Clerk (AD-020), and a PostHog person cannot be edited out of reports later |
| 3. Delivery | dependency `posthog-node` in `frontend/lib/analytics.ts`, which starts with `import "server-only"` (AD-017 pattern); `NEXT_PUBLIC_*` PostHog variables are never defined; with `POSTHOG_KEY` unset every call is a no-op | `posthog-js` in the browser: it adds cookies and a consent decision, is blocked by ad blockers, and puts a third-party script on a page that shows bank balances |
| 4. Report reads PostHog | the API's `app/analytics.py` posts HogQL to `{POSTHOG_HOST}/api/projects/{POSTHOG_PROJECT_ID}/query/` with `Authorization: Bearer {POSTHOG_PERSONAL_API_KEY}` through a `PostHogQuery` Protocol (the AD-036 pattern: tests use a fake, one error type, 15-second timeout) | Writing every event to our own table as well: each event would need an API endpoint the web server calls, doubling every write path. Cost: the report depends on PostHog being up (AC 18 handles that) |
| 5. Schedule and delivery | due when the UTC time is Tuesday in the 12 o'clock hour; recipients are the comma-separated `METRICS_REPORT_RECIPIENTS`; template `metrics_report.subject.txt`, `.html`, `.txt` over `base.*`; a missed or doubled run loses or repeats that week's report | Monday: the 4-week error for the week is recorded on each business's local Tuesday (AD-085), and the first Canadian Tuesday begins at 07:00 UTC. A claim table to stop doubles: a table for an internal email is more than one repeated report costs (AD-118 accepts the same) |
| 6. Cross-module composition | `services/core/app/metrics.py` (app-level, extends AD-102): `compute(session, *, now, query) -> WeeklyMetrics`, imports only `app.modules.<name>.service`, owns no table or event | A sixth module `metrics`: AGENTS.md fixes five. A SQL join over `users`, `memberships` and `bank_connections`: each module owns its tables |
| 7. Sign-up detection (found while building) | `app/sign-up/[[...sign-up]]/page.tsx` renders `<SignUp forceRedirectUrl="/welcome?next=<encoded path and query of Clerk's redirect_url>" />`; `lib/safe-path.ts` keeps only a same-site path | `NEXT_PUBLIC_CLERK_SIGN_UP_FORCE_REDIRECT_URL=/welcome`: a forced redirect overrides `redirect_url`, so an invited bookkeeper who signs up would miss the invitation page |
| 8. Query host (found while building) | API settings name `POSTHOG_APP_HOST` (`https://us.posthog.com`), distinct from the web's ingestion `POSTHOG_HOST` (`https://us.i.posthog.com`) | One `POSTHOG_HOST` for both: the Query API and event ingestion are served from different hosts |

- Nothing else in this change is hard to reverse

## Criteria

### S1: Product events reach PostHog (P1)

Each of the eight events is sent from the web server when its step succeeds.

**Acceptance Criteria**

1. WHEN a new user finishes Clerk sign-up THEN the web app SHALL send `sign_up_completed` from `GET /welcome` and redirect to `/` with `307`.
2. WHEN the create-business action receives `201` THEN the web app SHALL send `business_created` with `business_id`.
3. WHEN a bank connection is created, from onboarding or from settings, and the API answers with success THEN the web app SHALL send `bank_connected` with `business_id`.
4. WHEN the minimum balance is saved, from onboarding step 4 or from settings, and the API answers `200` THEN the web app SHALL send `minimum_balance_set` with `business_id`.
5. WHEN the dashboard renders for a business THEN the web app SHALL send `dashboard_viewed` with `business_id` and the caller's `role`.
6. WHEN `/alerts/{alertId}` renders an alert it found THEN the web app SHALL send `alert_opened` with `business_id`, `alert_id` and `role`. An unknown alert sends nothing.
7. WHEN the dismiss action receives `200` THEN the web app SHALL send `alert_dismissed` with `business_id` and `alert_id`.
8. WHEN an expected payment is created and the API answers `201` THEN the web app SHALL send `expected_payment_added` with `business_id`.
9. IF the API answers with an error for the step THEN the web app SHALL send no event for it.
10. The system SHALL send no property outside `business_id`, `alert_id` and `role`, and SHALL send no amount, description, counterparty, name or email. A test fails if an event is sent with another key.
11. IF `POSTHOG_KEY` is unset THEN the web app SHALL make no network call and no step SHALL fail.
12. IF a capture throws or does not finish within 2 seconds THEN the user's action SHALL still return its normal result, and the error SHALL go to Sentry without the event's properties.
13. The system SHALL load no PostHog script in the browser and define no `NEXT_PUBLIC_` PostHog variable.

**Independent test:** with a fake client, run each server action against a fake API and assert the event names and exact property keys; run once with `POSTHOG_KEY` unset.

### S2: The weekly report (P1)

Every Tuesday the team gets the four figures with no manual step.

**Acceptance Criteria**

14. WHEN the job runs on a Tuesday in the 12 o'clock hour (UTC) and recipients are configured THEN the system SHALL send one email to each recipient for the report week, and SHALL send nothing in any other hour.
15. The report SHALL show weekly active businesses as the number of distinct `business_id` values on `dashboard_viewed` events in the report week.
16. The report SHALL show alerts opened as the number of distinct `alert_id` values on `alert_opened` events in the report week.
17. The report SHALL show activation as the share of users who signed up in the report week and have a bank connection on a business they own created within 24 hours of signing up, as a whole percent, with the counts it came from. Users whose only membership is `bookkeeper` are not counted. With no sign-ups it SHALL show "no sign-ups" and not 0%.
18. The report SHALL show the 4-week forecast error as the mean `error_percent` of the horizon-4 accuracy records whose target week is the report week, to one decimal, with the number of businesses it covers. With none it SHALL show "no data yet". A record with a null percent is left out.
19. IF the PostHog query fails THEN the system SHALL still send the report with weekly active businesses and alerts opened marked "unavailable", log `metrics.posthog_failed` with the error type only, and show the two figures that come from the database.
20. IF no recipient is configured THEN the system SHALL send nothing and log `metrics.report_skipped`.
21. The report SHALL name the report week's first and last day, define each figure in one line, and contain no business name, business ID or user ID.
22. WHEN `weekly_metrics` runs twice in one hour for the same week THEN the system SHALL send a second email per recipient and change no stored state.

**Independent test:** call the job at Tuesday 12:05 UTC with the fake PostHog query and the sample data of spec 18; read the one email on the fake sender.

### S3: Staging wiring (P2)

**Acceptance Criteria**

23. The system SHALL list the new variables in `.railway/railway.ts` with `preserve()` or a `${{api.NAME}}` reference, and `railway config plan --detailed-exit-code` SHALL exit 0 after `railway config apply`.
24. WHEN a user goes through each of the eight steps on staging THEN each event name SHALL appear in PostHog's live events with only the allowed property keys.

**Independent test:** the staging walk-through in AC 24, then the report job run once by hand.

## Out of scope

| Excluded | Why |
| --- | --- |
| Dashboards, funnels and cohorts inside PostHog | The report is the deliverable; PostHog is the source |
| Paid share, lifetime value, cancellations and testimonials | No billing exists until the pilot (Roadmap) |
| "Share of alerts that lead to an action" | Not in the spec's list; the events it would need are not defined |
| Per-business or per-user breakdowns, a metrics page in the app | The spec asks for one email of aggregates |
| A cookie banner | No cookie is set: events leave the server only |
| Session recording, feature flags, error tracking in PostHog | Sentry covers errors (AD-010) |
| Backfilling events from before this ships | There is no history to read |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Where the report goes | An email to `METRICS_REPORT_RECIPIENTS` | The spec says "a weekly report" and nothing else; email reuses spec 28 and needs no new screen | n |
| When it is sent | Tuesday 12:00 UTC (door 5) | The previous week's 4-week error is recorded by then in every Canadian time zone | n |
| Weekly active counts bookkeepers | Any member's view counts for the business | The pilot gate asks whether the business checks its forecast, and a bookkeeper checking for it is that | n |
| Activation excludes bookkeepers | A user with only a `bookkeeper` membership is not in the cohort | They accept an invite and never connect a bank, which would lower the number for a reason that is not onboarding | n |
| A disconnected bank | Not counted for activation, because disconnecting deletes the connection (AD-064) | The report reads current rows; keeping history is a new table | n |
| How sign-up is detected | The sign-up page's redirect to `/welcome` (door 7) | The API creates the `users` row on a first request, which the web server cannot see | n |
| PostHog region | US cloud, disclosed in the privacy policy | Railway is in US East and the data-location decision already accepts the United States (Roadmap) | n |
| Event identity | Clerk user ID as `distinctId`, no `identify` | Door 2 | n |

**Open questions:**

| # | Kind | Question | Until answered |
| --- | --- | --- | --- |
| 1 | blocks go-live | A PostHog project (project API key, project ID, personal API key with query read) and the recipient addresses for the report | AC 24 and the first real report cannot run on staging; the unit proofs run on fakes |

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| route `GET /welcome` | error shape and codes | AC 1; unauthenticated callers go to sign-in through `auth.protect()` (AD-026) |
| route `GET /welcome` | versioning, rate limits | n/a - a web redirect, not under `/v1`; v1 has no rate limiting |
| events (all eight) | response shape, who may send | AC 1-8 and AC 10; only the web server holds `POSTHOG_KEY` |
| events (all eight) | failure and unavailable PostHog | AC 11, AC 12 |
| scheduled task `weekly_metrics` | output and exit codes | existing - `run_due` logs `jobs.run_finished` with counts and exits 0 (AD-056) |
| scheduled task `weekly_metrics` | what it prints when it fails halfway | AC 19; a raising job is logged `jobs.job_failed` and the rest still run (AD-056) |
| scheduled task `weekly_metrics` | flags and defaults | n/a - no flags; settings in the config row of Impact |
| email `metrics_report` | structure, tone, next action | AC 21: dated, one line per figure, no action to take |
| email `metrics_report` | unsubscribe | n/a - an internal operations email to addresses the team chose, not to customers |
| email `metrics_report` | rendering in mail clients | existing - the `base` template proven in spec 29 |
| screen | empty, loading, error states | n/a - this spec adds no screen |

## Sources

- `context/specs/32-launch-analytics-and-metrics.md` - the events, the four figures and the two Done-when items
- `context/project-overview.md` "Measuring success" and `context/Roadmap.md` "Pilot" - the targets the figures serve
- `.specs/STATE.md` AD-020, AD-026, AD-054, AD-056, AD-085, AD-086, AD-102, AD-110, AD-118 - the constraints this conforms to
