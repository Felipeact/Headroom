# Production

Spec 34. How production is set up, and how to bring its database back. This is written to be followed by one person under stress, like `context/security/incident-response.md`.

## What runs where

- Railway project `headroom`, environment `production`, region US East. It has the same services as staging: `Postgres`, `api`, `web`, and `jobs`.
- Settings live in `.railway/railway.ts`. Production differs from staging in two ways: it deploys from `main`, and it sets `SENTRY_ENVIRONMENT=production`. Check for drift with `railway environment link production`, then `railway config plan --detailed-exit-code`. Link `staging` again afterwards.
- A merge into `main` deploys production once the `web` and `api` checks pass. `api` runs `alembic upgrade head` before it starts.
- The addresses are Railway's generated `*.up.railway.app` domains. Spec 34b moves them to Headroom's own domain. **Invite no client before that move.** Email links and the Plaid webhook point at these addresses.
- Every production secret differs from its staging counterpart. Check with `python3 .specs/features/34-launch-production/check_no_shared_credentials.py`. It prints names only, and exit 0 means nothing is shared.

## Where alerts go

- **Sentry:** `headroom-api` and `headroom-web` each have an issue alert and a "more than 10 errors in 1 hour" alert, both filtered to `environment:production`, both emailing the founder. Any `log.error(...)` line in the API becomes a Sentry event named after the event. That covers `bank_sync.sync_failed`, `plaid.request_failed` (webhook verification), `email.failed`, and `jobs.job_failed`.
- **Railway:** emails the founder when a deployment fails or crashes, and when the database volume reaches 80, 95, or 100 percent full.
- To test the path, run `railway ssh --service api --environment production -- python -m app.sentry_check`. The alert email should arrive within 5 minutes.

## Backups

The production `Postgres` volume has the Daily, Weekly, and Monthly schedules on: Railway, then `Postgres`, then **Backups**. Railway keeps daily backups for 6 days, weekly for 27 days, and monthly for 89 days. A restore only works inside `production`: Railway cannot restore into another environment.

Once a month, open the Backups tab and check that a backup from the last 24 hours is listed. Railway sends no alert when a backup fails.

## Restore a backup

Restoring rolls the database back to the backup's time. Everything written after it is lost. Before you start, decide that losing that data is the lesser harm, and write the time and the reason in an incident log (`context/security/incident-<YYYY-MM-DD>.md`).

1. Railway, environment `production`, service `Postgres`, **Backups** tab. Find the backup by its date stamp and note its timestamp.
2. Click **Restore** on it. Railway creates a new volume from the backup, mounts it in place of the current one, and keeps the old volume unmounted, under its old name. Nothing is deleted.
3. The change is staged. Click **Deploy** to apply it. Note the time: the clock starts here.
4. Wait for `Postgres` to show its new deployment as Active. Then redeploy `api` and `jobs` (each service, **Redeploy**), so they reconnect.
5. Run `curl -i https://<api production domain>/healthz/ready` until it answers `200 {"status":"ok"}`. Note the time: the clock stops here.
6. Sign in and check that the data you expected is there. If you're rehearsing, run `bash .specs/features/34-launch-production/proofs.sh c23`.
7. If the restore is wrong, mount the old volume again from the `Postgres` service's volume settings. It still holds the data from before the restore.
8. Write the date, the backup's timestamp, and the minutes from step 3 to step 5 under "Last drill" below.

## Last drill

Not yet run. Spec 34 runs it in production before any client signs up.
