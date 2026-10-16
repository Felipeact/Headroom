# Spec 31: Bookkeeper invitations checks

Profile: light
Plan: `.specs/features/31-accounts-bookkeeper-invitations/plan.md`

29 checks in 4 slices · 6 one-way doors · 0 open

Unless noted, `uv run` proofs run from `services/core`. API tests use the real local Postgres from `tests/conftest.py` (`migrated_database`) and signed test tokens (`tests/tokens.py`), plus spec 28's `mail` fixture (`FakeEmailSender`, `FakeClerkUsers`), so no test calls Resend or Clerk. Each caller is registered in the fake Clerk with a primary address. "Expired" means the test sets `invitations.expires_at` one second in the past with SQL. New tests live in `tests/test_invitations.py` (S1), `tests/test_bookkeeper_access.py` (S2), `tests/test_bookkeeper_alert_emails.py` (S3) and `tests/test_invitation_email.py` (the template, no database). Web proofs run from `frontend`.

## Checks

### S1 - Invite, accept, remove · 9 files · 90 KB · ~25k

**C1** - `POST /v1/businesses/{id}/invitations` as the owner with `Pat@Example.test` (spaces around it) answers `201` with `id` and `expires_at` exactly 7 days after the row's `created_at`. `FakeEmailSender` holds 1 email to `pat@example.test` whose text holds `https://app.example.test/invite/{token}`, and the log holds one `audit_log` entry `invitation.created` (AC 1, doors 1, 3, 4, 5)
Proof: `uv run pytest tests/test_invitations.py -k "invite_stores_emails_and_audits"`

**C2** - After C1, the `invitations` row holds `token_hash` equal to the SHA-256 hex of the token in the email and `email_hash` equal to the SHA-256 hex of `pat@example.test`. No column of `invitations`, and no `audit_log.details`, contains `pat@example.test` or the token. The captured logs hold neither (AC 5, doors 1, 2)
Proof: `uv run pytest tests/test_invitations.py -k "stores_only_hashes"`

**C3** - Inviting an address that already has a pending invitation (`pat@EXAMPLE.test`), and inviting the address of a current member, each answer `409`, add no row and send no email (AC 2)
Proof: `uv run pytest tests/test_invitations.py -k "duplicate_invite_conflicts"`

**C4** - When `FakeEmailSender` raises a retryable `SendError`, the invite answers `503` and `invitations` holds 0 rows for the business and `audit_log` 0 `invitation.created` entries (AC 3, door 4)
Proof: `uv run pytest tests/test_invitations.py -k "send_failure_stores_nothing"`

**C5** - `not-an-email`, an empty string and 255 characters of `a` plus `@example.test` each answer `422` (AC 4)
Proof: `uv run pytest tests/test_invitations.py -k "invalid_address_is_422"`

**C6** - A signed-in user whose primary Clerk address is `pat@example.test` accepting gets `200` with the business and `role` `bookkeeper`. The membership exists with `receive_alert_emails` false, `accepted_at` and `accepted_by_user_id` are set, and `audit_log` holds `invitation.accepted` (AC 6, doors 2, 3, 5, 6)
Proof: `uv run pytest tests/test_invitations.py -k "accept_adds_bookkeeper"`

**C7** - Accepting with `expires_at` one second in the past answers `410` and adds no membership. With `expires_at` one minute ahead it answers `200`. `GET /v1/invitations/{token}` reports `status` `expired` for the first (AC 7, door 1)
Proof: `uv run pytest tests/test_invitations.py -k "expired_invitation_cannot_be_accepted"`

**C8** - A user whose primary address is `lee@example.test` accepting gets `403` and no membership. A user with no primary address gets `403` (AC 8, door 2)
Proof: `uv run pytest tests/test_invitations.py -k "wrong_address_is_403"`

**C9** - The invited user accepting twice gets `200` both times and has one membership and one `invitation.accepted` entry (AC 9)
Proof: `uv run pytest tests/test_invitations.py -k "accept_twice_is_idempotent"`

**C10** - After C6, a different user (any address) accepting the same token gets `403` and no membership (AC 10)
Proof: `uv run pytest tests/test_invitations.py -k "used_invitation_other_user_403"`

**C11** - An unknown token answers `404` on `GET /v1/invitations/{token}` and on `POST .../accept` (AC 11)
Proof: `uv run pytest tests/test_invitations.py -k "unknown_token_is_404"`

**C12** - The owner of the business accepting an invitation to it (their own address) gets `409` and the membership stays `owner` (AC 12)
Proof: `uv run pytest tests/test_invitations.py -k "owner_cannot_accept_own_invitation"`

**C13** - `DELETE /v1/businesses/{id}/members/{user_id}` as the owner for a bookkeeper answers `204`, deletes the membership and writes `member.removed`. The removed user's `GET /v1/businesses/{id}/dashboard` then answers `404` (AC 13, door 5)
Proof: `uv run pytest tests/test_invitations.py -k "remove_bookkeeper"`

**C14** - Removing an owner (the caller) answers `409` and keeps the membership. Removing a user who is not a member answers `404` (AC 14, 15)
Proof: `uv run pytest tests/test_invitations.py -k "remove_owner_conflicts_and_stranger_404"`

**C15** - `GET /v1/businesses/{id}/members` as the owner lists 1 owner and 1 bookkeeper with `name` and `email` from the fake Clerk, plus the pending invitations with `id`, `created_at` and `expires_at` only. With Clerk unavailable it still answers `200` with the roles and `name` and `email` null (Assumption 1)
Proof: `uv run pytest tests/test_invitations.py -k "members_list_with_and_without_clerk"`

**C16** - Migration: after `alembic upgrade head`, `invitations` exists with a unique `token_hash` and the partial unique index on `(business_id, email_hash)`. `memberships.role` accepts `bookkeeper` and rejects `viewer`. `memberships.receive_alert_emails` defaults to false (doors 3, 6)
Proof: `uv run pytest tests/test_invitations.py -k "schema_constraints"`

### S2 - Bookkeeper permissions · 5 files · 60 KB · ~15k

**C17** - A bookkeeper gets `200` from each of `GET .../dashboard`, `.../forecast`, `.../forecast/status`, `.../upcoming`, `.../alerts`, `.../alerts/{alert_id}`, `.../expected-payments`, `.../recurring-patterns`, `.../minimum-balance`, `.../members` and `GET /v1/businesses/{id}` (AC 16)
Proof: `uv run pytest tests/test_bookkeeper_access.py -k "bookkeeper_can_read"`

**C18** - A bookkeeper can `POST` an expected payment (`201`), `PUT` it (`200`) and `DELETE` it (`204`), and each writes the same `expected_payment.*` audit entry as for an owner, with the bookkeeper as actor (AC 16)
Proof: `uv run pytest tests/test_bookkeeper_access.py -k "bookkeeper_manages_expected_payments"`

**C19** - A bookkeeper gets `403` from `PATCH /businesses/{id}`, `PUT .../minimum-balance`, `POST .../alerts/{id}/dismiss`, `POST .../bank/link-token`, `POST .../bank/connections`, `GET .../bank/connections`, `GET .../bank/transactions`, `PATCH .../bank/accounts/{id}`, the connection `link-token`, `repair` and `DELETE` routes, `POST .../invitations` and `DELETE .../members/{user_id}`. Every one is called, none changes data (AC 17)
Proof: `uv run pytest tests/test_bookkeeper_access.py -k "bookkeeper_gets_403_from_owner_routes"`

**C20** - The test builds the list of every `APIRoute` whose path starts with `/v1/businesses/{business_id}` from `app`, and fails unless each (method, path) is in exactly one of two literal sets in the test file: owner-only or shared. The sets together hold every route (AC 17)
Proof: `uv run pytest tests/test_bookkeeper_access.py -k "every_business_route_is_classified"`

**C21** - A signed-in user who is not a member of the business gets `404` from each new business route (`POST .../invitations`, `GET .../members`, `DELETE .../members/{user_id}`, `PUT .../me/alert-emails`) and a bookkeeper of business A gets `404` from the same routes for business B (AC 18)
Proof: `uv run pytest tests/test_bookkeeper_access.py -k "strangers_get_404"`

### S3 - Alert emails for bookkeepers · 4 files · 30 KB · ~8k

**C22** - A bookkeeper `PUT .../me/alert-emails` with `{"enabled": true}` answers `200` with `receive_alert_emails` true, and `false` turns it off. An owner gets `403`. A body without `enabled` answers `422` (AC 20, 21)
Proof: `uv run pytest tests/test_bookkeeper_alert_emails.py -k "toggle_alert_emails"`

**C23** - With the sample alert (Harbor Street seed 0) and two bookkeepers, one opted in, publishing `alert.created` sends to the owner and to the opted-in bookkeeper, 2 emails, and 0 to the other. The reason line for the bookkeeper reads "You're getting this email because you're a bookkeeper for Harbor Street Plumbing on Headroom." (AC 20)
Proof: `uv run pytest tests/test_bookkeeper_alert_emails.py -k "opted_in_bookkeeper_gets_alert"`

**C24** - A bookkeeper who is opted in but turned alert emails off in `/me/email-preferences` gets a `skipped` delivery, and handling the same event twice leaves one delivery per recipient (AC 20)
Proof: `uv run pytest tests/test_bookkeeper_alert_emails.py -k "preferences_and_replay"`

**C25** - `weekly_digest` for the same business with an opted-in bookkeeper records deliveries for the owner only (AC 22)
Proof: `uv run pytest tests/test_bookkeeper_alert_emails.py -k "digest_owners_only"`

### S4 - Email and screens · 11 files · 120 KB · ~30k

**C26** - The `invitation` email renders without a database: the subject reads "{inviter} invited you to {business} on Headroom"; the HTML and text hold one link, exactly `https://app.example.test/invite/{token}`, with no query string; the footer reason is "You're getting this email because {inviter} invited you to {business} on Headroom."; it holds no unsubscribe link and carries no `List-Unsubscribe` header (AC 1, door 4)
Proof: `uv run pytest tests/test_invitation_email.py -k "renders_invitation"`

**C27** - The Members screen (Vitest, Testing Library) renders the loading state, the empty state ("no bookkeepers yet" text from `messages/en.json`), the error state, one row per member and pending invitation, and asks for confirmation before removing. A bookkeeper sees none of the invite form, the remove buttons or the owner-only settings navigation items (AC 19, 23)
Proof: `npm test -- members-section -t "members section"`

**C28** - The `/invite/[token]` screen renders, from `messages/en.json`, distinct messages for ready, expired, wrong address, already accepted and unknown (AC 24)
Proof: `npm test -- invite-page -t "invite page"`

**C29** - Playwright against the running app (seeded fixtures, fake auth as in the existing settings tests) on `/settings/members` and `/invite/{token}`: loading, empty and error states, 375 px width without horizontal scroll, keyboard-only use, touch targets of at least 44 px, and no axe violations (AC 25)
Proof: `npx playwright test members.spec.ts invite.spec.ts -g "members and invite"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST /v1/businesses/{business_id}/invitations` statuses (6) | 201 C1 · 403 C19 · 404 C21 · 409 C3 · 422 C5 · 503 C4 | - |
| `GET /v1/businesses/{business_id}/members` statuses (2) | 200 C15 · 404 C21 | - |
| `DELETE /v1/businesses/{business_id}/members/{user_id}` statuses (4) | 204 C13 · 403 C19 · 404 C14 · 409 C14 | - |
| `GET /v1/invitations/{token}` statuses (2) | 200 C7 · 404 C11 | - |
| `POST /v1/invitations/{token}/accept` statuses (5) | 200 C6 · 403 C8 · 404 C11 · 409 C12 · 410 C7 | - |
| `PUT /v1/businesses/{business_id}/me/alert-emails` statuses (4) | 200 C22 · 403 C22 · 404 C21 · 422 C22 | - |
| Landing doors (6) | 1 token C1 · 2 address binding C2 · 3 table C16 · 4 invitation email C26 · 5 audit actions C13 · 6 role value C16 | - |
| Relations entities (3) | Business C16 · Invitation C16 · Membership C6 | - |
| audit actions (3) | `invitation.created` C1 · `invitation.accepted` C6 · `member.removed` C13 | - |
| accept outcomes (6) | valid C6 · expired C7 · wrong address C8 · same user twice C9 · other user C10 · owner C12 | - |
| owner-only route families (5) | business `PATCH` and minimum balance C19 · alert dismiss C19 · bank C19 · members and invitations C19 · every route classified C20 | - |
| bookkeeper-readable routes (11) | dashboard C17 · forecast C17 · forecast/status C17 · upcoming C17 · alerts C17 · alert C17 · expected-payments C17 · recurring-patterns C17 · minimum-balance C17 · members C17 · business C17 | - |
| Members screen states (4) | loading C27 · empty C27 · error C27 · bookkeeper view C27 | - |
| `/invite/[token]` messages (5) | ready C28 · expired C28 · wrong address C28 · already accepted C28 · unknown C28 | - |
| startup config: `bookkeeper` role admitted by the API (1 assembly) | the app in `app.main` C17 | - |

- Claims naming a status code, route or response shape: C1, C3 to C15, C17 to C19, C21, C22 - each has a proof that calls the route through the test client
- No other check claims more than the single case its proof exercises

## Swept

- validation: C5, C22 (address format, missing `enabled`)
- failure modes: C4 (send fails, nothing stored), C15 (Clerk down)
- idempotency: C9 (accept twice), C24 (event handled twice)
- authorization: C17, C18, C19, C20, C21
- concurrency: n/a - two accepts at once end on the primary key `(business_id, user_id)` and the partial unique index of C16; the second gets `409` or `403` by the same checks as C10
- data lifecycle: C7 (7-day expiry), C13 (removal), C16 (invitation rows are kept after accepting)
- dependency failure: C4 (Resend), C15 (Clerk)
- state transitions: C6 to C10, C12 (pending, accepted, expired)
- observability: C2 (no address or token in logs), C1 and C6 and C13 (audit entries)

## Out of scope

Same as plan.md: revoking an invitation, naming the invitee in the pending list, background retry of the invitation email, role changes, bookkeeper digests.

## Handoff

Size, from `wc -c` on the files each slice touches, divided by four, budget 150k:

- S1 = 25k (accounts 20 KB, auth, audit, notifications service and templates, tests support, one migration), S2 = 15k (three `api.py` files, tests), S3 = 8k (notifications service, accounts service) - 48k in the backend
- S4 = 30k (email templates, settings pages, `messages/en.json`, generated API types, Playwright tests) - 78k in total, under the 150k budget - one builder
- Environment: this PC has no Postgres or Docker, so the proofs C1 to C25 that use the database are written but cannot run here (the same as spec 30). C26 to C29 and the lint, type and build checks can run

- Mechanism: one builder
