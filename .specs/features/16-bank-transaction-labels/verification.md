# 16 - Transaction labels verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 06fe8df..c74f0370456969eb001ade9ac0d9f9085ca8eb55
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

Round 2 is scoped to fix commit c74f037: AC 27 in `plan.md`, check C29 in `checks.md`, `_can_pair`/`_is_card_payment`/`_pairs(account_types)` in `services/core/app/modules/bank_sync/labels.py`, and `test_card_side_pairing` in `services/core/tests/test_transaction_labels.py`. Round 1 (full, at f55b8c7) passed 28/28. In this round every proof, C1-C29, was re-run at `HEAD` c74f037. All 29 checks are proven with a located assertion. Citations in `tests/test_transaction_labels.py` were refreshed at c74f037, because the new test moved every line after `:433` down by 35. Citations in `tests/test_transaction_labels_nightly.py` and `tests/test_migrations.py` are carried from f55b8c7: the fix did not touch those files, and their line numbers were re-checked with `rg -n` and are unchanged.

## Binding sources

Carried from f55b8c7. Step 1 is not required under `light`. The fix touched no interface, so the step was not re-run.

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| `context/specs/16-bank-transaction-labels.md` ("Done when" 1-3) | yes (round 1) - carried from f55b8c7 | none (Done 1 -> C1, Done 2 -> C7/C8, Done 3 -> C15) | - |
| `context/specs/19-forecast-recurring-payments.md` (skips card purchases and transfers between included accounts) | yes (round 1) - carried from f55b8c7 | none; AC 27 strengthens it: a card purchase can no longer be hidden inside a `card_payment` pair (C29) | - |

## Proof run

Verified at c74f037. One batched invocation was run from `services/core/`:

`uv run pytest tests/test_transaction_labels.py tests/test_transaction_labels_nightly.py tests/test_migrations.py -k "savings_to_checking_paired or across_connections_paired or money_in_first_paired or window_edges or near_misses_not_paired or pairing_order or card_purchase_labelled or card_payment_paired or card_credit_by_category or card_payment_unconnected_card or credit_draw or credit_repayment or card_beats_credit_line or card_side_pairing or in_transit_by_category or in_transit_expires or in_transit_then_paired or everything_else_normal or all_labels_consistent or constraints_refuse or every_sync_path_relabels or nightly_path_relabels or relabel_same_transaction or failed_sync_keeps_labels or removed_half_relabels or same_day_resync_unchanged or concurrent_syncs_pair or event_counts_relabeled or relabel_only_publishes or log_relabeled_no_details or transaction_labels or holidays_dependency" -v`

Result: **57 passed, 10 deselected**, exit 0. Round 1 ran 54. The difference is the 3 new `test_card_side_pairing[purchase|refund|payment]` cases. Every named test and every parametrized case appeared individually as PASSED. `-m` was not passed.

## Checks

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | savings -1,000,000 (09-14) + checking +1,000,000 (09-16): both `internal_transfer`, paired | `test_savings_to_checking_paired` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:163` - `assert_paired(rows(c.business_id), "out", "in", "internal_transfer")`; helper `:136-138` - `(found[a].label, found[b].label) == (label, label)`, `found[a].linked_transaction_id == found[b].id`, `found[b].linked_transaction_id == found[a].id` | PASS |
| C2 | across two connections: A alone `normal` unpaired, after B both paired | `test_across_connections_paired` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:174` - `assert_unpaired(rows(a.business_id), "out", "normal")`; `:177` - `assert_paired(..., "out", "in", "internal_transfer")` | PASS |
| C3 | money in (Tue 09-15) before money out (Thu 09-17): paired | `test_money_in_first_paired` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:195` - `assert_paired(rows(c.business_id), "out", "in", "internal_transfer")` | PASS |
| C4 | window edges x4 (Thanksgiving / weekend, in and out) | `test_window_edges[*]` 4 cases PASSED - verified at c74f037 | `tests/test_transaction_labels.py:198-206` param table; `:223` - `assert_paired(found, "out", "in", "internal_transfer")`; `:225-226` - `assert_unpaired(found, "out", "normal")`, `assert_unpaired(found, "in", "normal")` | PASS |
| C5 | 4 near misses (cent short, USD, same account, other business): both `normal` unpaired | `test_near_misses_not_paired[cent_short,usd,same_account,other_business]` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:257-258` - `assert_unpaired(found, "out", "normal")`, `assert_unpaired(found, "in", "normal")` | PASS |
| C6 | tie-break x3: fewest days, earliest date, lowest id; exactly 2 rows linked | `test_pairing_order[fewest_days,earliest_date,lowest_id]` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:290` - `assert_paired(found, "out", winner, "internal_transfer")`; `:291` - `assert_unpaired(found, loser, "normal")`; `:292` - `assert sum(r.linked_transaction_id is not None for r in found.values()) == 2` | PASS |
| C7 | card -8,500 unpaired: `card_purchase` | `test_card_purchase_labelled` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:305` - `assert_unpaired(rows(c.business_id), "buy", "card_purchase")` | PASS |
| C8 | checking -245,000 (10-08) + card +245,000 (10-09): `card_payment`, paired | `test_card_payment_paired` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:323` - `assert_paired(rows(c.business_id), "pay", "paid", "card_payment")` (card half has no category, the `tx` default `None`, so it passes `_is_card_payment`) | PASS |
| C9 | card +12,000 by primary category x4 | `test_card_credit_by_category[*]` 4 cases PASSED - verified at c74f037 | `tests/test_transaction_labels.py:326-334` param table (`LOAN_PAYMENTS`/`TRANSFER_IN`/`None` -> `card_payment`, `GENERAL_MERCHANDISE` -> `card_purchase`); `:349` - `assert_unpaired(rows(c.business_id), "credit", label)` | PASS |
| C10 | checking -60,000 `LOAN_PAYMENTS_CREDIT_CARD_PAYMENT`, no card: `card_payment`, unpaired | `test_card_payment_unconnected_card` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:373` - `assert_unpaired(rows(c.business_id), "pay", "card_payment")` | PASS |
| C11 | LOC -1,500,000 -> checking: `credit_draw` paired; unpaired LOC -40,000 `credit_draw` | `test_credit_draw` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:389` - `assert_paired(..., "draw", "in", "credit_draw")`; `:394` - `assert_unpaired(rows(d.business_id), "draw-2", "credit_draw")` | PASS |
| C12 | checking -700,000 -> LOC: `credit_repayment` paired; unpaired LOC +40,000 `credit_repayment` | `test_credit_repayment` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:410` - `assert_paired(..., "out", "repaid", "credit_repayment")`; `:415` - `assert_unpaired(rows(d.business_id), "repaid-2", "credit_repayment")` | PASS |
| C13 | LOC -90,000 -> card +90,000: `card_payment`, paired | `test_card_beats_credit_line` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:433` - `assert_paired(rows(c.business_id), "draw", "paid", "card_payment")` (card half category `None`) | PASS |
| C14 | checking -400,000 (Fri 10-09) by detailed category x4, nightly at 10-15T06:00Z | `test_in_transit_by_category[*]` 4 cases PASSED - verified at c74f037 | `tests/test_transaction_labels_nightly.py:149-157` param table; `:166` - `assert_unpaired(rows(bank.business_id), "out", label)` - citation carried from f55b8c7 (file untouched) | PASS |
| C15 | `in_transit` at 10-15, `normal` at 10-16, no new data | `test_in_transit_expires` PASSED - verified at c74f037 | `tests/test_transaction_labels_nightly.py:176` - `assert_unpaired(..., "out", "in_transit")`; `:179` - `assert_unpaired(..., "out", "normal")` - citation carried from f55b8c7 | PASS |
| C16 | `in_transit` at 10-13, savings +400,000 (10-14) arrives at 10-14 sync: paired | `test_in_transit_then_paired` PASSED - verified at c74f037 | `tests/test_transaction_labels_nightly.py:188` - `assert_unpaired(..., "out", "in_transit")`; `:193` - `assert_paired(rows(bank.business_id), "out", "in", "internal_transfer")` - citation carried from f55b8c7 | PASS |
| C17 | 5 unpaired checking rows: all `normal` | `test_everything_else_normal[*]` 5 cases PASSED - verified at c74f037 | `tests/test_transaction_labels.py:474-487` param table; `:511` - `assert_unpaired(rows(c.business_id), "t", "normal")` | PASS |
| C18 | all 7 labels in one business; links only on 4 labels; links mirrored | `test_all_labels_consistent` PASSED - verified at c74f037 | `tests/test_transaction_labels_nightly.py:225` - `assert {r.label for r in found} == LABELS`; `:227-232` - `linked <= {"internal_transfer", "card_payment", "credit_draw", "credit_repayment"}`; `:235` - `assert by_id[row.linked_transaction_id].linked_transaction_id == row.id` - citation carried from f55b8c7 | PASS |
| C19 | DB refuses 4 bad writes with IntegrityError naming the constraint | `test_constraints_refuse[*]` 4 cases PASSED - verified at c74f037 | `tests/test_transaction_labels.py:533-541` param table; `:552` - `pytest.raises(IntegrityError) as excinfo`; `:570` - `assert constraint in str(excinfo.value)` | PASS |
| C20 | webhook, connect and nightly paths each relabel | `test_every_sync_path_relabels[webhook,connect]` + `test_nightly_path_relabels` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:580` - `assert_unpaired(..., "in", "normal")`; `:592` - `connect(caller, business_id).status_code == 201`; `:594` - `assert_paired(rows(stored.business_id), "out", "in", "internal_transfer")`; `tests/test_transaction_labels_nightly.py:246`, `:251` (carried from f55b8c7) | PASS |
| C21 | relabelled A outflow and inserted B inflow share `xmin` | `test_relabel_same_transaction` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:617` - `assert found["out"].label == "internal_transfer"`; `:618` - `assert xmins[found["out"].id] == xmins[found["in"].id]` | PASS (precision gap carried from f55b8c7, see below) |
| C22 | failed sync (unknown account on page 2) raises; pair intact | `test_failed_sync_keeps_labels` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:640` - `with pytest.raises(PlaidError):`; `:643` - `assert_paired(rows(c.business_id), "out", "in", "internal_transfer")` | PASS |
| C23 | removed half leaves partner `normal` unpaired; posted replacement re-pairs | `test_removed_half_relabels` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:662-663` - `assert "out" not in found`, `assert_unpaired(found, "in", "normal")`; `:676` - pending pair; `:686-687` - `assert "p" not in found`, `assert_paired(found, "posted", "in-2", "internal_transfer")` | PASS |
| C24 | same-day resync: unchanged, `relabeled` 0, no event | `test_same_day_resync_unchanged` PASSED - verified at c74f037 | `tests/test_transaction_labels_nightly.py:290` - `assert [line["relabeled"] for line in synced] == [0]`; `:291` - `assert published == []`; `:292` - `assert labels_and_links(bank.business_id) == before` - citation carried from f55b8c7 | PASS |
| C25 | two concurrent syncs of one business: no exception, pair formed | `test_concurrent_syncs_pair` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:734` - `assert started == 2`; `:735` - `assert errors == []`; `:736` - `assert_paired(rows(a.business_id), "out", "in", "internal_transfer")` | PASS |
| C26 | C1's sync publishes `relabeled` 2; relabel-only sync publishes exact zero counts + `relabeled` 1 | `test_event_counts_relabeled` + `test_relabel_only_publishes` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:778-791` - `assert published == [events.Event(name="transactions.synced", ..., payload={"connection_id": ..., "added": 2, "modified": 0, "removed": 0, "balances_changed": False, "relabeled": 2})]`; `tests/test_transaction_labels_nightly.py:320-333` (carried from f55b8c7) - same exact-list assertion with `"relabeled": 1` | PASS |
| C27 | `bank_sync.synced` has `relabeled` 2; no description, counterparty, or `10000` in logs | `test_log_relabeled_no_details` PASSED - verified at c74f037 | `tests/test_transaction_labels.py:831` - `assert [line["relabeled"] for line in synced] == [2]`; `:832-838` - `assert [v for v in leaks if v in logs] == []` over the two descriptions, `"Reserve Account"`, `"10000"` | PASS |
| C28 | migration: existing row `normal`/null; downgrade drops both; `holidays` in pyproject + lock | `test_transaction_labels_upgrade_downgrade_and_check` + `test_holidays_dependency` PASSED - verified at c74f037 | `tests/test_migrations.py:669` - `assert tuple(existing) == ("normal", None)`; `:680` - `assert remaining.isdisjoint({"label", "linked_transaction_id"})` (carried from f55b8c7); `tests/test_transaction_labels.py:851-852` - `assert "holidays" in names`, `assert "holidays" in locked` | PASS |
| C29 | card-side pairing x3: card -50,000 `GENERAL_MERCHANDISE` vs checking +50,000 `INCOME` -> `card_purchase` / `normal` unpaired; card +30,000 `GENERAL_MERCHANDISE` vs checking -30,000 `GENERAL_SERVICES` -> `card_purchase` / `normal` unpaired; card +30,000 `LOAN_PAYMENTS` (09-15) vs checking -30,000 (09-14) -> both `card_payment`, paired | `test_card_side_pairing[purchase,refund,payment]` PASSED - verified at c74f037 (new in c74f037) | `tests/test_transaction_labels.py:436` - `@pytest.mark.parametrize("case", ["purchase", "refund", "payment"])`; inputs `:443-446` (purchase), `:450-453` (refund), `:457-458` (payment); `:465` - `assert_paired(found, "cash", "card", "card_payment")` (payment); `:467` - `assert_unpaired(found, "card", "card_purchase")` and `:468` - `assert_unpaired(found, "cash", "normal")` (purchase, refund). `assert_unpaired` (`:142`) asserts `(label, linked_transaction_id) == (label, None)`, so "unpaired" is asserted, not just the label | PASS |

## Effect of the `labels.py` change on earlier checks

Verified at c74f037. The change is confined to `_pairs`. A candidate pair is now refused when the money-out half is on a `credit_card` account, or when the money-in half is on a card and is not a payment. `_is_card_payment` (`services/core/app/modules/bank_sync/labels.py:80-84`) is the old inline condition from `_unpaired_label`, extracted without change, and `_unpaired_label` now calls it (`:107`). The gate is applied at `labels.py:146`, and `account_types` is threaded through `label_all` at `:185`. `_pairs` and `_can_pair` have no other callers (`rg -n "_pairs\(|_can_pair" app/`).

- **C1-C6 (pairing between cash accounts):** no card account takes part, so `_can_pair` reduces to the old `out.account_id == incoming.account_id` test (`labels.py:93`). The behaviour is unchanged, and all 15 cases re-ran green.
- **C7, C9, C10 (unpaired card rules):** `_unpaired_label` is logically identical. The extracted predicate is the same expression. Green.
- **C8 and C13 (cash or credit line -> card):** the card half is money in and has no category (the `tx` default is `None`), so it passes `_is_card_payment` and the pair is still formed. Green.
- **C11 and C12 (credit line <-> cash):** no card is involved. Unchanged. Green.
- **C18 (all 7 labels):** the fixture's card rows are an unpaired purchase (-8,500) and an uncategorised +245,000 payment (`tests/test_transaction_labels_nightly.py:209`, `:211`). Both still get the same labels. Green.
- **C14-C17 and C19-C28:** these checks do not involve cards, or they exercise sync plumbing that is unaffected. Green.

## Level and sampling

- Every table-driven claim is proven on its full stated set: C4 4/4, C5 4/4, C6 3/3, C9 4/4, C14 4/4, C17 5/5, C19 4/4, C20 3/3, and C29 3/3 (new). (Carried from f55b8c7, and re-confirmed by the case list of the c74f037 run.)
- Boundaries are proven on both sides of the edge (C4, C14/C15). Carried from f55b8c7.
- No route changes, so there are no status-code rows. C20's connect path crosses the HTTP boundary (`tests/test_transaction_labels.py:592`).
- **Precision gap (C21, AC 19) - carried from f55b8c7.** The `xmin` assertion (`tests/test_transaction_labels.py:618`) cannot tell "relabelled in the sync's own transaction" apart from "relabelled in a second transaction after commit". In C2's second sync, the relabel rewrites both rows, so they share the relabelling transaction's `xmin` whichever transaction that is. To discriminate, the check would need to compare against a row that only the sync's own transaction writes, such as the connection row after the cursor update. The literal claim holds. By code reading, `_relabel` runs inside `_sync_locked`, before the caller commits. Lesson L-022 already records this gap, so no new lesson is needed.
- **Minor sampling note (C6, AC 6) - carried from f55b8c7.** The tie-break is exercised only for one outflow with several candidate inflows, never for one inflow with several candidate outflows. The sort key (`labels.py:153-164`, `candidates.sort(key=lambda c: c[:5])` over `(apart, out.date, incoming.date, out.id, incoming.id)`) covers both directions. Non-failing.
- **Minor sampling note (AC 27 / C29) - new at c74f037, non-failing.** AC 27 allows a money-in card half to pair when its primary category is absent, `LOAN_PAYMENTS` or `TRANSFER_IN`. Pairing is proven for absent (C8, C13) and `LOAN_PAYMENTS` (C29 `payment`). No test pairs a card half categorised `TRANSFER_IN`. C9 proves `TRANSFER_IN` only for the unpaired label. The refused side is proven with one non-payment category (`GENERAL_MERCHANDISE`) and one counter-account type (checking). A card money-out half against a credit line money-in half (also refused under AC 27, and formerly a `card_payment` pair) has no case. Both gaps go through the same `_can_pair` branches that are proven, and every stated claim of C29 is fully proven, so neither is a finding against the checks.

## Swept (existing behaviour re-read)

Carried from f55b8c7. The fix touched none of the code these rows cite (`repository.py`, `service.py`):

- authorization: `repository.business_transactions` filters by `business_id` (`services/core/app/modules/bank_sync/repository.py:152-166`). Confirmed in round 1.
- concurrency, door 3: `repository.lock_accounts` (`ORDER BY id ... FOR UPDATE`, `repository.py:82-95`) is called before `_apply`. Confirmed in round 1. The lock is taken after the Plaid fetch, which is disclosed in the Handoff of `checks.md`.
- dependency failure `n/a`: approved policy.

## Coverage

Not recomputed: under `light`, the Coverage join is not recomputed. The new row in `checks.md`, "card halves refused a pair (2)", resolves to C29's `purchase` (money-out card half) and `refund` (money-in card half with a non-payment category), and both are proven above.

## Faults injected

None: under `light`, fault injection does not run. No mutant was run against the new `_can_pair` branches.

## Gate

Verified at c74f037, from `services/core`:

- `uv run ruff format --check .` - 70 files already formatted
- `uv run ruff check .` - All checks passed
- `uv run mypy app` - Success: no issues found in 32 source files
- `uv run pytest -q` - **422 passed, 3 deselected**, 0 failed (2 warnings). Round 1 had 419 passed; the 3 new cases are C29's.

## Notes (outside the checks)

- Round 1's note is resolved at c74f037. That note said a card purchase (-X on the card) and an unrelated +X deposit on checking within 3 business days became a `card_payment` pair. AC 27 now refuses this pair, and C29 `purchase` proves the refusal.
