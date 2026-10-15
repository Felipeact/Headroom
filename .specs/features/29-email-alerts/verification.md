# 29 - Alert emails verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: 24b62e8..900bbc7 (HEAD)
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

25 of 26 checks are proven with located evidence at `900bbc7`. C22 (the manual Resend send to three mail clients) is still not proven: the three screenshots do not exist and the user has not confirmed them. F1 from round 1 is resolved by `900bbc7`. F3 is a precision note and carries over unchanged.

This round's scope is the fix's diff (`git diff --stat 1dca603..900bbc7` shows `services/core/app/modules/notifications/service.py` changed 5 lines and `services/core/tests/test_alert_emails.py` gained 31) and every verdict from round 1 that was not PASS (C22, F1, F2, F3). Every proof was re-run in full at `900bbc7`. Rows the fix could not touch carry their verdict from `1dca603`, with citations refreshed where line numbers moved.

## Binding sources

Carried from 1dca603. Step 1 does not run under profile `light`, and the fix did not touch the interface. The plan marks `design/mockups/email-alert.dc.html` as binding. It was not compared against the checks. Checking how the email renders in real mail clients is C22's job, and C22 is unproven.

## Checks

Verified at 900bbc7. Proof run (from `services/core`): `uv run pytest tests/test_alert_emails.py tests/test_alert_email_template.py tests/test_email_delivery.py tests/test_email_retries_job.py -v`. It printed 67 test ids, each PASSED: 67 passed, 0 failed, 22.3s. Each named test below appears in that output by itself. The spec 28 delivery and retry files were included because the fix touched the shared `_attempt`.

C25b was run from `frontend` with `npx vitest run tests/auth-protect.test.ts -t "every page protected"`: 1 file, 1 test passed. C22 was checked from the repo root with `test -f` on the three PNGs, which exited 1.

`test_alert_emails.py` gained one import at line 19 (`from app.modules.notifications import sample_alert`), so every citation in that file moved down by 1. The citations below are refreshed. `test_alert_email_template.py` and `alert_email_support.py` did not change.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | created → 1 row per owner (2), with kind, template, dedup key and reason; sent; 2 sends | `test_created_emails_each_owner` PASSED | `services/core/tests/test_alert_emails.py:110` `len(rows) == 2`; `:116` `row.dedup_key == f"alert:{alert.id}:{alert.notified_shortfall_cents}"`; `:120` `row.state == "sent"`; `:121-122` sends to both addresses | PASS |
| C2 | grown shortfall → second key `alert:{id}:300000`, 2 rows, 2 sends | `test_updated_emails_again` PASSED | `services/core/tests/test_alert_emails.py:135` dedup keys `== [f"alert:{first.id}:100000", f"alert:{first.id}:300000"]`; `:139` `len(mail.sender.sent) == 2` | PASS |
| C3 | same event twice → 1 row and 1 send; updated twice → exactly 1 more | `test_same_event_twice` PASSED | `services/core/tests/test_alert_emails.py:150-151` `== 1`; `:158-159` `== 2` | PASS |
| C4 | both subscription rows come after the last `check_cash_gaps`, none for resolved; resolve → 0 new rows | `test_subscriptions_and_resolved` PASSED | `services/core/tests/test_alert_emails.py:170-172` `created > last_check`, `updated > last_check`, no `alert.resolved`; `:179-180` state `resolved`, `len(deliveries) == 1` | PASS |
| C5 | dismissed or resolved → 0 rows; logs `email.alert_skipped` with the state | `test_not_open_skipped` PASSED | `services/core/tests/test_alert_emails.py:215-216` `== []`; `:222` `skipped == [(str(alert.id), "dismissed"), (str(gone.id), "resolved")]` | PASS |
| C6 | foreign or random alert id → 0 rows; logs `not_found` | `test_foreign_alert_skipped` PASSED | `services/core/tests/test_alert_emails.py:242` `len(deliveries()) == before`; `:248` `skipped == [(str(alert.id), "not_found"), (str(stranger), "not_found")]` | PASS |
| C7 | only A's owners get rows; B's owner gets 0 | `test_only_this_business_owners` PASSED | `services/core/tests/test_alert_emails.py:257` `{r.user_id ...} == set(owners(a))`; `:259` B's owner rows `== []` | PASS |
| C8 | opted-out owner is `skipped`, the other is `sent`, 1 send | `test_owner_opted_out` PASSED | `services/core/tests/test_alert_emails.py:270` `states[first] == "skipped"`; `:271` `["sent", "skipped"]`; `:272` `[e.to ...] == ["sam@example.test"]` | PASS |
| C9 | one `email.alert_requested` with alert_id, `alert.created`, and 2 deliveries | `test_requested_logged` PASSED | `services/core/tests/test_alert_emails.py:290-293` `len(requested) == 1`, `alert_id`, `event_name == "alert.created"`, `deliveries == 2` | PASS |
| C10 | PUT minimum-balance alone → exactly 1 email to Dana with the C11 subject | `test_sample_end_to_end` PASSED | `services/core/tests/test_alert_emails.py:303-305` `(email,) = sample.sent`, `email.to == DANA`, subject literal; the request is in `services/core/tests/alert_email_support.py:66-74` (unchanged) | PASS |
| C11 | subject = h1 = the text line after the label | `test_sample_heading` PASSED | `services/core/tests/test_alert_email_template.py:96-99` (carried from 1dca603; file unchanged) | PASS |
| C12 | label by change, in HTML and text; label comes before the h1 | `test_label_by_change` PASSED | `services/core/tests/test_alert_email_template.py:107-109` (carried from 1dca603) | PASS |
| C13 | greeting with and without a first name | `test_greeting` PASSED | `services/core/tests/test_alert_email_template.py:114-124` (carried from 1dca603) | PASS |
| C14 | sample li order; builder ordering, naming, no `arrives_after` | `test_sample_causes`, `test_params_causes` PASSED | `services/core/tests/test_alert_email_template.py:131` li literal list; `services/core/tests/test_alert_emails.py:367-370` `== [(9000, "2026-11-11"), (9000, "2026-11-12"), (5000, "2026-11-10")]`; `:384` `== ["Acme", "Birch & Co"]` | PASS |
| C15 | text for the 4 fix kinds, `Top fix:` prefix, keeps-above at =, > and −1; sample line | `test_top_fix[x4]`, `test_top_fix_keeps_above_edges`, `test_sample_top_fix` PASSED | `services/core/tests/test_alert_email_template.py:176`, `:179`, `:203-205`, `:211` (carried from 1dca603) | PASS |
| C16 | no fix → no "Top fix:" in HTML or text, no `#FFF4E2` | `test_no_fix` PASSED | `services/core/tests/test_alert_email_template.py:219-221` (carried from 1dca603) | PASS |
| C17 | one button link; button text for counts 0-3 | `test_button[x4]` PASSED | `services/core/tests/test_alert_email_template.py:237-238` (carried from 1dca603) | PASS |
| C18 | money and day filter values; non-CAD raises; unsigned params; negative low | `test_filters`, `test_filters_unsigned_params`, `test_negative_low` PASSED | `services/core/tests/test_alert_email_template.py:244-254`, `:251` `pytest.raises(ValueError)`, `:259-260`, `:266` (carried from 1dca603). Door 4's consequence ("which fails the delivery") is now proven at `services/core/tests/test_alert_emails.py:460-462` (see F1) | PASS |
| C19 | plain-text line order | `test_plain_text_order` PASSED | `services/core/tests/test_alert_email_template.py:285`, `:289` (carried from 1dca603) | PASS |
| C20 | no flex, grid or position; no link, script or img; button td has bgcolor and a white link | `test_email_safe_html` PASSED | `services/core/tests/test_alert_email_template.py:295-303` (carried from 1dca603) | PASS |
| C21 | mockup colours | `test_mockup_colours` PASSED | `services/core/tests/test_alert_email_template.py:309-315` (carried from 1dca603) | PASS |
| C22 | Gmail, Outlook and Apple Mail screenshots, plus user confirmation | `test -f .specs/features/29-email-alerts/{gmail,outlook,apple-mail}.png` exit 1 | none: `.specs/features/29-email-alerts/` holds only `plan.md`, `checks.md` and `verification.md`; no user confirmation | FAIL (not proven) |
| C23 | sample command sends 1 email to `--to` with the C11 subject and a cause line; no `--to` → exit 2 | `test_sample_alert_command` PASSED | `services/core/tests/test_alert_email_template.py:336-343` (carried from 1dca603) | PASS |
| C24 | params have exactly the door 3 keys; no account id, Plaid id, mask, source_id or Clerk id in params, HTML or text | `test_params_hold_no_account` PASSED | `services/core/tests/test_alert_emails.py:390-404` exact key sets; `:421` `assert accounts and source_ids`; `:423-425` `value not in text` | PASS |
| C25 | hrefs are exactly the 3 URLs, each present, none with `?`; the alert page is protected | `test_links` PASSED; vitest `every page protected` 1 passed | `services/core/tests/test_alert_email_template.py:325-329`; `frontend/tests/auth-protect.test.ts:33` `expect(unprotected).toEqual([])`; `frontend/app/(app)/alerts/[alertId]/page.tsx:10` `await auth.protect()` (carried from 1dca603) | PASS |
| C26 | without `mail`, `get_clerk_users()` is a no-users fake, not Backend | `test_no_real_clerk_in_tests` PASSED | `services/core/tests/test_alert_emails.py:431` `not isinstance(users, clerk.BackendClerkUsers)`; `:432` `users.get("user_anything") is None`. The consequence is proven by spec 28's `services/core/tests/test_email_delivery.py:160` (F3, carried) | PASS |

## Findings

**F1: resolved at 900bbc7.**

`services/core/app/modules/notifications/service.py:179` now reads `except (TemplateError, ValueError) as exc:` and returns `_failed(delivery, type(exc).__name__, retryable=False)` (`:182`). The `money` filter's `ValueError` (`services/core/app/modules/notifications/rendering.py:62`) now marks that one row `failed`. `deliver()` (`service.py:124-137`) then commits and returns. This means:

- `email_alert`'s loop over owners goes on to the next owner.
- `retry_pending` goes on to the next row.

The new test `test_non_cad_fails_one_delivery` (`services/core/tests/test_alert_emails.py:435-462`) asserts what door 4 claims:

- It requests a USD delivery and then a CAD delivery, and calls `deliver` for each in turn.
- `:460` `mail.deliveries(bad)[0].state == "failed"`
- `:461` `mail.deliveries(good)[0].state == "sent"`
- `:462` `[email.to for email in mail.sender.sent] == ["good@example.test"]`

Without the fix, the first `deliver` would raise and the test would error, which is what the commit message reports. The test calls `deliver` directly, not through `email_alert` or `retry_pending`. That is enough, because the change is inside `_attempt`, which both paths reach through `deliver`.

Fault injection is not run under `light`, so this new assertion surface has not been made to fail by the Verifier. The test fails on the pre-fix code, and that reasoning stands in place of a mutation run.

**Is catching `ValueError` too broad?** No. The `try` block covers only `rendering.render(...)` and building `rendering.Footer(...)` (`service.py:167-181`). Everything that is retryable sits outside it:

- The Clerk and contact lookup is at `service.py:158-163`. Its `ContactUnavailableError` is still mapped to retryable at `:160-161`.
- `get_settings()` (`:165`) and `repository.ensure_token` (`:166`) run before the `try`.
- The sender call is at `:195-198`. It is still `SendError` → `exc.retryable`.

`render()` (`rendering.py:89-112`) is pure over stored params and local template files. It calls `get_settings()` again, but that function is `@lru_cache` (`services/core/app/settings.py:109-110`) and was already resolved at `service.py:165`. So a pydantic `ValidationError` (a `ValueError` subclass) cannot first appear inside the `try`.

Any other `ValueError` that rendering could raise is deterministic for a given stored row, so failing it permanently is correct and does not hide a transient error. Examples are `date.fromisoformat` at `rendering.py:71` on a malformed date, or a `UnicodeDecodeError` from a template file. The spec 28 retryable and permanent tests (`test_retryable_errors[*]`, `test_retryable_errors_clerk_timeout`, `test_permanent_errors[*]`, `test_render_error_fails_one_row_and_spares_the_rest`) all passed at `900bbc7`, so the fix did not change the existing classification.

A residual, outside door 4: `KeyError` and `TypeError` from a bad params shape would still escape `_attempt`. `StrictUndefined` (`rendering.py:81`) turns missing keys into `UndefinedError`, which is a `TemplateError`, so this is unlikely. No check or door claims these errors, and this is not a finding.

**F2 (C22 unproven, blocking): carried from 1dca603, re-checked at 900bbc7.** This is the plan's open question 1, and nothing changed. The user has to:

1. Send the sample through Resend: `uv run python -m app.modules.notifications.sample_alert --to <address>` from `services/core`.
2. Save `gmail.png`, `outlook.png` and `apple-mail.png` in `.specs/features/29-email-alerts/`.
3. Confirm what each screenshot shows.

The `test -f` proof exited 1 at `900bbc7`.

**F3 (precision note, C26): carried from 1dca603.** The fix did not touch C26 or its test (the only change is the new test appended after it). The C26 test asserts only that the fake is installed and has no users (`services/core/tests/test_alert_emails.py:431-432`). The `no_contact` consequence is proven by spec 28's `test_no_contact_fails` (`services/core/tests/test_email_delivery.py:149-165`, which passed at `900bbc7`). The C26 proof line does not cite that test.

**Level and sampling: carried from 1dca603.** The new test exercises `deliver` against the real local Postgres, at the same level as C1-C9.

## Swept existing re-read

Verified at 900bbc7 for the two rows F1 touched. The other rows are carried from 1dca603 (their files did not change).

| Row | Cited constraint | In code | Finding |
| --- | --- | --- | --- |
| validation | non-CAD raises and the delivery is marked `failed` | raise at `rendering.py:62`; failed at `service.py:179-182`; proven at `test_alert_emails.py:460` | none (F1 resolved) |
| failure modes | the bus logs `event.handler_failed`; a render error fails one delivery without stopping the others | `services/core/app/events.py:53`; `service.py:179-182` now covers `TemplateError` and `ValueError`; proven at `test_alert_emails.py:461-462` and in `test_render_error_fails_one_row_and_spares_the_rest` | none |
| concurrency | `uq_email_deliveries_dedup_key_user_id` + `ON CONFLICT DO NOTHING` + `SKIP LOCKED` | `models.py:56`, `repository.py:105`, `repository.py:118` (carried) | none |
| dependency failure | a Clerk or Resend failure stays `pending` | `service.py:160-161` (Clerk, retryable), `service.py:195-198` (SendError, retryable flag), `service.py:218-220` (`_failed` returns `pending` when retryable) | none |

Profile `light`: no coverage recompute, no Test policy verdicts and no fault injection (not required).

## Gate

`uv run pytest tests/test_alert_emails.py tests/test_alert_email_template.py tests/test_email_delivery.py tests/test_email_retries_job.py -v` at 900bbc7: 67 passed, 0 failed. `npx vitest run tests/auth-protect.test.ts -t "every page protected"`: 1 passed. C22 file check: exit 1. The full API suite was not re-run in this round.

**Ranked gaps**
1. C22 has no screenshots and no user confirmation. Evidence: none (`test -f` exit 1).
2. F3: C26's proof is narrower than its claim (precision note, not blocking). `services/core/tests/test_alert_emails.py:431-432`.
