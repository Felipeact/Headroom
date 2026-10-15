# 30 - Weekly digest verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: ebb454a^..HEAD (7c34c42)
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

Two checks are not proven: C11 (one of its three claims has no assertion, and its job list is stale after spec 32) and C27 (the three mail-client screenshots do not exist). The other 32 checks are proven with located assertions.

## Binding sources

Step 1 does not run under profile `light`. Not applicable.

## Checks

Proofs run at HEAD from `services/core` with DATABASE_URL set to the local Postgres: `uv run pytest tests/test_weekly_digest.py tests/test_weekly_digest_template.py tests/test_digest_reads.py -v` - 48 collected, 48 PASSED, each id printed individually. From `frontend`: `npx vitest run tests/auth-protect.test.ts -t "every page protected"` - 1 passed.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | one row per owner, kind/template/dedup/reason/sent | `-k emails_each_owner` passed | `tests/test_weekly_digest.py:280` `assert {r.user_id for r in rows} == {biz.owner_id, second}`; `:284` dedup key; `:289` `row.state == "sent"` | PASS |
| C2 | only the 08:00 hour sends | `-k only_the_eight_o_clock_hour` 6 passed | `test_weekly_digest.py:307` `assert weekly_digest(now) == {"digests_requested": 0, "digests_failed": 0}`; `:316` `len(digests(biz.id)) == 1` | PASS |
| C3 | St. John's half hour and clock change | `-k newfoundland_half_hour` passed | `test_weekly_digest.py:346` `assert due(found) == {ST_JOHNS}`; `:348` `len(...) == 1` after the 11:00 UTC Nov 2 run; `:351` two dedup keys | PASS |
| C4 | Toronto at 12:00, Vancouver at 15:00 | `-k eastern_and_pacific` passed | `test_weekly_digest.py:361` `assert due(found) == {TORONTO}`; `:363` `{TORONTO, VANCOUVER}` | PASS |
| C5 | same hour twice leaves one row and send | `-k same_hour_twice` passed | `test_weekly_digest.py:372-373` `len(digests(biz.id)) == 1`, `len(digest_sends(mail)) == 1` | PASS |
| C6 | opted-out owner skipped; alerts-off still sent | `-k owner_opted_out` passed (plus `alerts_off_still_gets_the_digest`) | `test_weekly_digest.py:383` `by_user[biz.owner_id].state == "skipped"`; `:385` sends `== ["sam@example.test"]`; `:394` `row.state == "sent"` | PASS |
| C7 | only this business's owners | `-k only_this_business_owners` passed | `test_weekly_digest.py:409` user_id set; `:413` `row.business_id == biz.id` | PASS |
| C8 | skipped without forecast or minimum, logged | `-k skipped_without_forecast_or_minimum` passed | `test_weekly_digest.py:446-447` reasons `no_forecast`, `no_minimum`; `:450` complete business gets 1 | PASS |
| C9 | one failure does not stop the rest | `-k one_failure_does_not_stop_the_rest` passed | `test_weekly_digest.py:482` error_type log; `:485-487` 0 rows, 1 row, `digests_failed == 1` | PASS |
| C10 | requested logged and counted | `-k requested_logged_and_counted` passed | `test_weekly_digest.py:498` counts `{"digests_requested": 2, ...}`; `:506` monday; `:507-509` zero counts | PASS |
| C11 | JOBS order; run_due summary holds both keys; keys in no other job | `-k registered_in_jobs` passed | `test_weekly_digest.py:516-522` asserts JOBS names only. No assertion anywhere that the `run_due` summary holds `digests_requested` and `digests_failed` (search `rg digests_requested tests` hits only direct `weekly_digest(...)` calls in `test_weekly_digest.py`). The asserted list also contains `weekly_metrics` (spec 32), which `checks.md` C11 does not list | FAIL |
| C12 | subject, h1, first text line | `-k sample_heading` passed | `test_weekly_digest_template.py:82` `out.subject == SUBJECT`; `:83` h1 regex; `:85` line after label `== SUBJECT` | PASS |
| C13 | label in HTML and text, before h1 | `-k label` passed | `test_weekly_digest_template.py:93` `label in out.text.splitlines()`; `:94` `out.html.index(label) < out.html.index("<h1")` | PASS |
| C14 | greeting with and without name | `-k greeting` passed | `test_weekly_digest_template.py:101` "Hi Dana, here's where ..."; `:108-110` no-name text and no "Hi" | PASS |
| C15 | cash on hand from snapshot, tile format | `-k cash_on_hand_from_snapshot`, `-k cash_tile` passed | `test_weekly_digest.py:530` `["cash_on_hand_cents"] == 4230000`; `test_weekly_digest_template.py:115-116` "$42,300", "−$1,500" | PASS |
| C16 | projected low, tie, amber only below minimum | `-k projected_low`, `-k low_tile` passed | `test_weekly_digest.py:546` low dict; `test_weekly_digest_template.py:123-124` "$3,150 Week of Nov 9", amber; `:128` "−$3,150"; `:133-134` no amber at equal or above | PASS |
| C17 | open alerts block, link text by fix count, order | `-k open_alerts`, `-k alerts_by_start_date` passed | `test_weekly_digest_template.py:141,145,149-150,157-158`; `test_weekly_digest.py:564-565` "Open alerts (2)", Nov 9 before Dec 14 | PASS |
| C18 | all clear text, also at equal | `-k all_clear` (2 params), `-k all_clear_params` passed | `test_weekly_digest_template.py:168-171` (params 620000 and 500000); `test_weekly_digest.py:572` `alerts == []` | PASS |
| C19 | dismissed gap: no alerts, neither block, amber | `-k dismissed_gap` (2 tests) passed | `test_weekly_digest.py:582-585`; `test_weekly_digest_template.py:178-180` | PASS |
| C20 | changes since last Monday | `-k changes_since_last_monday`, `-k changes_bullets` passed | `test_weekly_digest.py:621-623` +412000, -60000, 3 largest in order, "Tiny" and "Before the cutoff" absent; `test_weekly_digest_template.py:192,197,199,204` bullets | PASS |
| C21 | nothing changed line | `-k nothing_changed` passed | `test_weekly_digest_template.py:213` and `:215` `"<li>" not in out.html` | PASS |
| C22 | no baseline pin gives null and no section | `-k no_baseline_pin`, `-k no_changes_section` passed | `test_weekly_digest.py:655` `["changes"] is None`; `test_weekly_digest_template.py:221-222` | PASS |
| C23 | one button to the dashboard | `-k dashboard_button` passed | `test_weekly_digest_template.py:228` regex `<a href="{WEB}/"...>Open your dashboard</a>`; `:231` text line. It asserts presence, not that there is exactly one button | PASS |
| C24 | plain-text order | `-k plain_text_order` passed | `test_weekly_digest_template.py:249` `assert positions == sorted(positions)` over the nine lines at `:236-246` | PASS |
| C25 | email-safe HTML | `-k email_safe_html` passed | `test_weekly_digest_template.py:256,258` banned strings and tags; `:267` `.count(2) == 1`; `:268` bgcolor button regex | PASS |
| C26 | mockup colours | `-k mockup_colours` passed | `test_weekly_digest_template.py:274-280` (#5A6370, #E2DDD3, #FFF4E2 with #F0D3A4, #5C3300, #7A4300, #3D2E1C, #1D4E89) | PASS |
| C27 | one screenshot per mail client | `test -f .specs/features/30-email-weekly-digest/gmail.png && ... outlook.png && ... apple-mail.png` exits 1 | The folder holds only `checks.md` and `plan.md`; none of the three PNGs exist. Needs real Resend, mail clients and the user's confirmation, which I cannot do. GATED, and as written the check is not met | FAIL (gated) |
| C28 | sample command sends one email, exit 2 without --to | `-k sample_digest_command` passed | `test_weekly_digest_template.py:287` `main([...]) == 0`; `:289-291` to/subject/html; `:294` `exit_info.value.code == 2` | PASS |
| C29 | end to end through run_due | `-k sample_end_to_end` passed | `test_weekly_digest.py:668` `[e.to for e in sent] == [DANA]`; `:669-671` "$3,150", "Week of Nov 9", alert text | PASS |
| C30 | params keys; no account data | `-k params_hold_no_account` passed | `test_weekly_digest.py:733` `set(params) == {...}`; `:743`, `:748`; `:763-765` forbidden values absent from stored, html, text | PASS |
| C31 | hrefs allowed, no `?`, pages protected | `-k links` passed; `npx vitest run tests/auth-protect.test.ts -t "every page protected"` 1 passed | `test_weekly_digest_template.py:300` `set(hrefs(out.html)) == {...}`; `:306` no `?`; `frontend/tests/auth-protect.test.ts:17` `test('every page protected'` | PASS |
| C32 | pinned forecast read | `-k pinned_forecast` (2 tests) passed | `tests/test_digest_reads.py:53` `found == PinnedForecastView(...)`; `:75` other business's pin; `:95-96` tie takes earlier week | PASS |
| C33 | payments added since | `-k payments_added_since` passed | `tests/test_digest_reads.py:148` `assert found == [...]` | PASS |
| C34 | all business zones | `-k all_business_zones` passed | `tests/test_digest_reads.py:182-183` Vancouver and St_Johns | PASS |

## Findings

1. C11, coverage gap: the claim that `run_due(now)` returns a summary holding `weekly_digest` with both keys, and that the keys appear in no other job, has no assertion. The one test that goes through `run_due` (C29, `test_weekly_digest.py:665`) monkeypatches `JOBS` to the digest alone and asserts only on the email.
2. C11, stale check: `checks.md` says JOBS is `(nightly_bank_sync, forecast_accuracy, weekly_digest, email_retries)`. Spec 32 added `weekly_metrics`, so the test (`test_weekly_digest.py:516-522`) rightly asserts five. The check text needs amending.
3. C27: the three screenshots were never produced. This is user-gated (Gmail, Outlook, Apple Mail).

## Gate

`uv run pytest tests/test_weekly_digest.py tests/test_weekly_digest_template.py tests/test_digest_reads.py -v` - 48 passed, 0 failed; `npx vitest run tests/auth-protect.test.ts -t "every page protected"` - 1 passed.
