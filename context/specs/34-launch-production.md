# Spec 34: Production

- **Milestone:** 7, production
- **Status:** In progress
- **Depends on:** 33

## Goal

Set up the production environment that real clients will use.

## Build

- A Railway `production` environment in US East, deploying from `main`, with no credentials shared with staging.
- Headroom's domain on the web app.
- Production setups for each service:
  - a Clerk production instance
  - a sending domain verified in Resend
  - Plaid production keys, once Plaid has approved access
- Database backups turned on, and a restore that has been tested and timed.
- Team alerts through Sentry and Railway when a sync fails, errors spike, or emails or webhooks fail.

## Done when

- [ ] A backup restores to a fresh database, and the app runs against it.
- [ ] Staging and production share no credentials.
