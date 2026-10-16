# If customer data is exposed

Last rehearsed: 2026-10-16 (record: `rehearsal-2026-10-16.md`)

Read this top to bottom. It is written to be followed at 02:00 by one person. "Exposed" means any
of: a Plaid access token, a Clerk session token, a bank balance, a transaction or an email address
reached someone who should not have it, or we cannot rule that out.

## Detect

Exposure usually shows up as one of these. Any one of them starts this plan.

- A Sentry alert, a Railway log line or a PostHog event that holds a token, an account number or a
  transaction description.
- A client or bookkeeper writes that they see another business's data.
- Plaid, Clerk, Resend or Railway emails us about a leaked key or unusual access.
- A secret appears in a commit, a pull request, a screenshot or a chat message.
- Someone loses a laptop or a phone that is signed in to Railway, GitHub, Clerk or Plaid.

Our logger and Sentry redact Plaid tokens and bearer tokens, so a leak usually means something
wrote around them (a `print()`, a new library). Sentry may show `[REDACTED]`: read the raw Railway
logs before deciding nothing leaked.

## Decide

The founder decides, and writes the time and the decision in the incident log (a new file
`context/security/incident-<YYYY-MM-DD>.md`). If the founder cannot be reached within 30 minutes,
whoever found it takes the First hour steps without waiting; stopping the exposure is never
blocked on a decision. The lawyer confirms the notice duties before any message leaves.

Lawyer: TODO(question): name and phone number, agreed before the first client's data arrives.

Decide three things and write them down: what data, which businesses, and since when.

## First hour

Do these in order. Write the time each step finished in the incident log.

1. Stop the leak. If it is a log line or a page, remove the deploy that writes it (Railway: roll
   back `api` or `web` to the last good deployment). If it is a public file, take it down. Then copy
   the Railway logs for the window into a local file at once: Railway keeps only 24 hours.
2. Revoke Plaid access tokens: call `/item/remove` for every connection of the affected
   businesses. Plaid access tokens are the most sensitive thing we hold. There is no operator
   command for this yet: the only path in the code is the owner's Disconnect
   (`disconnect_bank`), which also deletes that bank's accounts and transactions, so the client
   has to reconnect. Say so in the client notice.
3. Rotate `TOKEN_ENCRYPTION_KEYS` only if the key or the stored encrypted tokens leaked (for plain
   tokens, step 2 is the fix): add a new Fernet key first in the list on `api` and redeploy `api`
   and `jobs`. Stored tokens are not re-encrypted, so the old key stays until every connection
   encrypted with it has been revoked and reconnected.
4. Rotate `CLERK_SECRET_KEY` in the Clerk dashboard, update it on `api` and `web` (`jobs` reads
   `api`'s by reference), and redeploy all three.
   Revoke all sessions in Clerk if a session token was exposed.
5. Rotate `RESEND_API_KEY` in Resend, update it on `api` (`jobs` reads it by reference), and
   redeploy both.
6. Rotate the Railway database password for `Postgres`; `DATABASE_URL` is built from it, so
   only redeploy `api` and `jobs`. Check that `Postgres` still has no public domain or TCP proxy.
7. Preserve the evidence: save the Sentry events and the Railway logs copied in step 1, with
   times, next to the incident log. Do not paste secrets into it.
8. Count who is affected: filter the Railway logs by the route and the window and read the
   business IDs from the `uvicorn.access` paths; the audit log records only bank connections
   created and disconnected and account changes, not reads. If you cannot be sure, treat every
   business as affected.

## Notify

Order matters. Nobody learns of it from someone else.

1. Affected clients, as soon as step 8 gives a list and the lawyer has confirmed the wording:
   every owner of an affected business, by email from the founder, then by phone for any client
   with a bookkeeper.
2. Their bookkeepers, with the same text.
3. The Office of the Privacy Commissioner of Canada, when the lawyer confirms there is a real risk
   of significant harm. The lawyer sets the deadline; ask on day one.
4. Plaid, Clerk and Resend, if their keys or data were involved.
5. Everyone else who asks, using the same text.

## Client notice

Send this, filled in, from the founder's own address. Keep it plain and short.

> Subject: A security incident at Headroom that affects your data
>
> We are writing to tell you that <what happened>.
>
> The data involved was <what data>. It did not include <what was not involved>.
>
> Here is what we did: <what we did>.
>
> Here is what we suggest you do: <what you should do>.
>
> We are sorry. You can reach me directly at <phone and email>, and I will answer within the hour.
