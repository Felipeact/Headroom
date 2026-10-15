# If customer data is exposed

Last rehearsed: not yet

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

## Decide

The founder decides, and writes the time and the decision in the incident log (a new file
`context/security/incident-<YYYY-MM-DD>.md`). If the founder cannot be reached within 30 minutes,
whoever found it takes the First hour steps without waiting; stopping the exposure is never
blocked on a decision. The lawyer confirms the notice duties before any message leaves.

Decide three things and write them down: what data, which businesses, and since when.

## First hour

Do these in order. Write the time each step finished in the incident log.

1. Stop the leak. If it is a log line or a page, remove the deploy that writes it (Railway: roll
   back `api` or `web` to the last good deployment). If it is a public file, take it down.
2. Revoke Plaid access tokens: in the Plaid dashboard remove the affected items, or call
   `/item/remove` for every connection of the affected businesses. Plaid access tokens are the
   most sensitive thing we hold.
3. Rotate `TOKEN_ENCRYPTION_KEYS`: add a new Fernet key first in the list on `api` and `jobs`,
   redeploy, and keep the old key until every token is re-encrypted or revoked.
4. Rotate `CLERK_SECRET_KEY` in the Clerk dashboard, update `api`, `jobs` and `web`, and redeploy.
   Revoke all sessions in Clerk if a session token was exposed.
5. Rotate `RESEND_API_KEY` in Resend, update `api` and `jobs`, and redeploy.
6. Rotate the Railway database password for `Postgres`, update the `DATABASE_URL` reference, and
   redeploy `api` and `jobs`. Check that `Postgres` still has no public domain or TCP proxy.
7. Preserve the evidence: save the Railway and Sentry logs for the window, with times, in the
   incident log. Do not paste secrets into it.
8. Count who is affected: list the businesses and the kind of data from the audit log and the
   logs. If you cannot be sure, treat every business as affected.

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
