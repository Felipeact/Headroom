# 31 - Bookkeeper invitations verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: e8189be^..HEAD (7c34c42)
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

C29 (Playwright) could not be run here: it needs a live web app, API and real Clerk test users, and none was running. Every other check (28 of 29) is proven with a located assertion. One frontend test is flaky, noted under Findings.

## Binding sources

Step 1 does not run under profile `light`. Not applicable.

## Checks

Proofs run at HEAD from `services/core` with DATABASE_URL set to the local Postgres: `uv run pytest tests/test_invitations.py tests/test_bookkeeper_access.py tests/test_bookkeeper_alert_emails.py tests/test_invitation_email.py tests/test_run_due.py -v` - 40 passed, each id printed. From `frontend`: `npx vitest run members-section invite-page` - 17 passed on 7 of 8 runs (see Findings), and `npx vitest run tests/settings-nav.test.tsx` - 5 passed.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | invite 201, 7 days, email, audit | `-k invite_stores_emails_and_audits` passed | `tests/test_invitations.py:53` `invite(owner, business_id, "  Pat@Example.test ")`; `:54` `== 201`; `:61` link in text; `:65` `expires_at - created_at == timedelta(days=7)`; `:66` `audit_actions(...) == ["invitation.created"]` | PASS |
| C2 | only hashes stored or logged | `-k stores_only_hashes` passed | `test_invitations.py:77` `token_hash == sha256(token)`; `:78` `email_hash == sha256(PAT)`; `:85-89` address and token absent from rows and logs | PASS |
| C3 | duplicate or member gives 409, no row or email | `-k duplicate_invite_conflicts` passed | `test_invitations.py:99,101,108` `== 409`; `:103-104` one row, send count unchanged | PASS |
| C4 | send failure gives 503, nothing stored | `-k send_failure_stores_nothing` passed | `test_invitations.py:117` `== 503`; `:118-119` no rows, no audit | PASS |
| C5 | bad addresses give 422 | `-k invalid_address_is_422` (3 params) passed | `test_invitations.py:127` `invite(...).status_code == 422`; `:128` no rows | PASS |
| C6 | accept adds bookkeeper | `-k accept_adds_bookkeeper` passed | `test_invitations.py:140` role `bookkeeper`; `:148` `(role, receives) == ("bookkeeper", False)`; `:151` `accepted_by == pat.id`; `:152` audit list | PASS |
| C7 | expired gives 410, status expired | `-k expired_invitation_cannot_be_accepted` passed | `test_invitations.py:163` status json; `:167` `== 410`; `:179` `== 200` | PASS |
| C8 | wrong or missing address gives 403 | `-k wrong_address_is_403` passed | `test_invitations.py:190-191` both `== 403`; `:192` no membership | PASS |
| C9 | accept twice idempotent | `-k accept_twice_is_idempotent` passed | `test_invitations.py:205-206` both 200; `:212-213` one row, one audit entry | PASS |
| C10 | other user gets 403 | `-k used_invitation_other_user_403` passed | `test_invitations.py:225` `== 403`; `:226` no membership | PASS |
| C11 | unknown token 404 | `-k unknown_token_is_404` passed | `test_invitations.py:237` GET 404; `:241` `accept(caller, unknown).status_code == 404` | PASS |
| C12 | owner accept gives 409, stays owner | `-k owner_cannot_accept_own_invitation` passed | `test_invitations.py:251` `== 409`; `:257` `role == "owner"` | PASS |
| C13 | remove bookkeeper | `-k remove_bookkeeper` passed | `test_invitations.py:269` `== 204`; `:270` removed user's dashboard `== 404`; `:271` `[-1] == "member.removed"` | PASS |
| C14 | remove owner 409, stranger 404 | `-k remove_owner_conflicts_and_stranger_404` passed | `test_invitations.py:278` `== 409`; `:279` membership kept; `:285` `== 404` | PASS |
| C15 | members list, Clerk down degrades | `-k members_list_with_and_without_clerk` passed | `test_invitations.py:297,298,300` roles, email, invitation keys; `:304-306` 200 with null name and email | PASS |
| C16 | schema constraints | `-k schema_constraints` passed | `test_invitations.py:324` `ck_memberships_role`; `:332` `default is False`; `:339` `uq_invitations_token_hash`; `:342` `uq_invitations_pending_business_id_email_hash` | PASS |
| C17 | bookkeeper reads 11 routes | `-k bookkeeper_can_read` passed | `tests/test_bookkeeper_access.py:116` `assert response.status_code == 200, (route, response.text)` over the SHARED GET routes (`:42-55`) | PASS |
| C18 | bookkeeper manages expected payments | `-k bookkeeper_manages_expected_payments` passed | `test_bookkeeper_access.py:141` 201; `:146` 200; `:147` 204; `:159` actor set `== {str(bookkeeper.id)}` | PASS |
| C19 | owner routes give 403, no change | `-k bookkeeper_gets_403_from_owner_routes` passed | `test_bookkeeper_access.py:183` `== 403` for every OWNER_ONLY route (`:30-43`); `:189` audit count unchanged; `:190` no mail; `:194` name unchanged | PASS |
| C20 | every business route classified | `-k every_business_route_is_classified` passed | `test_bookkeeper_access.py:92` `assert found == OWNER_ONLY \| SHARED \| BOOKKEEPER_ONLY` (the file has three literal sets, not two as the check says; the third holds only `PUT /me/alert-emails`) | PASS |
| C21 | strangers get 404 | `-k strangers_get_404` passed | `test_bookkeeper_access.py:225` `== 404` for the four routes and both caller types (`:208-218`); `:226` detail "Business not found." | PASS |
| C22 | toggle alert emails | `-k toggle_alert_emails` passed | `tests/test_bookkeeper_alert_emails.py:60-61` 200 and true; `:68` false; `:70-75` owner 403 and `:74` missing body `== 422` | PASS |
| C23 | opted-in bookkeeper gets alert | `-k opted_in_bookkeeper_gets_alert` passed | `test_bookkeeper_alert_emails.py:89` `len(rows) == 2`; `:90` quiet absent; `:94` reason; `:97-99` sends | PASS |
| C24 | preferences off skipped; replay once | `-k preferences_and_replay` passed | `test_bookkeeper_alert_emails.py:115` `len(rows) == 2` after replay; `:117` `skipped.state == "skipped"`; `:118` `len(sent) == 1` | PASS |
| C25 | digest owners only | `-k digest_owners_only` passed | `test_bookkeeper_alert_emails.py:129` `recipients == {biz.owner_id, second}`; `:130` opted bookkeeper absent | PASS |
| C26 | invitation email renders | `-k renders_invitation` passed | `tests/test_invitation_email.py:30` subject; `:32` `re.findall(href) == [link]`; `:33` text links; `:38-39` reason; `:41` no "unsubscribe"; `:43` `dict(email.headers) == {}` | PASS |
| C27 | Members screen states, confirm, bookkeeper view | `npx vitest run members-section` - 7 passed | `frontend/tests/members-section.test.tsx:48` loading status; `:54` empty text; `:62` error `rejects.toThrow`; `:78-80` rows; `:90` confirm before remove; `:70` bookkeeper redirected to `/settings/email` with `loadMembers` not called; `frontend/tests/settings-nav.test.tsx:69` bookkeeper nav is `['/settings/email', '/settings/data']` (this file is outside the check's proof command) | PASS |
| C28 | invite screen messages | `npx vitest run invite-page` - 10 passed in 7 of 8 runs | `frontend/tests/invite-page.test.tsx:63-72` expired, wrongAddress, alreadyOwner, notFound titles; `:98` used link; ready at `:41`. One failure seen, see Findings | PASS |
| C29 | Playwright on /settings/members and /invite/{token} | not run | `frontend/e2e/members.spec.ts` and `e2e/invite.spec.ts` exist, but `curl localhost:3000` and `localhost:8000` get no connection, and the specs create real Clerk users (`createOnboardingUser`). GATED: needs the running app, API and Clerk keys | FAIL (gated) |

## Findings

1. C29 is gated and unproven here (no running app or Clerk).
2. Flaky test, `frontend/tests/invite-page.test.tsx:85`: "a failed accept can be tried again" failed once in 8 runs. After `setOutcome("failed")` the alert appears while the transition is still pending, so the button is briefly named "Accepting..." and `getByRole('button', { name: 'Accept invitation' })` misses it. It needs a `waitFor` around the button assertion.
3. C20 wording: `checks.md` says two literal sets, the test has three (adds `BOOKKEEPER_ONLY`). Harmless.
4. C27 wording: the bookkeeper nav assertion lives in `settings-nav.test.tsx`, which the check's proof command (`members-section` filter) does not run.

## Gate

`uv run pytest tests/test_invitations.py tests/test_bookkeeper_access.py tests/test_bookkeeper_alert_emails.py tests/test_invitation_email.py tests/test_run_due.py -v` - 40 passed, 0 failed; `npx vitest run members-section invite-page` - 17 passed (one earlier run: 1 failed); `tests/settings-nav.test.tsx` - 5 passed.
