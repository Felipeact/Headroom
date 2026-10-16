# Spec 08: API errors, logging, and monitoring

- **Milestone:** 2, foundations
- **Status:** Done
- **Depends on:** 03 (can run alongside 06 and 07)

## Goal

Make every API failure consistent, logged safely, and visible.

## Build

- Every error returns RFC 9457 problem details (`application/problem+json`).
- Structured JSON logs, with a filter that removes tokens, account numbers, and any field named like a secret.
- Sentry in the API, set up by following Sentry's FastAPI guide.
- An append-only `audit_log` table, with an `audit.record(...)` helper.

**Docs:** [Sentry for FastAPI](https://docs.sentry.io/platforms/python/integrations/fastapi/)

## Done when

- [x] A test proves that a secret written to a log line is removed.
- [x] An unknown route returns problem details with status 404.
- [x] A deliberate test error shows up in Sentry.
