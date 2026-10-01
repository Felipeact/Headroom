# Spec 15: Nightly sync job

- **Milestone:** 3, bank data
- **Status:** Not started
- **Depends on:** 05, 14

## Goal

Keep every bank up to date automatically, even if a Plaid webhook is missed.

## Build

- `python -m app.jobs.run_due` runs whatever work is due, then exits.
- A Railway `jobs` service runs it on the cron schedule `0 * * * *` (every hour).
- Each business syncs once a night, around 2 AM in its own time zone.
- Only one sync runs per connection at a time.
- Failed syncs are retried, waiting longer each time. A connection that fails 3 nights in a row is flagged as needing attention.

**Docs:** [Railway cron jobs](https://docs.railway.com/reference/cron-jobs)

## Done when

- [ ] With a simulated clock, businesses in Pacific and Newfoundland time each sync once a night.
- [ ] Overlapping runs never sync the same connection twice.
