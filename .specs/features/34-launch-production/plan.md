# Spec 34: Production

## Problem

Spec 34 is the next roadmap item: specs 01–33 are Done, and 34 is `Not started`. Its only dependency (33) is Done.

Headroom runs only in `staging`. Staging deploys every push to `development`, uses Clerk's development instance, the Plaid sandbox, and the Resend test sender, and nothing backs up its database. A pilot client (spec 36) has nowhere to sign up that is meant to stay up and keep their data. Today, if the Postgres volume were lost, every connection, forecast, and alert would be gone with no way back. Nobody would hear about it either: a failed bank sync and a failed webhook are only `warning` log lines, which never reach Sentry, and no Sentry alert rule exists. The spec gives no figures. The roadmap fixes the order: production before the pilot (spec 36), and "Migrations run automatically before each deploy" (AGENTS.md, Deployment).

When this ships, a release merged into `main` deploys to a separate Railway `production` environment at Headroom's own domain. That environment has its own Clerk, Resend, Plaid, Sentry, and PostHog credentials. Its database is backed up on a schedule, and one restore has been rehearsed and timed. The team gets an email when a sync fails, errors spike, an email fails, a webhook fails, or a deploy fails.

## Flow

This reuses the staging setup as-is: the one `.railway/railway.ts` (AD-005, AD-007), the `/healthz/*` probes (AD-002, AD-028), `alembic upgrade head` as pre-deploy, `app.monitoring.init_sentry` with its redaction (AD-010), and the structlog-to-stdlib path that already turns every `log.error` into a Sentry event. Nothing new runs in the request path.

1. A release PR merges `development` into `main` on GitHub. The `web` and `api` checks pass (`checkSuites`), and Railway environment `production` (door 1) builds `api`, `web`, and `jobs` from `main`.
2. `api` pre-deploy runs `alembic upgrade head` against production `Postgres` (exists in Railway's default `production` env, empty since spec 05), over its private host (AD-006). Then `fastapi run`, and `/healthz/ready` gates the switch.
3. `web` answers on `headroom.felipeviana.com` and `api` on `api.headroom.felipeviana.com`, as Railway custom domains (door 8). Sign-in is the user's Clerk production instance on `headroom.felipeviana.com` (door 9). Email still uses Resend's test sender with its own key until a sending domain is verified.
4. `jobs` runs hourly with production's secrets. `bank_sync.sync_failed`, Plaid webhook failures, and `email.failed` are logged at `error` (door 4). `app.monitoring` (exists) sends them to Sentry, where a production-only alert rule emails the team.
5. Railway backs up the production `Postgres` volume on a daily, weekly, and monthly schedule. A restore swaps in a new volume in the same environment (door 6).
6. Proof, outside the app: `check_no_shared_credentials.py` (door 5) reads `railway variable list --json` for both environments and compares the values without printing any of them.

## Impact

| Front | What changes |
| --- | --- |
| DNS | `felipeviana.com`'s zone gets the records Railway lists for the two custom domains, plus Clerk's records under `headroom.felipeviana.com` (`clerk.`, `accounts.`, and the email ones). The user adds them at the registrar |
| hosting | Railway's default `production` environment (left empty by spec 05, AD-005) gets `Postgres`, `api`, `web`, `jobs`, and the volume, with backups on. It deploys only from `main` |
| repository | `.railway/railway.ts` stops throwing for `production`. The branch, `SENTRY_ENVIRONMENT`, and custom domains are chosen per environment. Staging's live settings must stay exactly as they are (`railway config plan --detailed-exit-code` exits 0 for `staging` before and after) |
| branch flow | the first deploy needs a release PR from `development` into `main`. AGENTS.md allows that only when the user asks. Every later merge into `main` deploys production with no manual step |
| web Sentry | `web` gains `NEXT_PUBLIC_SENTRY_DSN` (preserved) and `NEXT_PUBLIC_SENTRY_ENVIRONMENT` in both environments. Staging `web` has never set them, so applying the file to staging adds `NEXT_PUBLIC_SENTRY_ENVIRONMENT=staging` and nothing else (found while building) |
| logging | `bank_sync.sync_failed` (2 sites) and the Plaid webhook's `plaid.request_failed` go from `warning` to `error`. Each becomes a Sentry event in staging too. Staging's Sentry gets noisier, and no rule alerts on staging |
| configuration | about 25 variables are set per environment by `railway variable set`, never in a file. `.env.example` files are unchanged |
| external services | new: Clerk production instance, Resend domain, Plaid production secret, a production client key (DSN) in each Sentry project, a production PostHog project, and DNS records at the registrar |
| stored data | a new, empty production database. Migrations create the schema. Nothing to migrate. Staging data never moves to production |
| security docs | `context/security/access.md` and `incident-response.md` already name production and need no change. The new runbook `context/operations/production.md` holds the restore steps and the measured time |

## Relations

None. The stored-data shape doesn't change. Production gets exactly the schema the migration chain produces.

## Surface

None. Nothing new is consumed outside. The production domains serve the routes that already exist. Their signatures don't change. The domain names themselves are door 2.

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. Two environments in one IaC file | `defineRailway((ctx) => ...)` sets `const env = ctx.isEnvironment("production") ? PRODUCTION : ctx.isEnvironment("staging") ? STAGING : fail()`, with `PRODUCTION = { branch: "main", sentryEnvironment: "production", domains: {...} }` and `STAGING = { branch: "development", sentryEnvironment: "staging", domains: {} }`. Same service names, regions, start commands, and `preserve()` variables for both. `jobs` keeps its `${{api.*}}` references | two files or a named partial: the README calls a partial a last resort, and two files drift. Branching on the environment keeps one reviewed diff for both (AD-007) |
| 2. Interim production URLs (until spec 34b) | Railway-generated domains, no `domains` entry in IaC: `WEB_URL=https://<web production>.up.railway.app`, `API_PUBLIC_URL=https://<api production>.up.railway.app`, `PLAID_WEBHOOK_URL=<API_PUBLIC_URL>/v1/webhooks/plaid`, `CLERK_AUTHORIZED_PARTIES=<WEB_URL>`. No client is invited while these are live: email links and the Plaid webhook bind to the host, and spec 34b moves them before spec 36 | waiting for a domain before building anything: backups, the restore drill, credential separation, and alerts don't need one. Inviting pilot clients on Railway names: their unsubscribe links (AD-108) and Plaid items would break at the move |
| 3. Interim identity and email (until spec 34b) | Clerk: a new Clerk application `Headroom Production`, using its development instance (its own `pk_test_`/`sk_test_` keys, never staging's). Email: `EMAIL_SENDER=resend` with a new Resend API key and `EMAIL_FROM="Headroom <onboarding@resend.dev>"`, which only delivers to the Resend account owner's address | staging's Clerk instance: shared credentials and shared users (fails S2). A Clerk production instance and a Resend domain: both need a domain you own (Clerk: "You will need to have a domain you own") |
| 4. "A team alert is a Sentry event" | a failure the team must hear about is logged with `log.error("<noun>.<verb_past>", ...)` and no message text beyond the event name, so Sentry groups it as one issue per event name. One Sentry issue alert per project, filtered to `environment:production`, emails the team | a second alerting path (Railway log alerts, a webhook to email): two places to keep in sync. Raising every warning: a single network blip would page. This sets the precedent later specs copy |
| 5. "No shared credentials" check | `.specs/features/34-launch-production/check_no_shared_credentials.py` reads `railway variable list --service <s> --environment <e> --json` for `api`, `web`, and `jobs` in both environments. Every variable whose value is equal in both, after resolving references, fails unless its name is in a fixed allowlist of non-secret settings (`NEXT_PUBLIC_CLERK_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL`, `POSTHOG_HOST`, `POSTHOG_APP_HOST`, `EMAIL_MAILING_ADDRESS`, `FORECAST_STRATEGY`, `PLAID_CLIENT_ID`, `RAILWAY_*`). It prints names only, never values, and exits 1 on any match | a denylist of secret names: a new secret added later would pass silently. Comparing by eye in the dashboard: not repeatable |
| 6. Restore rehearsal | in `production`, before any client signs up: create business `Restore drill A`, take a manual backup, create `Restore drill B`, restore that backup (Railway mounts a new volume and keeps the old one unmounted), redeploy, then check that `/healthz/ready` returns `200`, A is visible, and B is not. Time is measured from clicking Restore to the first `200` and written into `context/operations/production.md`. Both drill businesses are deleted afterwards | a `pg_dump` restored into a fresh local database: production `Postgres` has no public proxy (AD-006), and opening one to take a dump is the exposure that rule prevents. Railway can't restore across environments ("Backups can only be restored into the same project + environment"), so staging can't be the target |
| 7. Sentry message for a structlog line (found while building: the log record's `msg` is structlog's event dict, so every line reached Sentry with the whole dict as its message, and grouping per event name (door 4) failed) | `app.monitoring._before_send` reads `hint["log_record"]`. When `record.msg` is a dict, it sets `logentry` to `{"message": <event>, "formatted": <event>, "params": []}` and moves the other non-underscore fields into `extra`, before `app.log.redact` | the `structlog-sentry` package: a new dependency for one field. Logging the event name as the stdlib message: every call site would need changing |
| 8. Production URLs (supersedes door 2, user decision 2026-10-16) | `web`: `domains: ["headroom.felipeviana.com"]`, `api`: `domains: ["api.headroom.felipeviana.com"]`, production only, in `.railway/railway.ts`. `WEB_URL=https://headroom.felipeviana.com`, `API_PUBLIC_URL=https://api.headroom.felipeviana.com`, `PLAID_WEBHOOK_URL=https://api.headroom.felipeviana.com/v1/webhooks/plaid`, `CLERK_AUTHORIZED_PARTIES=https://headroom.felipeviana.com` | Railway's generated domains (door 2): the user's Clerk production instance only signs people in on `headroom.felipeviana.com` and its subdomains. `app.<domain>` on a separate Headroom domain: none exists yet; moving later breaks every sent link, so this is the address clients keep until a deliberate move |
| 9. Production sign-in (supersedes door 3's Clerk half, user decision 2026-10-16) | the user's Clerk production instance for `headroom.felipeviana.com` (`pk_live_`/`sk_live_` keys, `CLERK_JWT_KEY` = that instance's PEM public key), on `api` and `web` in production only. Door 3's email half stands: Resend's test sender with its own key | a separate development-instance app (door 3): the user chose the live instance. Development instances show a banner, cap users, and their sessions don't carry over to the live instance later |
| 10. `EMAIL_SENDER` on the door 5 allowlist (found while building: the live check flagged it on 2026-10-16) | `ALLOWED` gains `EMAIL_SENDER`; every other door 5 name stands | leaving it off: `resend` is a mode, not a credential, so the check would fail forever on a setting both environments must share |

- Doors 1, 4, 5, 7, 8, and 9 reach past this feature: every later alert, credential, sent link, and sign-in. Each gets a row in `.specs/STATE.md` `## Decisions`. Doors 8 and 9 supersede door 2 and door 3's Clerk half. Door 3's email half (the test sender) stays interim until a Resend domain is verified.
- Alert thresholds, backup schedules, and Railway notification settings are dashboard settings you can reverse in a minute. They are criteria, not doors.

## Criteria

### S1: Production deploys from `main` (P1)

A merge into `main` puts the release live at its Railway domain. Nothing else deploys there.

**Acceptance Criteria**

1. WHEN a deployment of `api` in `production` succeeds THEN `GET https://api.headroom.felipeviana.com/healthz/ready` SHALL respond `200` with body exactly `{"status": "ok"}`
2. WHEN a deployment of `web` in `production` succeeds THEN `GET https://headroom.felipeviana.com/healthz` SHALL respond `200` with body `{"status":"ok"}`, and `GET https://headroom.felipeviana.com/` SHALL respond `307` to the sign-in page
3. WHEN `api` deploys in `production` THEN its deploy log SHALL show `alembic upgrade head` finishing before the new deployment starts
4. WHEN a commit reaches `development` THEN Railway SHALL NOT start any deployment in `production` for it
5. WHEN a commit reaches `main` and its `web` and `api` checks succeed THEN Railway SHALL start `production` deployments for that SHA with no manual action
6. The `production` services `Postgres`, `api`, `web`, and `jobs` SHALL run in `us-east4-eqdc4a`, and `Postgres` SHALL have no public domain or TCP proxy
7. WHEN `GET https://api.headroom.felipeviana.com/docs` or `/openapi.json` is requested THEN the API SHALL respond `404` (`API_DOCS_ENABLED` unset, AD-133)
8. WHEN `railway config plan --detailed-exit-code` runs against `production` and against `staging` THEN each SHALL exit 0
9. IF `.railway/railway.ts` is evaluated for an environment other than `staging` or `production` THEN it SHALL throw, and `railway config plan` SHALL fail

**Independent test:** `curl -i` both health URLs after a merge into `main`. The `production` deployment list shows the `main` SHA, and the `staging` list doesn't.

### S2: Staging and production share no credentials (P1)

**Acceptance Criteria**

10. WHEN `check_no_shared_credentials.py` runs against the live project THEN it SHALL exit 0
11. IF any variable outside the door 5 allowlist has the same value in `staging` and `production` on `api`, `web`, or `jobs` THEN the script SHALL exit 1 and print `<service> <NAME>` for each match
12. The script's output SHALL contain no variable value, in pass or fail (checked against fixtures with known values)
13. The production `api` SHALL carry `PLAID_ENV` = `production`, and `api` and `web` SHALL carry the Clerk production instance's keys for `headroom.felipeviana.com` (`pk_live_` prefix), never staging's

**Independent test:** run the script and get exit 0. Run it on a fixture where `RESEND_API_KEY` matches and get exit 1, with `api RESEND_API_KEY` printed and the value absent.

### S3: Production's own external services work (P1)

**Acceptance Criteria**

14. WHEN the founder signs up at `https://headroom.felipeviana.com/sign-up` THEN the Clerk production instance SHALL list the new user, and staging's Clerk instance SHALL NOT
15. WHEN production sends an email to the Resend account owner's address THEN it SHALL arrive From `onboarding@resend.dev`, and Resend's log SHALL show it under the production API key
16. WHERE production `PLAID_SECRET` is a Plaid Production (Trial or paid plan) secret, WHEN the founder connects their own business bank in production THEN the connection SHALL sync (spec 14 behaviour), and Plaid's webhook SHALL reach `https://api.headroom.felipeviana.com/v1/webhooks/plaid` with `200`

**Independent test:** sign up at `https://headroom.felipeviana.com`. Clerk's production instance lists the user, and the invitation test email arrives from `onboarding@resend.dev`.

### S4: Backups exist and one restore is proven (P1)

**Acceptance Criteria**

17. The production `Postgres` volume SHALL have the Daily, Weekly, and Monthly backup schedules on
18. WHEN the door 6 drill restores the backup taken between `Restore drill A` and `Restore drill B` THEN `https://api.headroom.felipeviana.com/healthz/ready` SHALL respond `200`, `Restore drill A` SHALL be listed for its owner, and `Restore drill B` SHALL NOT
19. WHEN the drill finishes THEN `context/operations/production.md` SHALL record the date, the backup's timestamp, and the measured minutes from Restore to the first `200`, plus the restore steps in order

**Independent test:** follow the runbook. The owner sees A and not B.

### S5: The team hears about failures (P1)

**Acceptance Criteria**

20. IF a bank sync fails (`PlaidError` or any other exception, both sites in `bank_sync.service`) THEN the API SHALL log `bank_sync.sync_failed` at level `error` with the same fields as today, and no token or account number
21. IF Plaid's webhook-verification key cannot be fetched (`PlaidError` in the webhook route) THEN the API SHALL log `plaid.request_failed` at level `error`. An invalid signature SHALL stay at `warning`, because strangers can trigger it
22. WHEN an `error`-level log line is written with `SENTRY_DSN` set THEN one Sentry event SHALL be sent with the event name as its message, after `app.log.redact`
23. WHEN `python -m app.sentry_check` runs in production `api` THEN the team address SHALL receive a Sentry alert email for `environment:production`
24. The Sentry projects SHALL each have a metric alert that emails the team when `production` errors exceed 10 in 1 hour
25. WHEN a `production` deployment fails or crashes THEN Railway SHALL email the team, and the volume SHALL keep its 80, 95, and 100 percent usage alerts

**Independent test:** run `python -m app.sentry_check` through `railway ssh` in production `api`. The alert email arrives within 5 minutes.

## Out of scope

| Excluded | Why |
| --- | --- |
| Applying to Plaid for production access | the user's application in the Plaid Dashboard. This spec only installs the keys |
| Resend sending domain | spec 34b. Production keeps Resend's test sender, which only delivers to the Resend account owner, so no client email goes out until then (door 3, email half) |
| Backups for `staging` | staging holds only synthetic data (spec 05) |
| Legal pages, support address, marketing site on the root domain | spec 35 |
| Onboarding pilot clients, billing | spec 36, Stripe Payment Links by hand |
| Uptime monitoring and a status page | not asked for. `/healthz/ready` already gates deploys |
| Enforcing the CSP | AD-130: stays report-only until the violation rows are fixed |
| A second `api` replica | AD-129: rate limits need a shared store first |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Sentry: separate projects or keys | production gets its own client key (DSN) in each existing Sentry project, `headroom-api` and `headroom-web`. Alerts filter `environment:production` | a project can have several client keys. That satisfies "no shared credentials" while keeping one issue list per app | n |
| PostHog | a new production PostHog project, with its own project token, project ID, and personal API key | a shared project would mix staging test events into the pilot metrics (spec 32) | n |
| `PLAID_CLIENT_ID` | allowed to be equal across environments (door 5 allowlist) | Plaid issues one client ID per team across all environments, and only the secret differs. It's an identifier, not a credential | n |
| Team alert address | the founder's own email, the one Sentry and Railway already use | access.md: one person has production access | n |
| Error spike threshold | more than 10 `error` events in 1 hour, per project, `production` only | pilot scale is 5–10 businesses. Change in Sentry without a spec | n |
| Who sets up external services | the user creates the `Headroom Production` Clerk application, the Resend API key, Sentry keys, PostHog project, and backup schedules in each dashboard. The agent applies IaC, sets variables with `railway variable set` from values the user pastes into the terminal, and runs every proof | these steps need the user's accounts. Variable values never pass through chat | n |
| Release PR and production deploys | the first `development` → `main` PR, and every `railway config apply` against `production`, wait for the user's explicit go-ahead | AGENTS.md: PRs into `main` only when the user asks. Blast-radius rule | n |
| Drill data | the drill businesses are created by the founder's own production account and deleted after | no client data exists yet. AGENTS.md forbids real customer data in tests, and the founder's own account isn't customer data | n |

| No domain yet | the custom domain, the Clerk production instance, and the Resend sending domain move to a new spec 34b, done before spec 36. Spec 34 runs on doors 2 and 3 | user has no domain (2026-10-16), and approved the plan with this split | y |
| Plaid Production secret | the user applies for Plaid's free Trial plan (US/Canada, 10 Production Items, no OAuth registration for Canadian banks). Until a secret is issued, production `api` gets a random placeholder `PLAID_SECRET` so it starts, and AC 16 waits for the secret | user approved the plan with this default (2026-10-16) | y |
| Clerk and domain in production | production runs on `headroom.felipeviana.com` with the user's live Clerk instance (doors 8, 9). This supersedes the rows "No domain yet" (its domain and Clerk parts) and the earlier "no Clerk variable for now" | user chose option 1, 2026-10-16 | y |
| Restore route | the door 6 drill, in production, before any client | user approved the plan (2026-10-16) | y |

**Open questions:**

| # | Kind | Question | Until answered |
| --- | --- | --- | --- |
| 1 | blocks go-live | When does Plaid issue the Trial Production secret? | AC 16 (C-numbers in checks.md) waits for it. Spec 36 can't onboard a client |

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| command `check_no_shared_credentials.py` | output format | AC 11, AC 12: `<service> <NAME>` per match, never a value |
| command `check_no_shared_credentials.py` | exit codes | AC 10, AC 11: 0 clean, 1 on a match. A Railway CLI failure is also 1, with the CLI's exit code named |
| command `check_no_shared_credentials.py` | flags and defaults | n/a: no flags. It reads the linked project, and both environment names are fixed |
| command `check_no_shared_credentials.py` | fails halfway | non-zero exit with the service and environment it couldn't read. A partial comparison never reports success |
| scheduled task: deploy on merge into `main` | what triggers it, what it skips | AC 4, AC 5 |
| scheduled task: deploy on merge into `main` | fails halfway | existing: the pre-deploy or health check fails and Railway keeps the previous deployment (spec 05 AC 4, AC 5); AC 25 emails |
| scheduled task: Railway backups | output, failure | AC 17. A backup failure shows in Railway's Backups tab. No alert exists for it in Railway, so it's checked in the runbook's monthly line |
| document `context/operations/production.md` | structure and what the reader does next | AC 19: the restore steps in order, the measured time, and the date of the last drill. Written to be followed by one person under stress, like incident-response.md |
| screens on the production web domain | loading, empty, error, unauthorised, 375 px, keyboard | n/a: no screen changes. Specs 07–32 already proved them. AC 14 checks only that Clerk's production instance serves them |
| API `/v1/*` in production | errors, auth, rate limits, versioning | existing: unchanged (AD-008, AD-128–AD-133). AC 7 keeps the docs off |

## Sources

- `context/specs/34-launch-production.md`: the build list and the two "Done when" items
- `AGENTS.md`, sections Deployment, Branches, and Security and data handling: `main` → production, migrations before deploy, secrets only in Railway variables
- Railway docs, [Backups](https://docs.railway.com/reference/backups): restores mount a new volume, only in the same project and environment
