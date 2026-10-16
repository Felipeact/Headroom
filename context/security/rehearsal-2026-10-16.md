# Incident rehearsal, 2026-10-16

Date: 2026-10-16, 11:14 to 11:30 PDT (16 minutes)
Scenario: tabletop on staging, synthetic data. At 02:00 Sentry alerts on a staging `api` error whose breadcrumbs hold a full `access-sandbox-...` Plaid access token, from `POST /v1/businesses/{id}/bank/connections/{id}/repair`. An 18:00 deploy added a debug log line; Railway shows it 14 times, for 2 businesses.
Participants: Felipe Viana (founder; walked every dashboard step on staging), Claude (agent; checked each step against the code and `.railway/railway.ts`, drafted the incident log and the client notice, kept time)

Nothing was rotated or revoked for real. Each step was walked to the place in the dashboard where it would be done.

## Detect and decide

Detect item: "A Sentry alert, a Railway log line ... that holds a token". Decided: what data, Plaid access tokens in plain text in Railway logs and possibly Sentry; which businesses, the 2 named in the 14 lines; since when, the 18:00 deploy. Took 6 min.

## First hour timings

Numbered as `incident-response.md` stood when rehearsed.

Step 1: 2 min - Railway rollback of `api` found
Step 2: 2 min - Plaid dashboard walked; no operator command in the code (see below)
Step 3: 2 min - `TOKEN_ENCRYPTION_KEYS` on `api` found
Step 4: 2 min - Clerk secret key roll and session revoke found
Step 5: 2 min - Resend key create and delete found
Step 6: 2 min - Railway `Postgres` password rotation found
Step 7: 2 min - Railway logs filter by text and time window and can be copied; they go back 24 hours
Step 8: 2 min - affected businesses read from the access-log paths

Notify: walked; the client notice was filled in (below).

## What the plan got wrong

1. Detect: our logger and Sentry's `before_send` redact Plaid tokens (`app/log.py`, `app/monitoring.py`), so a leak like this one bypassed them (for example a `print()`), and Sentry may show `[REDACTED]`. The plan did not say to read the raw Railway logs.
2. Step 7 came too late: Railway keeps logs for 24 hours on the current plan. Copying them has to happen right after the leak is stopped.
3. Step 2: there is no operator command to call `/item/remove` for a business. The only code path is `disconnect_bank`, which deletes the bank's accounts and transactions and makes the client reconnect, and only an owner can trigger it from the app. The plan did not say so. Whether the Plaid dashboard can remove one item by hand was not confirmed.
4. Step 3: the code never re-encrypts stored tokens, so "keep the old key until every token is re-encrypted" can never complete. Rotating the key also protects nothing when the leak is of plain tokens, not of the key or the stored ciphertext.
5. Steps 3, 4 and 5 said "update `api` and `jobs`". `jobs` reads `api`'s secrets by reference (`.railway/railway.ts`); only `api` (and `web` for Clerk, which holds its own copy) is updated, then `jobs` redeployed.
6. Step 6: `DATABASE_URL` is built from `${{Postgres.PGPASSWORD}}`, so there is nothing to update after rotating; only redeploy.
7. Step 8: the audit log records only bank connection created and disconnected and account updated, not repairs or reads. The business IDs come from the `uvicorn.access` lines' paths.
8. Notify and Decide rely on "the lawyer", who is not named anywhere in the plan.
9. The drafted client notice first said "we deleted the log entries"; Railway was not checked for deleting log lines, so the notice must not promise it.

## Client notice as drafted

> We are writing to tell you that on October 15 a change we made to Headroom wrote the key we use to read your bank data into our internal system logs, which only our team can see, for 8 hours.
>
> The data involved was that key. It did not include your bank login, your account numbers or your transactions.
>
> Here is what we did: we removed the change and cancelled the key with Plaid so it can no longer be used.
>
> Here is what we suggest you do: reconnect your bank in Headroom (Settings, then Bank connections). Nothing else is needed.

## Follow-ups

- An operator command that revokes one business's Plaid items without the owner (finding 3) is not covered by any spec; it needs one before production data arrives.
- Name the lawyer and their number in `incident-response.md` (finding 8).
