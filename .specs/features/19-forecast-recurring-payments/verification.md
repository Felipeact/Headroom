# 19 - Recurring payments verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 1d2904f..a659f4b
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier), dispatched fresh with no build context; read-only apart from this report

Round 2 is scoped by the fix's diff (`a191481..a659f4b`) and by the one verdict that was not a clean PASS in round 1 (C9, AC 8). The fix closes round 1's only finding. The new tie cases kill the half-up mutant that survived round 1. Every proof was re-run at HEAD `a659f4b`. All 33 checks are proven with located evidence. 1 check (C9) was re-verified at `a659f4b`, and 32 verdicts are carried from `a191481`, each marked as carried below.

## Round history

- **Round 1** (`1d2904f..a191481`, full) gave FAIL. All 33 checks were proven, but a mutant survived on C9. Changing `_median_cents` (`services/core/app/modules/forecasting/detection.py:196`) from `whole + (half and whole % 2)` to `whole + half`, which rounds half toward +infinity, still passed. The only tie in the test, -100002.5, rounds to -100002 under both rules.
- **Fix** (`a659f4b`, test only) adds `test_median_amount_ties_to_even` at `services/core/tests/test_recurring_detection.py:295-309`. It has two 6-amount monthly series whose medians are -100001.5 (expected -100002) and 100002.5 (expected 100002). For both, half to even and half up give different answers. No source file changed.
- **Round 2** (this report) gives PASS. The round 1 mutant is now killed (see Faults injected).

## Scope of the fix (verified at a659f4b)

`git diff --stat a191481..a659f4b` shows 1 file changed with 17 insertions: `services/core/tests/test_recurring_detection.py`, and nothing else. The change is purely additive, after line 292, so it can't change any source behaviour, fixture, config, or other proof. Its only side effect on other checks is that every citation in that file after line 292 moves down 17 lines. Those citations (C10-C13) are refreshed below. Citations in other files and lines 1-292 are unchanged. `ruff format --check` and `ruff check` pass on the touched file.

## Binding sources

Step 1 runs only under `ui`, and the fix didn't touch the interface. This section is carried from `a191481`: `context/specs/19-forecast-recurring-payments.md`, `design/mockups/dashboard-desktop.dc.html` (lines 253, 267, 274) and `services/core/app/fixtures/harbor_street.py` were opened in round 1, and none of them contradicts a check.

## Checks

Batched proof, re-run at `a659f4b` from `services/core`: `uv run pytest tests/test_recurring_detection.py tests/test_recurring_refresh.py tests/test_recurring_sample.py tests/test_recurring_patterns_api.py tests/test_migrations.py -v -p no:logging -k "not test_migrations or recurring_patterns_upgrade_downgrade_and_check"`. It exited 0 with 84 passed and 12 deselected: round 1's 82 plus the 2 new parametrised cases. C9 was also run on its own with `-v` (`-k median_amount`): all 4 tests PASSED. `bash .specs/features/19-forecast-recurring-payments/proofs.sh c32 c33` was re-run at `a659f4b` and exited 0.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | 6 excluded labels and pending give no pattern; normal and posted gives 1 | `test_only_normal_posted_excluded[*]` x7, `test_only_normal_posted_included` PASSED at a659f4b | `services/core/tests/test_recurring_detection.py:109` - `assert detection.detect(series(days, label=label, pending=pending)) == []`; `:114` - `only(detection.detect(...))` (`only` asserts `len == 1` at `:62`) | PASS (carried from a191481) |
| C2 | grouping key: normalised counterparty, account, direction, currency, description fallback | `test_grouping_key_*` PASSED at a659f4b | `test_recurring_detection.py:129` - `len(only(...).transaction_ids) == 12`; `:147` - `len(detection.detect(transactions)) == 2`; `:158` - `pattern.counterparty == "Invoice 1006"` | PASS (carried from a191481) |
| C3 | 115% stays in the band; 115001 splits, giving the later band of 3 | `test_amount_bands_within`, `test_amount_bands_split` PASSED at a659f4b | `test_recurring_detection.py:168` - `len(...transaction_ids) == 6`; `:177-178` - `pattern.amount_cents == -115_001`, `pattern.transaction_ids == tuple(t.id for t in later)` | PASS (carried from a191481) |
| C4 | each of the 5 series gives its own schedule, with all transactions | `test_each_schedule[*]` PASSED at a659f4b | `test_recurring_detection.py:186-187` - `pattern.schedule == schedule`; `pattern.transaction_ids == tuple(t.id for t in transactions)` | PASS (carried from a191481) |
| C5 | the tolerance edge is a hit; edge+1 is not | `test_tolerance_edges[*]` x10 PASSED at a659f4b | `test_recurring_detection.py:201` - `transactions[4].id not in pattern.transaction_ids`; `:204` - `pattern.transaction_ids == tuple(ids)` | PASS (carried from a191481) |
| C6 | 9 of 12 gives monthly with confidence 75; 8 of 12 gives none | `test_share_threshold`, `test_share_threshold_below` PASSED at a659f4b | `test_recurring_detection.py:215-216` - `schedule == "monthly"`, `confidence == 75`; `:224` - `detection.detect(series(kept)) == []` | PASS (carried from a191481) |
| C7 | 2 occurrences give none; 3 give monthly with confidence 50 | `test_three_needed` PASSED at a659f4b | `test_recurring_detection.py:242` - `detect(series(months((2026, 1), 2, 15))) == []`; `:245` - `pattern.confidence == 50` | PASS (carried from a191481) |
| C8 | biweekly cadence kept; month-end clamp to 2026-03-02; weekend moved to 2026-08-17 | `test_next_date_*` x3 PASSED at a659f4b | `test_recurring_detection.py:254` - `next_date == BIWEEKLY[-1] + timedelta(days=14)`; `:269` - `== date(2026, 3, 2)`; `:275` - `== date(2026, 8, 17)` | PASS (carried from a191481) |
| C9 | median of the last 6, rounded half to even: -100002.5 gives -100002; 3 amounts give -100001; ties that differ under half-up go to even | `test_median_amount_last_six`, `test_median_amount_ties_to_even[odd-whole-negative]`, `test_median_amount_ties_to_even[even-whole-positive]`, `test_median_amount_three` PASSED at a659f4b (`-v`) | `test_recurring_detection.py:292` - `only(detection.detect(transactions)).amount_cents == -100_002`; `:309` - `only(detection.detect(transactions)).amount_cents == expected` with `expected` readable at `:299` (`-100_002` for median -100001.5) and `:301` (`100_002` for median 100002.5); `:318` - `amount_cents == -100_001` | PASS (re-verified at a659f4b; round 1 mutant now killed) |
| C10 | confidence 50/67/100/100, and 75 for 9 of 12 | `test_confidence[*]`, `test_share_threshold` PASSED at a659f4b | `test_recurring_detection.py:327` - `pattern.confidence == confidence`; `:216` - `pattern.confidence == 75` | PASS (carried from a191481; citation refreshed, +17) |
| C11 | reported at next date + half the interval; not 1 day later | `test_stopped[*]` x5 PASSED at a659f4b | `test_recurring_detection.py:337` - `[p.schedule for p in kept] == [schedule]`; `:339` - `late == []` | PASS (carried from a191481; citation refreshed, +17) |
| C12 | fields from the most recent hit; IDs oldest first; the non-hit is excluded | `test_pattern_fields` PASSED at a659f4b | `test_recurring_detection.py:355-360` - `counterparty == "Wharfside Properties"`, `description == "Rent 6"`, `account_id == ACCOUNT`, `currency == "CAD"`, `transaction_ids == tuple(...)`, `extra.id not in pattern.transaction_ids` | PASS (carried from a191481; citation refreshed, +17) |
| C13 | shuffled input with Random(0..4) gives equal patterns | `test_input_order` PASSED at a659f4b | `test_recurring_detection.py:380` - `assert detection.detect(shuffled) == expected` | PASS (carried from a191481; citation refreshed, +17; precision note 2) |
| C14 | seed 0 Payroll: Operating, biweekly, -1120000, CAD, 2026-10-02 | `test_payroll` PASSED at a659f4b | `services/core/tests/test_recurring_sample.py:91-95` - `account_id == sample.account_id("Operating checking")`, `schedule == "biweekly"`, `amount_cents == -1_120_000`, `currency == "CAD"`, `next_date == "2026-10-02"` | PASS (carried from a191481) |
| C15 | seed 0 Rent: Wharfside, "Rent", Operating, monthly, -380000, 2026-10-15 | `test_rent` PASSED at a659f4b | `test_recurring_sample.py:101-105` - `description == "Rent"` ... `amount_cents == -380_000`, `next_date == "2026-10-15"` | PASS (carried from a191481) |
| C16 | seed 0 Software: Fieldworks, Operating, monthly, -64000, 2026-10-07 | `test_software` PASSED at a659f4b | `test_recurring_sample.py:111-115` - `description == "Software subscriptions"` ... `amount_cents == -64_000`, `next_date == "2026-10-07"` | PASS (carried from a191481) |
| C17 | seeds 0-9 give exactly the 3 counterparties | `test_exactly_three[0..9]` PASSED at a659f4b | `test_recurring_sample.py:122` - `sorted(p["counterparty"] for p in patterns) == ["Fieldworks Software", "Payroll", "Wharfside Properties"]` | PASS (carried from a191481) |
| C18 | no Reserve savings or internal_transfer IDs in any pattern; transfers exist on both accounts | `test_no_transfers` PASSED at a659f4b | `test_recurring_sample.py:139` - `{reserve, operating} <= transfer_accounts`; `:143-144` - `t["account_id"] != reserve`, `t["label"] != "internal_transfer"` | PASS (carried from a191481) |
| C19 | a sync replaces the planted row with exactly the detected set; other business unchanged | `test_sync_replaces_patterns` PASSED at a659f4b | `services/core/tests/test_recurring_refresh.py:160-163` - `len(stored) == 1`, `ghost not in ...`, `values(stored) == values(detected_now(business_id))`, `[r.id for r in rows(other)] == [others_row]` | PASS (carried from a191481; precision note 3) |
| C20 | the same event twice leaves equal rows | `test_same_event_twice` PASSED at a659f4b | `test_recurring_refresh.py:172` - `first and values(rows(c.business_id)) == first` | PASS (carried from a191481) |
| C21 | concurrent refreshes leave one set, no duplicate keys | `test_concurrent_refreshes` PASSED at a659f4b | `test_recurring_refresh.py:215,217` - `len(stored) == expected`; `len(set(keys)) == len(keys)` | PASS (carried from a191481) |
| C22 | removing all transactions leaves 0 patterns | `test_no_transactions_no_patterns` PASSED at a659f4b | `test_recurring_refresh.py:233` - `rows(c.business_id) == []` | PASS (carried from a191481) |
| C23 | the detector raises: the sync stays committed, rows are kept, one handler_failed line | `test_failure_keeps_patterns` PASSED at a659f4b | `test_recurring_refresh.py:266-267` - `count == len(RENT_DAYS) + 1`, `{r.id ...} == before`; `:273-275` - `len(failed) == 1`, `handler.endswith("refresh_recurring_patterns")`, `error_type == "RuntimeError"` | PASS (carried from a191481) |
| C24 | one refreshed line with business_id and patterns 1; no counterparty, description or amount | `test_refresh_logged` PASSED at a659f4b | `test_recurring_refresh.py:291-295` - `len(refreshed) == 1`, `["patterns"] == 1`, `secret not in out` for "Wharfside", "Rent", "380000" | PASS (carried from a191481) |
| C25 | `SUBSCRIPTIONS[0]` is the refresh handler | `test_subscribed_first` PASSED at a659f4b | `test_recurring_refresh.py:300-303` - `subscriptions.SUBSCRIPTIONS[0] == ("transactions.synced", service.refresh_recurring_patterns)` | PASS (carried from a191481) |
| C26 | 3 check constraints refuse bad rows by name; confidence 0 and 100 accepted | `test_constraints_refuse[*]` x3, `test_constraints_refuse_edges_accepted[0,100]` PASSED at a659f4b | `test_recurring_refresh.py:331` - `pytest.raises(IntegrityError, match=constraint)`; `:355` - `[r.confidence ...] == [confidence]` | PASS (carried from a191481) |
| C27 | the migration goes up from spec 17's head, with uuid[] and smallint, down, up again, then check | `test_recurring_patterns_upgrade_downgrade_and_check` PASSED at a659f4b | `services/core/tests/test_migrations.py:776-777` - `columns["transaction_ids"] == ("ARRAY", "_uuid")`, `columns["confidence"][0] == "smallint"`; `:785` - `"recurring_patterns" not in inspect(engine).get_table_names()`; `:789-791` - `alembic check` returncode 0 | PASS (carried from a191481) |
| C28 | 200, keys exactly `items`, order Acme, Zed, then 10-07; exact item keys; ISO date; int confidence | `test_order_and_shape` PASSED at a659f4b | `services/core/tests/test_recurring_patterns_api.py:221-229` - `status_code == 200`, `set(body) == {"items"}`, `[i["id"] ...] == [str(acme), str(zed), str(weekly)]`, `set(item) == ITEM_KEYS`, `type(item["confidence"]) is int` | PASS (carried from a191481) |
| C29 | an empty business gets 200 `{"items": []}` | `test_empty_business` PASSED at a659f4b | `test_recurring_patterns_api.py:239-240` - `status_code == 200`, `response.json() == {"items": []}` | PASS (carried from a191481) |
| C30 | 404 for a non-member, 403 for a viewer, only A's IDs | `test_access_denied` PASSED at a659f4b | `test_recurring_patterns_api.py:251-252` - `404`, `"Business not found."`; `:256` - `[i["id"] ...] == [str(mine)]`; `:264-265` - `403`, `"You don't have permission to do this."` | PASS (carried from a191481) |
| C31 | a non-UUID id gives 422 problem+json | `test_invalid_business_id` PASSED at a659f4b | `test_recurring_patterns_api.py:271-272` - `status_code == 422`, `content-type == "application/problem+json"` | PASS (carried from a191481) |
| C32 | the regenerated contract and types show no diff; the route has `get` | `proofs.sh c32` re-run at a659f4b: exit 0, `PASS c32`, working tree left clean | `.specs/features/19-forecast-recurring-payments/proofs.sh:17-23` - `git diff --exit-code` plus `assert "get" in spec["paths"][...]` | PASS (carried from a191481; proof re-run green) |
| C33 | every AGENTS.md check passes for the API and the web | `proofs.sh c33` re-run at a659f4b: exit 0. ruff "All checks passed!", mypy "no issues found in 43 source files", pytest 601 passed (5 deselected), vitest 29 files and 224 tests passed, build "Compiled successfully", `PASS c33` | `.specs/features/19-forecast-recurring-payments/proofs.sh:29-33` - the `&&` chain, then `fail c33` | PASS (carried from a191481; proof re-run green) |

Level is carried from `a191481`: every route and sample-data claim goes through `TestClient` with a signed token. The new C9 test is in the feature's own diff (`a659f4b`), so it isn't a proof that resolves to an untouched test.

## Swept existing (re-read)

Carried from `a191481`. The fix touched none of the files these rows cite (`services/core/tests/test_run_due.py:307`, `services/core/app/main.py:41,50,57`, `services/core/app/jobs/run_due.py:47`, `services/core/app/subscriptions.py:23`).

## Faults injected

`light` doesn't require this step. It was run on the fix's surface (`_median_cents`, the rounding rule C9 claims) on the real tree. The baseline `git status --porcelain` showed only this report. Each mutant was applied to line 196 and restored with `git checkout --`. After all mutants, the sha256 of `detection.py` matched the original (`3e2f9f4b…d01c`), and the porcelain matched the baseline.

| Mutation | Location | Killed |
| --- | --- | --- |
| round 1 survivor: `whole + (half and whole % 2)` changed to `whole + half` (half toward +infinity) | `services/core/app/modules/forecasting/detection.py:196` | yes - both `test_median_amount_ties_to_even` cases failed (2 failed, 2 passed) |
| changed to `whole` (half toward -infinity / floor) | `services/core/app/modules/forecasting/detection.py:196` | yes - `test_median_amount_last_six` failed |
| changed to `whole + (half and not whole % 2)` (half to odd) | `services/core/app/modules/forecasting/detection.py:196` | yes - `last_six` and both `ties_to_even` cases failed (3 failed) |

A fourth mutant, `whole + half * (whole % 2)`, passed all 4 tests. It is semantically equivalent to the original, because `half` is always 0 or 1, so it isn't a finding. The 4 C9 tests together now pin all three non-even tie rules.

## Findings and precision notes

1. **Round 1 finding 1 (surviving mutant / precision gap on C9, AC 8): resolved at `a659f4b`.** `test_recurring_detection.py:295-309` adds ties where half to even and half up disagree, and the half-up mutant is killed. The check's text at `.specs/features/19-forecast-recurring-payments/checks.md:60` still names only the -100002.5 tie. That text is weaker than the test now proves, but it isn't contradicted, so this is noted, not failed.
2. **Precision note (C13), carried from a191481.** The test uses a series like C12's, not C12's literal inputs. Order independence is still exercised.
3. **Precision note (C19), carried from a191481.** The planted row is written with `session.add` rather than through `forecasting.repository`. The behaviour proven is unchanged.
4. **Acknowledged in the checks, carried from a191481.** AC 5's tie-break is proven only indirectly through C4. AC 21's "after disconnect" case is proven by a sync that removes every transaction.

## Gate

- Batched recurring proofs at `a659f4b`: 84 passed, 0 failed (12 deselected).
- C9 alone with `-v`: 4 passed, 0 failed.
- `proofs.sh c32 c33` at `a659f4b`: exit 0. API 601 passed, 0 failed. Web 224 passed, 0 failed. ruff, mypy, lint, typecheck and build passed.
- Mutants: 3 injected, 3 killed. 1 equivalent mutant noted.
