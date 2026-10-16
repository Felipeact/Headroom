# 29 - Alert emails verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 24b62e8..cd1d68e (HEAD)
**Round**: 3 - scoped
**Verifier**: independent sub-agent (author != verifier)

All 26 checks are proven at `cd1d68e`. C22 was the only check that was not PASS in round 2. It is now settled by its amended proof: `gmail.png` exists and shows the email in one column. The user's own check of Outlook and Apple Mail is recorded as AD-117, and the user decided that counts as evidence. Three notes go with C22 (F4, F5 and F6). None of them blocks. F3 carries over unchanged.

This round covers two things: the fix's diff, and every round 2 verdict that was not PASS (C22, F2, F3).

- `git diff --stat 900bbc7..HEAD` touches only `.specs/STATE.md` (+1, AD-117), `checks.md` (+3/−1, the C22 amendment and the header count), `plan.md` (+2, open question 1 answered) and the new `gmail.png` (213,685 bytes, PNG 1463 x 914).
- Commit 503be11 adds only the round 2 report and the token log rows.
- `git diff --stat 900bbc7..HEAD -- services frontend` is empty, so no code, test or fixture changed.

Every proof was re-run in full at `cd1d68e`. Every row except C22 carries its verdict and citations from `900bbc7`. The cited files did not change, so the line numbers did not move.

## Binding sources

Carried from 900bbc7. Step 1 does not run under profile `light`, and nothing in this round touched the interface. The plan marks `design/mockups/email-alert.dc.html` as binding. I did not compare it against the checks this round. C22 is the check that covers rendering in real mail clients, and it is judged below.

## Checks

Verified at cd1d68e. From `services/core` I ran `uv run pytest tests/test_alert_emails.py tests/test_alert_email_template.py tests/test_email_delivery.py tests/test_email_retries_job.py -v`. It collected 67 items and printed each id as PASSED: 67 passed, 0 failed, 1 warning (Starlette's `httpx` deprecation), 25.10s. Each named test below appears in that output by itself.

From `frontend` I ran `npx vitest run tests/auth-protect.test.ts -t "every page protected"`: 1 file, 1 test passed.

From the repo root, `test -f .specs/features/29-email-alerts/gmail.png` exited 0. For the record, `outlook.png` and `apple-mail.png` still exit 1. The amended proof no longer requires them.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | created → 1 row per owner (2), with kind, template, dedup key and reason; sent; 2 sends | `test_created_emails_each_owner` PASSED | `services/core/tests/test_alert_emails.py:110` `len(rows) == 2`; `:116` dedup key; `:120` `row.state == "sent"`; `:121-122` (carried from 900bbc7) | PASS |
| C2 | grown shortfall → second key `alert:{id}:300000`, 2 rows, 2 sends | `test_updated_emails_again` PASSED | `services/core/tests/test_alert_emails.py:135`, `:139` (carried from 900bbc7) | PASS |
| C3 | same event twice → 1 row and 1 send; updated twice → exactly 1 more | `test_same_event_twice` PASSED | `services/core/tests/test_alert_emails.py:150-151`, `:158-159` (carried from 900bbc7) | PASS |
| C4 | subscription rows after the last `check_cash_gaps`, none for resolved; resolve → 0 new rows | `test_subscriptions_and_resolved` PASSED | `services/core/tests/test_alert_emails.py:170-172`, `:179-180` (carried from 900bbc7) | PASS |
| C5 | dismissed or resolved → 0 rows; logs `email.alert_skipped` with the state | `test_not_open_skipped` PASSED | `services/core/tests/test_alert_emails.py:215-216`, `:222` (carried from 900bbc7) | PASS |
| C6 | foreign or random alert id → 0 rows; logs `not_found` | `test_foreign_alert_skipped` PASSED | `services/core/tests/test_alert_emails.py:242`, `:248` (carried from 900bbc7) | PASS |
| C7 | only A's owners get rows; B's owner gets 0 | `test_only_this_business_owners` PASSED | `services/core/tests/test_alert_emails.py:257`, `:259` (carried from 900bbc7) | PASS |
| C8 | opted-out owner `skipped`, other `sent`, 1 send | `test_owner_opted_out` PASSED | `services/core/tests/test_alert_emails.py:270-272` (carried from 900bbc7) | PASS |
| C9 | one `email.alert_requested` with alert_id, `alert.created`, 2 deliveries | `test_requested_logged` PASSED | `services/core/tests/test_alert_emails.py:290-293` (carried from 900bbc7) | PASS |
| C10 | PUT minimum-balance alone → exactly 1 email to Dana with the C11 subject | `test_sample_end_to_end` PASSED | `services/core/tests/test_alert_emails.py:303-305` (carried from 900bbc7) | PASS |
| C11 | subject = h1 = the text line after the label | `test_sample_heading` PASSED | `services/core/tests/test_alert_email_template.py:96-99` (carried from 900bbc7) | PASS |
| C12 | label by change; label before the h1 | `test_label_by_change` PASSED | `services/core/tests/test_alert_email_template.py:107-109` (carried from 900bbc7) | PASS |
| C13 | greeting with and without a first name | `test_greeting` PASSED | `services/core/tests/test_alert_email_template.py:114-124` (carried from 900bbc7) | PASS |
| C14 | sample li order; builder ordering, naming, no `arrives_after` | `test_sample_causes`, `test_params_causes` PASSED | `services/core/tests/test_alert_email_template.py:131`; `services/core/tests/test_alert_emails.py:367-370`, `:384` (carried from 900bbc7) | PASS |
| C15 | the 4 fix kinds, `Top fix:` prefix, keeps-above at =, > and −1; sample line | `test_top_fix[x4]`, `test_top_fix_keeps_above_edges`, `test_sample_top_fix` PASSED | `services/core/tests/test_alert_email_template.py:176`, `:179`, `:203-205`, `:211` (carried from 900bbc7) | PASS |
| C16 | no fix → no "Top fix:", no `#FFF4E2` | `test_no_fix` PASSED | `services/core/tests/test_alert_email_template.py:219-221` (carried from 900bbc7) | PASS |
| C17 | one button link; text for counts 0-3 | `test_button[x4]` PASSED | `services/core/tests/test_alert_email_template.py:237-238` (carried from 900bbc7) | PASS |
| C18 | filter values; non-CAD raises; unsigned params; negative low | `test_filters`, `test_filters_unsigned_params`, `test_negative_low` PASSED | `services/core/tests/test_alert_email_template.py:244-254`, `:251`, `:259-260`, `:266`; door 4 consequence `services/core/tests/test_alert_emails.py:460-462` (carried from 900bbc7) | PASS |
| C19 | plain-text line order | `test_plain_text_order` PASSED | `services/core/tests/test_alert_email_template.py:285`, `:289` (carried from 900bbc7) | PASS |
| C20 | email-safe HTML; button td bgcolor and white link | `test_email_safe_html` PASSED | `services/core/tests/test_alert_email_template.py:295-303` (carried from 900bbc7) | PASS |
| C21 | mockup colours | `test_mockup_colours` PASSED | `services/core/tests/test_alert_email_template.py:309-315` (carried from 900bbc7) | PASS |
| C22 | in Gmail, Outlook and Apple Mail: one column; nothing clipped or overlapping; wordmark, label, heading, causes, top fix box, button and footer all shown (amended proof: `gmail.png` + AD-117) | `test -f .specs/features/29-email-alerts/gmail.png` exit 0 | `.specs/features/29-email-alerts/gmail.png` opened and described below; `.specs/STATE.md:124` AD-117 records the user's check of all three clients; `.specs/features/29-email-alerts/checks.md:427-428` amendment (verified at cd1d68e) | PASS |
| C23 | sample command: 1 email to `--to`, C11 subject, a cause line; no `--to` → exit 2 | `test_sample_alert_command` PASSED | `services/core/tests/test_alert_email_template.py:336-343` (carried from 900bbc7) | PASS |
| C24 | params have exactly the door 3 keys; no account or Clerk identifiers in params, HTML or text | `test_params_hold_no_account` PASSED | `services/core/tests/test_alert_emails.py:390-404`, `:421`, `:423-425` (carried from 900bbc7) | PASS |
| C25 | hrefs exactly the 3 URLs, none with `?`; the alert page is protected | `test_links` PASSED; vitest `every page protected` 1 passed | `services/core/tests/test_alert_email_template.py:325-329`; `frontend/tests/auth-protect.test.ts:33` `expect(unprotected).toEqual([])`; `frontend/app/(app)/alerts/[alertId]/page.tsx:10` (carried from 900bbc7) | PASS |
| C26 | without `mail`, `get_clerk_users()` is a no-users fake, not Backend | `test_no_real_clerk_in_tests` PASSED | `services/core/tests/test_alert_emails.py:431-432`; consequence at `services/core/tests/test_email_delivery.py:160` (F3, carried from 900bbc7) | PASS |

## C22: what gmail.png shows

Verified at cd1d68e. The image is a full-window Windows screenshot of Gmail (web) in Chrome. The tab title reads "Cash falls below your $5,000 m…", and the message pane is open. From top to bottom, inside the email:

- **Wordmark:** "Headroom" in a serif face, at the top of a white card. The card's top edge sits just under Gmail's toolbar, which means the pane is scrolled down a little. Gmail's own subject and sender header are scrolled out of view. The wordmark itself is whole.
- **Label:** "CASH GAP", in small uppercase type, coloured brown or amber.
- **Heading:** "Cash falls below your $5,000 minimum the week of Nov 9", in a serif face, wrapped over two lines.
- **First paragraph:** "Hi Dana, the forecast for Harbor Street Plumbing shows cash dropping to **$3,150** in the week of Nov 9."
- **Causes:** "What's causing it", in bold, followed by two bullets: "Coastal Supply Co, $14,500, on Thu, Nov 12" and "Payroll, $11,200, on Fri, Nov 13".
- **Top fix box:** a cream box with a tan border. It reads "**Top fix:** ask Birch & Co to pay their $9,600 invoice a week early. That keeps you above your minimum."
- **Button:** a dark blue button with white text, "See all 3 fixes".
- **Footer, below the card on the grey background:** "You're getting this email because you're an owner of Harbor Street Plumbing on Headroom." Below that, the links "Email preferences · Unsubscribe". Both links are underlined, and they sit at the bottom edge of the pane.

Everything sits in one centred column. No element is clipped inside the card, and none overlaps another. The text wraps cleanly.

**What falls outside the frame.** The footer's last line is not in the image. `services/core/app/modules/notifications/templates/base.html:29` renders it as `Headroom · {{ mailing_address }}`, so the mailing address is not visible. The "Email preferences · Unsubscribe" line, from `base.html:28`, sits right at the pane's lower edge. Its text and underlines are legible, and at most its bottom few pixels are cut.

This is a crop by the scrolled viewport, not a rendering defect. The cut falls at the edge of Gmail's message pane, where Gmail's fixed Reply/Forward bar begins, and not at any edge inside the email. The pane's scrollbar shows more content below, and the top of the card is cut the same way by the toolbar.

From this image I can't tell how the mailing-address line renders in Gmail. The HTML includes it: the spec 28 test `test_footer_in_sent_email` passed. Whether it renders without clipping rests on the user's confirmation in AD-117.

## Findings

**F2 (C22 unproven): resolved at cd1d68e by the user's decision, AD-117.** The amended proof is `test -f gmail.png` plus AD-117. The file test exits 0, and the screenshot shows what the claim lists, apart from the cropped mailing-address line (F4). By the user's decision, the recorded confirmation is accepted evidence for Outlook and Apple Mail. I saw no screenshot of either client, and I invent no evidence for them: they rest on AD-117 alone.

**F4 (precision note, C22): the Gmail screenshot does not show the whole footer.** The mailing-address line (`base.html:29`) is outside the frame, and the preferences and unsubscribe line sits at the pane's edge. This is a viewport crop, not a rendering defect (see above). The claim's "footer" is therefore only partly evidenced by the image. The rest is covered by the user's confirmation in AD-117. This does not block. A re-capture scrolled to the bottom would close it.

**F5 (precision note, C22): the claim and the amended proof disagree on one sentence.** The amendment says "the claim is unchanged". The claim still says "One screenshot per client exists in the feature folder" (`checks.md:425`), and that is false at HEAD: `outlook.png` and `apple-mail.png` exit 1. The user waived that sentence through AD-117, so this is a wording gap, not a FAIL. Rewording the claim to match the amended proof would remove the contradiction.

**F6 (wording in AD-117, for the user to confirm): the rationale reads two ways.** `.specs/STATE.md:124` says "the user has only Gmail and chose not to save the other two screenshots; they confirmed the email renders correctly in all three clients". The phrase "has only Gmail" reads at odds with having checked Outlook and Apple Mail. The commit message and the plan's answer (`plan.md`, "Answered 2026-10-14") both say plainly that the user checked all three. I take the explicit confirmation as the recorded fact. I flag the wording so the user can make sure AD-117 says what they meant. This does not block.

**F3 (precision note, C26): carried from 900bbc7.** C26's own test asserts only that the fake is installed and has no users (`services/core/tests/test_alert_emails.py:431-432`). The `no_contact` consequence is proven by spec 28's `test_no_contact_fails` (`services/core/tests/test_email_delivery.py:149-165`), which passed at `cd1d68e`.

**F1: resolved at 900bbc7 (carried).** The code it covers did not change.

**Level and sampling: carried from 900bbc7.**

## Swept existing re-read

Carried from 900bbc7. No code changed in `900bbc7..cd1d68e`.

| Row | Cited constraint | In code | Finding |
| --- | --- | --- | --- |
| validation | non-CAD raises and the delivery is marked `failed` | `rendering.py:62`; `service.py:179-182`; proven at `test_alert_emails.py:460` | none |
| failure modes | the bus logs `event.handler_failed`; a render error fails one delivery | `services/core/app/events.py:53`; `service.py:179-182` | none |
| concurrency | `uq_email_deliveries_dedup_key_user_id` + `ON CONFLICT DO NOTHING` + `SKIP LOCKED` | `models.py:56`, `repository.py:105`, `repository.py:118` | none |
| dependency failure | a Clerk or Resend failure stays `pending` | `service.py:160-161`, `service.py:195-198`, `service.py:218-220` | none |

Profile `light`: no coverage recompute, no Test policy verdicts and no fault injection (not required).

## Gate

At `cd1d68e`:

- `uv run pytest tests/test_alert_emails.py tests/test_alert_email_template.py tests/test_email_delivery.py tests/test_email_retries_job.py -v`: 67 passed, 0 failed.
- `npx vitest run tests/auth-protect.test.ts -t "every page protected"`: 1 passed.
- `test -f .specs/features/29-email-alerts/gmail.png`: exit 0.

The full API suite was not re-run in this round, because no code changed.

**Remaining notes (not blocking)**
1. F6: AD-117's "has only Gmail" wording. `.specs/STATE.md:124`.
2. F5: C22's claim still requires a screenshot per client. `.specs/features/29-email-alerts/checks.md:425`.
3. F4: the mailing-address line is outside the Gmail screenshot (viewport crop). `services/core/app/modules/notifications/templates/base.html:29`.
4. F3: C26's proof is narrower than its claim. `services/core/tests/test_alert_emails.py:431-432`.
