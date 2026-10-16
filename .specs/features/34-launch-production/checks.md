# 34 - Production checks

Profile: light
Plan: `.specs/features/34-launch-production/plan.md`

32 checks in 5 slices · 7 one-way doors (2 and 3 are interim until spec 34b) · 1 open, blocks go-live (C21)

Railway proofs are named functions in `.specs/features/34-launch-production/proofs.sh`, run from the repository root as `bash .specs/features/34-launch-production/proofs.sh cN`. Each prints `PASS cN` or exits non-zero. Like spec 05's, they read Railway only through `@railway/cli` 5.63.1 (`domain list`, `deployment list`, `logs`, `ssh`, `environment config`, `service list`, `tcp-proxy list`, `variable list`, `config plan`) with an explicit `--environment`. Domains are read from `railway domain list`, never hard-coded. Variable values are never printed.

Railway has no CLI for backup schedules or notification settings, and Sentry alert rules and received emails live in dashboards and inboxes. Those checks are proved by a dated row in `.specs/features/34-launch-production/evidence.md`, written from the user's own confirmation (the AD-117 pattern). `proofs.sh` checks that the row exists, carries the date, and says `confirmed`. Each such check says so.

## Checks

### S1 - Production deploys from `main` · `.railway/` + proofs · ~12k

**C1** - `curl` on `https://<api production domain>/healthz/ready` returns `200` with body exactly `{"status":"ok"}` (AC 1)
Proof: `bash .specs/features/34-launch-production/proofs.sh c1`

**C2** - `curl` on `https://<web production domain>/healthz` returns `200` with body `{"status":"ok"}`, and `/` returns `307` with a `location` containing `/sign-in` (AC 2)
Proof: `bash .specs/features/34-launch-production/proofs.sh c2`

**C3** - The logs of the latest `SUCCESS` production `api` deployment contain Alembic's `Context impl PostgresqlImpl` line, and in the running production `api` (`railway ssh`), `alembic current` prints the same revision as `alembic heads` at `origin/main` (AC 3)
Proof: `bash .specs/features/34-launch-production/proofs.sh c3`

**C4** - In `railway environment config --environment production --json`, `api`, `web`, and `jobs` have source branch `main`. Every commit SHA in their production deployment lists passes `git merge-base --is-ancestor <sha> origin/main` (AC 4, door 1)
Proof: `bash .specs/features/34-launch-production/proofs.sh c4`

**C5** - For `api` and `web`, the newest `SUCCESS` production deployment's commit SHA equals `git rev-parse origin/main` after the release merge, and its `meta.reason` is `deploy` (started by the push, AC 5)
Proof: `bash .specs/features/34-launch-production/proofs.sh c5`

**C6** - `railway service list --environment production --json` lists `Postgres`, `api`, `web`, and `jobs` with only `us-east` regions. `Postgres` has zero domains and zero TCP proxies (AC 6)
Proof: `bash .specs/features/34-launch-production/proofs.sh c6`

**C7** - `GET https://<api production domain>/docs` and `/openapi.json` each return `404` (AC 7)
Proof: `bash .specs/features/34-launch-production/proofs.sh c7`

**C8** - `railway config plan --detailed-exit-code` exits 0 against `production` and against `staging`, with `.railway/railway.ts` at `HEAD` (AC 8, door 1)
Proof: `bash .specs/features/34-launch-production/proofs.sh c8`

**C9** - Evaluating `.railway/railway.ts` with a Railway context for environment `preview` throws an error naming `preview`. Evaluating it for `staging` and for `production` does not throw (AC 9, door 1)
Proof: `bash .specs/features/34-launch-production/proofs.sh c9`

**C10** - The compiled IaC for `production` gives `api`, `web`, and `jobs` branch `main` and `SENTRY_ENVIRONMENT` `production`. For `staging` it gives branch `development` and `staging`. Both carry the same service names, start commands, `preDeploy`, health checks, and volume usage alerts at 80, 95, and 100 (door 1, AC 25 volume half)
Proof: `bash .specs/features/34-launch-production/proofs.sh c10`

### S2 - Staging and production share no credentials · new script + test · ~8k

**C11** - `python3 .specs/features/34-launch-production/check_no_shared_credentials.py` exits 0 against the live project (AC 10, spec Done-when 2)
Proof: `bash .specs/features/34-launch-production/proofs.sh c11`

**C12** - Given variables where `api` `RESEND_API_KEY` has the same value in both environments, the script exits 1 and prints exactly the line `api RESEND_API_KEY` (AC 11, door 5)
Proof: `uv run --project services/core pytest .specs/features/34-launch-production/test_check_no_shared_credentials.py -k shared_secret_fails`

**C13** - Given variables where every allowlisted name (`NEXT_PUBLIC_CLERK_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL`, `POSTHOG_HOST`, `POSTHOG_APP_HOST`, `EMAIL_MAILING_ADDRESS`, `FORECAST_STRATEGY`, `PLAID_CLIENT_ID`, `RAILWAY_PROJECT_ID`) is equal and nothing else is, the script exits 0. A name not on the list, such as `NEW_SECRET`, with equal values exits 1 (door 5)
Proof: `uv run --project services/core pytest .specs/features/34-launch-production/test_check_no_shared_credentials.py -k allowlist`

**C14** - In both the passing and the failing fixture runs, no fixture variable value appears anywhere in stdout or stderr (AC 12)
Proof: `uv run --project services/core pytest .specs/features/34-launch-production/test_check_no_shared_credentials.py -k no_value_printed`

**C15** - When reading one service's variables fails (the CLI exits non-zero), the script exits 1 and names that service and environment, without comparing anything (plan Observable, fails halfway)
Proof: `uv run --project services/core pytest .specs/features/34-launch-production/test_check_no_shared_credentials.py -k cli_failure`

**C16** - Production `api` has `PLAID_ENV` equal to `production`, and `API_DOCS_ENABLED` unset or not `true`. The proof prints only `match` or `mismatch` (AC 13, AC 7)
Proof: `bash .specs/features/34-launch-production/proofs.sh c16`

### S3 - Production's own external services · proofs + evidence · ~5k

**C17** - In production `api` (`railway ssh`), a Clerk Backend API user lookup for the founder's address returns 1 user. The same lookup in staging `api` returns 0. The proof prints only the counts (AC 14, AC 13 Clerk half, door 3)
Proof: `bash .specs/features/34-launch-production/proofs.sh c17`

**C18** - An email that production sends to the Resend account owner's address arrives From `onboarding@resend.dev`, and Resend's log lists it under the production API key's name. Proved by an evidence row (AC 15, door 3)
Proof: `bash .specs/features/34-launch-production/proofs.sh c18`

**C19** - Production `api` `EMAIL_SENDER` is `resend` and `EMAIL_FROM` contains `onboarding@resend.dev`. The proof prints `match` or `mismatch` (door 3)
Proof: `bash .specs/features/34-launch-production/proofs.sh c19`

**C20** - Production `WEB_URL`, `API_PUBLIC_URL`, `PLAID_WEBHOOK_URL`, and `CLERK_AUTHORIZED_PARTIES` are built from the production Railway domains exactly as door 2 states (`PLAID_WEBHOOK_URL` = `API_PUBLIC_URL` + `/v1/webhooks/plaid`) (door 2)
Proof: `bash .specs/features/34-launch-production/proofs.sh c20`

**C21** - Open, blocks go-live: once production `PLAID_SECRET` is a Plaid Production secret, the founder's own bank connected in production reaches status `synced`. Production logs show `POST /v1/webhooks/plaid` answered `200` (AC 16)
Proof: `bash .specs/features/34-launch-production/proofs.sh c21`

### S4 - Backups and a proven restore · runbook + evidence · ~6k

**C22** - The production `Postgres` volume has the Daily, Weekly, and Monthly backup schedules on. Proved by an evidence row (AC 17)
Proof: `bash .specs/features/34-launch-production/proofs.sh c22`

**C23** - After the door 6 restore and redeploy: production `/healthz/ready` returns `200`. In production `api` (`railway ssh`), the businesses named exactly `Restore drill A` count 1 and `Restore drill B` count 0. The proof prints only the counts (AC 18, spec Done-when 1, door 6)
Proof: `bash .specs/features/34-launch-production/proofs.sh c23`

**C24** - `context/operations/production.md` has a `## Restore a backup` section with numbered steps. It also has a `## Last drill` section giving an ISO date, the backup's timestamp, and a whole number of minutes (AC 19)
Proof: `bash .specs/features/34-launch-production/proofs.sh c24`

**C25** - After the drill, the production businesses named `Restore drill A` or `Restore drill B` count 0 (door 6 cleanup)
Proof: `bash .specs/features/34-launch-production/proofs.sh c25`

### S5 - The team hears about failures · 2 app files + tests · ~25k

**C26** - A Plaid failure during `sync_connection` logs `bank_sync.sync_failed` at level `error` with `business_id`, `connection_id`, `error_type`, `error_code`, and `request_id`. A sandbox access token placed on the failing client appears nowhere in the captured log line (AC 20)
Proof: `cd services/core && uv run pytest tests/test_alerting.py -k sync_failed_plaid_is_error`

**C27** - A non-Plaid exception during the nightly sync (`_log_failure`) logs `bank_sync.sync_failed` at level `error` with `business_id`, `connection_id`, and `error_type` (AC 20)
Proof: `cd services/core && uv run pytest tests/test_alerting.py -k sync_failed_other_is_error`

**C28** - When fetching Plaid's webhook-verification key raises `PlaidError`, the webhook route logs `plaid.request_failed` at level `error`. A webhook with an invalid signature logs nothing at level `error` (AC 21)
Proof: `cd services/core && uv run pytest tests/test_alerting.py -k webhook_levels`

**C29** - With Sentry started on a fake transport, `structlog.get_logger("x").error("bank_sync.sync_failed", business_id=..., access_token=<sandbox token>)` produces exactly one event whose message is `bank_sync.sync_failed`. The sandbox token appears nowhere in it. A `warning` line produces zero events (AC 22, door 4)
Proof: `cd services/core && uv run pytest tests/test_sentry.py -k error_log_is_one_event`

**C30** - Running `python -m app.sentry_check` in production `api` produced a Sentry alert email to the team, tagged `environment: production`, within 5 minutes. Proved by an evidence row (AC 23)
Proof: `bash .specs/features/34-launch-production/proofs.sh c30`

**C31** - Sentry projects `headroom-api` and `headroom-web` each have an issue alert filtered to `environment:production` and a metric alert at more than 10 errors in 1 hour, also on `production`, both emailing the team. Railway emails the team when a deployment fails or crashes. Proved by evidence rows, one per rule (AC 24, AC 25)
Proof: `bash .specs/features/34-launch-production/proofs.sh c31`

**C32** - In `services/core`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy app`, and `uv run pytest` each exit 0 (AGENTS.md, "Before you finish a task"; no frontend file changes)
Proof: `bash .specs/features/34-launch-production/proofs.sh c32`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| Landing doors (7) | door 1 two-env IaC C4 · C8 · C9 · C10 · door 2 interim URLs C20 · door 3 interim identity and email C17 · C18 · C19 · door 4 alert = Sentry event C29 · C31 · door 5 credential check C11 · C12 · C13 · C14 · C15 · door 6 restore drill C23 · C24 · C25 · door 7 Sentry message C29 | - |
| Surface routes (0) | none: the plan's `Surface` adds no route | - |
| production services (4) | `Postgres` C6 · C23 · `api` C1 · C3 · C6 · `web` C2 · C6 · `jobs` C4 · C6 | - |
| production URLs probed (4) | api `/healthz/ready` C1 · api `/docs` + `/openapi.json` C7 · web `/healthz` C2 · web `/` C2 | - |
| IaC environments (3) | `production` C9 · C10 · `staging` C9 · C10 · other C9 | - |
| credential check outcomes (4) | clean C11 · shared secret C12 · allowlisted equal C13 · CLI failure C15 | - |
| external services, production side (5) | Clerk C17 · Resend C18 · C19 · Plaid C16 · C21 · Sentry DSN C11 · C30 · PostHog C11 | - |
| failure kinds the team hears about (5) | sync fails C26 · C27 · errors spike C31 · emails fail existing (`email.failed` already logs at `error`, `notifications/service.py:225`) + C29 · webhooks fail C28 · deploy fails C31 | - |
| `bank_sync.sync_failed` sites (2) | Plaid error C26 · other exception C27 | - |
| webhook log levels (2) | key fetch fails -> `error` C28 · invalid signature -> not `error` C28 | - |
| backup schedules (3) | Daily C22 · Weekly C22 · Monthly C22 | - |
| restore drill outcomes (3) | app healthy C23 · A present C23 · B absent C23 | - |
| startup config: `SENTRY_ENVIRONMENT` / branch (3 services) | `api` C10 · `web` C10 · `jobs` C4 · C10 | - |
| finish-checks, API (4) | `ruff format --check` C32 · `ruff check` C32 · `mypy app` C32 · `pytest` C32 | - |

- Claims naming a status code or a route: C1, C2, C7, C21. Each proof sends a real HTTPS request or reads production logs.
- C21 has its proof but stays red until Plaid issues the Trial secret (blocks go-live, not this build).
- C18, C22, C30, and C31 rest on the user's confirmation recorded in `evidence.md`. No CLI or API this repository already uses can read those settings.

## Swept

- validation: C9 (an unknown environment fails the IaC), C16 (`PLAID_ENV`), C20 (URLs derived from the domains)
- failure modes: C15 (the credential check stops on a partial read). Existing: a failed pre-deploy or health check keeps the previous deployment (spec 05 C4, C5)
- idempotency: C8 (`config plan` shows no diff after apply, for both environments). Existing: `alembic upgrade head` at head is a no-op (spec 03)
- authorization: C6 (production `Postgres` unreachable from outside), C7 (API docs off), C11 (no credential opens both environments)
- concurrency: n/a. This change adds no shared state or handler. Two overlapping production pre-deploys run the same migration chain spec 05 already deploys to staging
- data lifecycle: C22 (schedules and their retention), C23 (restore), C25 (drill data deleted)
- dependency failure: C26, C27, C28 (Plaid failures now reach the team), C21 (Plaid production, open)
- state transitions: C23 (volume: backed up -> restored -> serving), C5 (deployment reaches `SUCCESS` from `main`)
- observability: C29, C30, C31

## Handoff

- Files touched: `.railway/railway.ts` 6 KB, `bank_sync/service.py` 43 KB (two log lines, read around them), `bank_sync/api.py` 16 KB, `tests/test_sentry.py` 5 KB, new `tests/test_alerting.py` ~6 KB, new `check_no_shared_credentials.py` + test ~10 KB, new `proofs.sh` ~18 KB, new `context/operations/production.md` ~4 KB, `evidence.md` ~2 KB. Read: `plan.md` 21 KB, `checks.md` 14 KB, STATE rows ~10 KB, plus existing webhook tests ~15 KB: ~170 KB / 4 ≈ 43k. Railway and dashboard round-trips while provisioning ≈ 40k. Total ≈ 83k, under the 150k budget, so one builder
- Mechanism: one builder (no ask, under budget)
- Order: S5 and S2 first (local code, no go-ahead needed), then `.railway/railway.ts` (S1). Then, each with its own go-ahead: `railway config apply` for production, variables set by the user, the release PR into `main`, and the restore drill (S4). C21 stays open until Plaid issues the Trial secret
