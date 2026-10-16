# 31 - Bookkeeper invitations verification

**Verdict**: PASS
**Profile**: light
**Diff range**: e8189be^..HEAD (7c34c42)
**Round**: 4 - scoped (rounds 1-3 kept below; C29 superseded by Round 4)
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
| C20 | every business route classified | `-k every_business_route_is_classified` passed | `test_bookkeeper_access.py:92` `assert found == OWNER_ONLY, SHARED or BOOKKEEPER_ONLY (set union)` (the file has three literal sets, not two as the check says; the third holds only `PUT /me/alert-emails`) | PASS |
| C21 | strangers get 404 | `-k strangers_get_404` passed | `test_bookkeeper_access.py:225` `== 404` for the four routes and both caller types (`:208-218`); `:226` detail "Business not found." | PASS |
| C22 | toggle alert emails | `-k toggle_alert_emails` passed | `tests/test_bookkeeper_alert_emails.py:60-61` 200 and true; `:68` false; `:70-75` owner 403 and `:74` missing body `== 422` | PASS |
| C23 | opted-in bookkeeper gets alert | `-k opted_in_bookkeeper_gets_alert` passed | `test_bookkeeper_alert_emails.py:89` `len(rows) == 2`; `:90` quiet absent; `:94` reason; `:97-99` sends | PASS |
| C24 | preferences off skipped; replay once | `-k preferences_and_replay` passed | `test_bookkeeper_alert_emails.py:115` `len(rows) == 2` after replay; `:117` `skipped.state == "skipped"`; `:118` `len(sent) == 1` | PASS |
| C25 | digest owners only | `-k digest_owners_only` passed | `test_bookkeeper_alert_emails.py:129` `recipients == {biz.owner_id, second}`; `:130` opted bookkeeper absent | PASS |
| C26 | invitation email renders | `-k renders_invitation` passed | `tests/test_invitation_email.py:30` subject; `:32` `re.findall(href) == [link]`; `:33` text links; `:38-39` reason; `:41` no "unsubscribe"; `:43` `dict(email.headers) == {}` | PASS |
| C27 | Members screen states, confirm, bookkeeper view | `npx vitest run members-section` - 7 passed | `frontend/tests/members-section.test.tsx:48` loading status; `:54` empty text; `:62` error `rejects.toThrow`; `:78-80` rows; `:90` confirm before remove; `:70` bookkeeper redirected to `/settings/email` with `loadMembers` not called; `frontend/tests/settings-nav.test.tsx:69` bookkeeper nav is `['/settings/email', '/settings/data']` (this file is outside the check's proof command) | PASS |
| C28 | invite screen messages | `npx vitest run invite-page` - 10 passed in 7 of 8 runs | `frontend/tests/invite-page.test.tsx:63-72` expired, wrongAddress, alreadyOwner, notFound titles; `:98` used link; ready at `:41`. One failure seen, see Findings | PASS |
| C29 | Playwright on /settings/members and /invite/{token} | not run | `frontend/e2e/members.spec.ts` and `e2e/invite.spec.ts` exist, but `curl localhost:3000` and `localhost:8000` get no connection, and the specs create real Clerk users (`createOnboardingUser`). GATED: needs the running app, API and Clerk keys | FAIL (gated) in round 1, superseded: PASS in round 4 |

## Findings

1. C29 is gated and unproven here (no running app or Clerk).
2. Flaky test, `frontend/tests/invite-page.test.tsx:85`: "a failed accept can be tried again" failed once in 8 runs. After `setOutcome("failed")` the alert appears while the transition is still pending, so the button is briefly named "Accepting..." and `getByRole('button', { name: 'Accept invitation' })` misses it. It needs a `waitFor` around the button assertion.
3. C20 wording: `checks.md` says two literal sets, the test has three (adds `BOOKKEEPER_ONLY`). Harmless.
4. C27 wording: the bookkeeper nav assertion lives in `settings-nav.test.tsx`, which the check's proof command (`members-section` filter) does not run.

## Gate

`uv run pytest tests/test_invitations.py tests/test_bookkeeper_access.py tests/test_bookkeeper_alert_emails.py tests/test_invitation_email.py tests/test_run_due.py -v` - 40 passed, 0 failed; `npx vitest run members-section invite-page` - 17 passed (one earlier run: 1 failed); `tests/settings-nav.test.tsx` - 5 passed.

## Round 2 - scoped

Verified at 88ab052. Scope: C29 (the only row that was not PASS) and the flaky `invite-page` test. The other 28 checks are carried from round 1 (verified at 7c34c42).

Environment: local Postgres on 127.0.0.1:58513 was already up; `uv run --no-sync alembic upgrade head` ran clean. A `next dev --webpack` already served localhost:3000 (I could not confirm its API_URL: my attempt to start a second one was refused because the port was in use, and I did not kill the existing process). Playwright started the API on 8100 itself (`webServer` in `frontend/playwright.config.ts`) with `EMAIL_SENDER=console`.

Flaky-fix proof: `npx vitest run invite-page` from `frontend`, 5 runs, each `Tests 10 passed (10)`. The fix is the `waitFor` at `frontend/tests/invite-page.test.tsx:85`: `await waitFor(() => expect(screen.getByRole('button', { name: 'Accept invitation' })).toBeTruthy())`. Five greens is consistent with the fix; it cannot prove a rare flake gone.

C29 proof: `EMAIL_SENDER=console npx playwright test members.spec.ts invite.spec.ts --reporter=line --timeout=90000` from `frontend`, run three times:

| Run | Result | Failed tests |
| --- | --- | --- |
| 1 | 7 passed, 5 failed | `invite.spec.ts:36, :52, :62, :70, :76` |
| 2 | 10 passed, 2 failed | `invite.spec.ts:36, :70` |
| 3 | 11 passed, 1 failed | `members.spec.ts:31` |

Every test passed in at least one run, but no single run was 12 of 12 (the author reports one run of 12 passed; I did not reproduce it). Every failure is the same: "Test timeout of 90000ms exceeded while running beforeEach hook", stuck at `frontend/e2e/onboarding-steps.ts:7` (`getByRole('option', { name: 'Ontario' }).click()`, the province select on step 2 of onboarding, a helper from an earlier spec). The failing step is in the shared sign-in and onboarding set-up, not in the members or invite screens. That is consistent with dev-mode cold compile and hydration, but I did not prove the cause.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C29 | Playwright on `/settings/members` and `/invite/{token}`: states, 375 px, keyboard, touch targets, axe | the three runs above | `frontend/e2e/members.spec.ts` and `frontend/e2e/invite.spec.ts` (12 tests); runs 1-3 each had 1 to 5 failures at `frontend/e2e/onboarding-steps.ts:7`; no run was fully green | FAIL (flaky set-up) in round 2, superseded: PASS in round 4 |

The verdict stays FAIL on C29 alone. One clean 12 of 12 run, ideally against a freshly started webpack dev server or a production build, clears it. A likely fix is to wait for the combobox to be hydrated before clicking in `completeBusinessStep`; that file is outside this spec.

## Gate (round 2)

`npx vitest run invite-page` x5 - 10 passed each; `npx playwright test members.spec.ts invite.spec.ts` x3 - 7, 10 and 11 of 12 passed.

## Round 3 - scoped

Verified at 88ab052 plus the author's uncommitted changes. Scope: C29 only; the other 28 checks are carried from round 1 and round 2. Environment: production build `next start` on localhost:3000 (`curl /sign-in` returned 200, not touched by me), Postgres 127.0.0.1:58513 reachable, API started by Playwright on 8100.

Proof run: `DATABASE_URL=postgresql+psycopg://headroom:localdev@127.0.0.1:58513/headroom EMAIL_SENDER=console npx playwright test members.spec.ts invite.spec.ts --reporter=line --timeout=90000` from `frontend`.

| Run | Result | Failed tests |
| --- | --- | --- |
| 1 | 12 passed (22.6s) | none |
| 2 | 11 passed, 1 failed | `members.spec.ts:53` phone width, keyboard and axe |
| 3 (extra, whole suite) | 11 passed, 1 failed | `members.spec.ts:53` (same) |
| 4 (extra, members.spec.ts alone) | 5 passed, 1 failed | `members.spec.ts:53` (same) |

The dev-mode onboarding flake at `frontend/e2e/onboarding-steps.ts:7` did not recur: the production build fixed it. A different failure now appears in 3 of 4 runs: `members.spec.ts:72-73` (`const axe = await new AxeBuilder({ page }).analyze(); expect(axe.violations).toEqual([])`) reports one `color-contrast` violation (serious): the sonner toast text "Invitation sent to pat@example.test" (`.cn-toast`), foreground #b1b3b4 on #f8f7f3, ratio 1.96, expected 4.5. The scan runs straight after `members.spec.ts:70` (`toBeVisible()` of the toast text), while the toast is still fading in, so the measured colour is partly transparent. Whether this is only a timing flake of the test or a real low-contrast toast was not proven; the settled toast colour was not measured.

Located assertions (all 12 tests exist and each passed in run 1): `members.spec.ts:33,35,40-42` (members heading, one member row, invitation toast, one pending invitation, empty state gone), `:57-71` (375 px overflow `<= 0`, send button and rows height `>= 44`, keyboard Tab then Enter), `:72-73` (axe, no violations); `invite.spec.ts:48-49` (accept gives the Email preferences link, no Members link), `:67` (expired link has no Accept button), `:81-87` (phone width, axe).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C29 | Playwright on `/settings/members` and `/invite/{token}`: states, 375 px, keyboard, touch targets, axe | runs 1-4 above | run 1 12 of 12; runs 2-4 each failed `frontend/e2e/members.spec.ts:73` on `color-contrast` of the toast (1.96) | FAIL (axe toast timing) in round 3, superseded: PASS in round 4 |

The verdict stays FAIL on C29 alone; the criterion needs two clean runs and only one was clean. Likely fixes, both outside what I may edit: wait for the toast animation to finish before the axe scan (or scan a region that excludes `.cn-toast`), or, if the settled toast is also under 4.5:1, fix its colour (design files need approval). Check the settled colour first.

## Gate (round 3)

`npx playwright test members.spec.ts invite.spec.ts` x2 as required: 12 passed, then 11 passed with 1 failed. Two extra runs reproduced that one failure.

## Round 4 - scoped

Scope: C29 only; the other 28 checks are carried from rounds 1-2. Servers untouched: production build on localhost:3000 (`/sign-in` 200), Postgres 127.0.0.1:58513. The author changed `frontend/e2e/members.spec.ts` (test code only) to wait for the toast before axe.

Proof run: `DATABASE_URL=postgresql+psycopg://headroom:localdev@127.0.0.1:58513/headroom EMAIL_SENDER=console npx playwright test members.spec.ts invite.spec.ts --reporter=line --timeout=90000` from `frontend`, twice.

| Run | Result |
| --- | --- |
| 1 | 12 passed (34.1s) |
| 2 | 12 passed (23.5s) |

Located assertions: `members.spec.ts:72-73` wait for `[data-sonner-toast]` `toHaveCSS('opacity', '1')`, then `:75-76` `AxeBuilder(...).analyze()` and `expect(axe.violations).toEqual([])`; `:33,35,40-42` (members heading, member row, invitation toast, pending invitation, empty state gone); 375 px overflow, 44 px targets and keyboard at `:53-71`; `invite.spec.ts:48-49` (Email preferences link, no Members link), `:67` (expired link, no Accept), `:81-87` (phone width, axe).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C29 | Playwright on `/settings/members` and `/invite/{token}`: states, 375 px, keyboard, touch targets, axe | runs 1-2 above | 12 of 12 twice, axe clean on the settled toast (`members.spec.ts:73-76`) | PASS |

Note: the round 3 contrast failure was a scan-timing issue in the test (toast mid fade-in), not a product defect; the settled toast passes axe.

## Gate (round 4)

`npx playwright test members.spec.ts invite.spec.ts` x2 - 12 passed, 12 passed. C1-C28 carried PASS.
