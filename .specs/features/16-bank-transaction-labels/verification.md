# 16 - Transaction labels verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 06fe8df..f55b8c7b8ba47922c142e5511897956caca3a3f2
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

All 28 checks are proven at `HEAD` with a located assertion. One precision gap (C21) and two minor notes are recorded below. None of them changes a check's result.

## Binding sources

Under `light`, step 1 (checking the checks against binding sources) is not required. Both binding sources were still opened and read. Nothing in them contradicts the checks.

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| `context/specs/16-bank-transaction-labels.md` ("Done when" 1-3) | yes | none (Done 1 -> C1, Done 2 -> C7/C8, Done 3 -> C15) | - |
| `context/specs/19-forecast-recurring-payments.md` (skips card purchases and transfers between included accounts) | yes | none (labels `card_purchase` C7 and `internal_transfer` C1 exist for it to branch on) | - |

## Proof run

There was one batched invocation from `services/core/` at `HEAD` f55b8c7:

`uv run pytest tests/test_transaction_labels.py tests/test_transaction_labels_nightly.py tests/test_migrations.py -k "<all 31 proof names joined with or>" -v`. The result was **54 passed, 10 deselected**, exit 0. Every named test (and every parametrized case) appeared individually as PASSED. All proof tests are new in the diff range, in `tests/test_transaction_labels.py`, `tests/test_transaction_labels_nightly.py` and `tests/test_migrations.py:624`.

## Checks

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | savings -1,000,000 (09-14) + checking +1,000,000 (09-16): both `internal_transfer`, paired | `test_savings_to_checking_paired` PASSED | `tests/test_transaction_labels.py:163` - `assert_paired(rows(c.business_id), "out", "in", "internal_transfer")`; helper `:136-138` - `(found[a].label, found[b].label) == (label, label)`, `found[a].linked_transaction_id == found[b].id`, `found[b].linked_transaction_id == found[a].id` | PASS |
| C2 | across two connections: A alone `normal` unpaired, after B both paired | `test_across_connections_paired` PASSED | `tests/test_transaction_labels.py:174` - `assert_unpaired(rows(a.business_id), "out", "normal")`; `:177` - `assert_paired(..., "out", "in", "internal_transfer")` | PASS |
| C3 | money in (Tue 09-15) before money out (Thu 09-17): paired | `test_money_in_first_paired` PASSED | `tests/test_transaction_labels.py:195` - `assert_paired(rows(c.business_id), "out", "in", "internal_transfer")` (dates `:190-191`) | PASS |
| C4 | window edges x4 (Thanksgiving / weekend, in and out) | `test_window_edges[*]` 4 cases PASSED | `tests/test_transaction_labels.py:201-204` param table; `:223` - `assert_paired(found, "out", "in", "internal_transfer")`; `:225-226` - `assert_unpaired(found, "out", "normal")`, `assert_unpaired(found, "in", "normal")` | PASS |
| C5 | 4 near misses (cent short, USD, same account, other business): both `normal` unpaired | `test_near_misses_not_paired[cent_short,usd,same_account,other_business]` PASSED | `tests/test_transaction_labels.py:257-258` - `assert_unpaired(found, "out", "normal")`, `assert_unpaired(found, "in", "normal")`; cases `:240`, `:242` (`iso="USD"`), `:244`, `:246-247` | PASS |
| C6 | tie-break x3: fewest days, earliest date, lowest id; exactly 2 rows linked | `test_pairing_order[fewest_days,earliest_date,lowest_id]` PASSED | `tests/test_transaction_labels.py:290` - `assert_paired(found, "out", winner, "internal_transfer")`; `:291` - `assert_unpaired(found, loser, "normal")`; `:292` - `assert sum(r.linked_transaction_id is not None for r in found.values()) == 2`; winner `:286` - `min(("a", "b"), key=lambda name: found[name].id)` | PASS |
| C7 | card -8,500 unpaired: `card_purchase` | `test_card_purchase_labelled` PASSED | `tests/test_transaction_labels.py:305` - `assert_unpaired(rows(c.business_id), "buy", "card_purchase")` | PASS |
| C8 | checking -245,000 (10-08) + card +245,000 (10-09): `card_payment`, paired | `test_card_payment_paired` PASSED | `tests/test_transaction_labels.py:323` - `assert_paired(rows(c.business_id), "pay", "paid", "card_payment")` | PASS |
| C9 | card +12,000 by primary category x4 | `test_card_credit_by_category[*]` 4 cases PASSED | `tests/test_transaction_labels.py:329-332` param table (`LOAN_PAYMENTS`/`TRANSFER_IN`/`None` -> `card_payment`, `GENERAL_MERCHANDISE` -> `card_purchase`); `:349` - `assert_unpaired(rows(c.business_id), "credit", label)` | PASS |
| C10 | checking -60,000 `LOAN_PAYMENTS_CREDIT_CARD_PAYMENT`, no card: `card_payment`, unpaired | `test_card_payment_unconnected_card` PASSED | `tests/test_transaction_labels.py:373` - `assert_unpaired(rows(c.business_id), "pay", "card_payment")` (detailed category `:368`, business has only checking `:355`) | PASS |
| C11 | LOC -1,500,000 -> checking: `credit_draw` paired; unpaired LOC -40,000 `credit_draw` | `test_credit_draw` PASSED | `tests/test_transaction_labels.py:389` - `assert_paired(..., "draw", "in", "credit_draw")`; `:394` - `assert_unpaired(rows(d.business_id), "draw-2", "credit_draw")` | PASS |
| C12 | checking -700,000 -> LOC: `credit_repayment` paired; unpaired LOC +40,000 `credit_repayment` | `test_credit_repayment` PASSED | `tests/test_transaction_labels.py:410` - `assert_paired(..., "out", "repaid", "credit_repayment")`; `:415` - `assert_unpaired(rows(d.business_id), "repaid-2", "credit_repayment")` | PASS |
| C13 | LOC -90,000 -> card +90,000: `card_payment`, paired | `test_card_beats_credit_line` PASSED | `tests/test_transaction_labels.py:433` - `assert_paired(rows(c.business_id), "draw", "paid", "card_payment")` | PASS |
| C14 | checking -400,000 (Fri 10-09) by detailed category x4, nightly at 10-15T06:00Z | `test_in_transit_by_category[*]` 4 cases PASSED | `tests/test_transaction_labels_nightly.py:152-155` param table; `:164` - `night(fake, date(2026, 10, 15))`; `:166` - `assert_unpaired(rows(bank.business_id), "out", label)` | PASS |
| C15 | `in_transit` at 10-15, `normal` at 10-16, no new data | `test_in_transit_expires` PASSED | `tests/test_transaction_labels_nightly.py:176` - `assert_unpaired(rows(bank.business_id), "out", "in_transit")`; `:179` - `assert_unpaired(rows(bank.business_id), "out", "normal")` | PASS |
| C16 | `in_transit` at 10-13, savings +400,000 (10-14) arrives at 10-14 sync: paired | `test_in_transit_then_paired` PASSED | `tests/test_transaction_labels_nightly.py:188` - `assert_unpaired(..., "out", "in_transit")`; `:193` - `assert_paired(rows(bank.business_id), "out", "in", "internal_transfer")` | PASS |
| C17 | 5 unpaired checking rows: all `normal` | `test_everything_else_normal[*]` 5 cases PASSED | `tests/test_transaction_labels.py:442-450` param table; `:476` - `assert_unpaired(rows(c.business_id), "t", "normal")` | PASS |
| C18 | all 7 labels in one business; links only on 4 labels; links mirrored | `test_all_labels_consistent` PASSED | `tests/test_transaction_labels_nightly.py:225` - `assert {r.label for r in found} == LABELS` (stronger than the claim: all 7 present); `:227-232` - `linked <= {"internal_transfer", "card_payment", "credit_draw", "credit_repayment"}`; `:235` - `assert by_id[row.linked_transaction_id].linked_transaction_id == row.id` | PASS |
| C19 | DB refuses 4 bad writes with IntegrityError naming the constraint | `test_constraints_refuse[*]` 4 cases PASSED | `tests/test_transaction_labels.py:501-504` param table; `:517` - `pytest.raises(IntegrityError)`; `:535` - `assert constraint in str(excinfo.value)` | PASS |
| C20 | webhook, connect and nightly paths each relabel | `test_every_sync_path_relabels[webhook,connect]` + `test_nightly_path_relabels` PASSED | `tests/test_transaction_labels.py:545` - `assert_unpaired(..., "in", "normal")`; `:557` - `connect(caller, business_id).status_code == 201`; `:559` - `assert_paired(rows(stored.business_id), "out", "in", "internal_transfer")`; `tests/test_transaction_labels_nightly.py:246`, `:251` - same pair of assertions on the nightly path | PASS |
| C21 | relabelled A outflow and inserted B inflow share `xmin` | `test_relabel_same_transaction` PASSED | `tests/test_transaction_labels.py:582` - `assert found["out"].label == "internal_transfer"`; `:583` - `assert xmins[found["out"].id] == xmins[found["in"].id]` | PASS (precision gap, see below) |
| C22 | failed sync (unknown account on page 2) raises; pair intact | `test_failed_sync_keeps_labels` PASSED | `tests/test_transaction_labels.py:605` - `with pytest.raises(PlaidError):`; `:608` - `assert_paired(rows(c.business_id), "out", "in", "internal_transfer")` | PASS |
| C23 | removed half leaves partner `normal` unpaired; posted replacement re-pairs | `test_removed_half_relabels` PASSED | `tests/test_transaction_labels.py:627-628` - `assert "out" not in found`, `assert_unpaired(found, "in", "normal")`; `:641` - pending pair; `:651-652` - `assert "p" not in found`, `assert_paired(found, "posted", "in-2", "internal_transfer")` | PASS |
| C24 | same-day resync: unchanged, `relabeled` 0, no event | `test_same_day_resync_unchanged` PASSED | `tests/test_transaction_labels_nightly.py:290` - `assert [line["relabeled"] for line in synced] == [0]`; `:291` - `assert published == []`; `:292` - `assert labels_and_links(bank.business_id) == before`; `:293` - `before["out"][0] == "internal_transfer"` | PASS |
| C25 | two concurrent syncs of one business: no exception, pair formed | `test_concurrent_syncs_pair` PASSED | `tests/test_transaction_labels.py:699` - `assert started == 2` (B's Plaid call started while A was held); `:700` - `assert errors == []`; `:701` - `assert_paired(rows(a.business_id), "out", "in", "internal_transfer")` | PASS |
| C26 | C1's sync publishes `relabeled` 2; relabel-only sync publishes exact zero counts + `relabeled` 1 | `test_event_counts_relabeled` + `test_relabel_only_publishes` PASSED | `tests/test_transaction_labels.py:743-756` - `assert published == [events.Event(name="transactions.synced", ..., payload={"connection_id": ..., "added": 2, "modified": 0, "removed": 0, "balances_changed": False, "relabeled": 2})]`; `tests/test_transaction_labels_nightly.py:320-333` - same exact-list assertion with `added/modified/removed` 0, `balances_changed` False, `"relabeled": 1` | PASS |
| C27 | `bank_sync.synced` has `relabeled` 2; no description, counterparty, or `10000` in logs | `test_log_relabeled_no_details` PASSED | `tests/test_transaction_labels.py:796` - `assert [line["relabeled"] for line in synced] == [2]`; `:797-803` - `assert [v for v in leaks if v in logs] == []` over the two descriptions, `"Reserve Account"`, `"10000"` | PASS |
| C28 | migration: existing row `normal`/null; downgrade drops both; `holidays` in pyproject + lock | `test_transaction_labels_upgrade_downgrade_and_check` + `test_holidays_dependency` PASSED | `tests/test_migrations.py:669` - `assert tuple(existing) == ("normal", None)`; `:680` - `assert remaining.isdisjoint({"label", "linked_transaction_id"})`; `tests/test_transaction_labels.py:816-817` - `assert "holidays" in names`, `assert "holidays" in locked` | PASS |

## Level and sampling

- Every table-driven claim is proven on its full stated set: C4 4/4, C5 4/4, C6 3/3, C9 4/4, C14 4/4, C17 5/5, C19 4/4, C20 3/3 (two files). No claim about N cases is proven on fewer.
- Boundaries are proven on both sides of the edge, not below it: C4 (last day in the window, then the next business day, for both holiday and weekend), and C14/C15 (`today == date + 3 business days` gives `in_transit`, the next business day gives `normal`).
- No route changes, so there are no status-code rows. C20's connect path crosses the HTTP boundary (`status_code == 201`, `tests/test_transaction_labels.py:557`).
- **Precision gap (C21, AC 19).** The `xmin` assertion cannot tell "relabelled in the sync's own transaction" apart from the rejected alternative: "relabelled in a second transaction after commit" (door 3's rejected `transactions.synced` handler). In C2's second sync, the relabel rewrites both the A outflow and the B inflow, so both rows get the relabelling transaction's `xmin` whichever transaction that is. Equal `xmin` therefore proves only that both rows were last written together. To discriminate, the check would need to compare against a row that only the sync's own transaction writes, such as the connection's `xmin` after the cursor update, or would need to observe that no committed state exists with the inflow stored and still `normal`. The literal claim holds. By code reading, the behaviour AC 19 demands is present: `services/core/app/modules/bank_sync/service.py:619` calls `_relabel` inside `_sync_locked`, before the caller's `session.commit()` at `:682` (and inside the nightly savepoint at `:802`). That is reading, not a proof. Because `light` runs no fault injection, no mutant was run against C21.
- **Minor sampling note (C6, AC 6).** The tie-break is exercised only for one outflow with several candidate inflows, never for one inflow with several candidate outflows. The code's sort key (`labels.py:140`, `(apart, out.date, incoming.date, out.id, incoming.id)`) covers both directions. This note is non-failing: C6's stated claim is fully proven.

## Swept (existing behaviour re-read)

- authorization, "every sync is already scoped by `business_id` (spec 14)": confirmed. `repository.business_transactions` filters `BankTransaction.business_id == business_id` (`services/core/app/modules/bank_sync/repository.py:152-166`). `repository.accounts` filters by `business_id` (`:72-79`). `_relabel` takes `connection.business_id` (`service.py:619`).
- concurrency, door 3, which extends AD-046's existing connection lock: `repository.lock_accounts` exists with `ORDER BY id ... FOR UPDATE` (`repository.py:82-95`). `_sync_locked` calls it before `_apply` (`service.py:617-618`). `update_account` takes only the account lock (`service.py:357`), so no lock-order inversion exists. **Note:** the plan's Landing row for door 3 says "right after the connection lock". The build takes the lock after the Plaid pages are fetched but still before any write, which preserves the stated lock order (connection, then accounts). The deviation is disclosed in checks.md's Handoff, C25 depends on it, and it does not weaken the door.
- dependency failure `n/a`: approved policy, so there is nothing to check in code.

## Coverage

Not recomputed: under `light`, the Coverage join is not recomputed, and the table in `checks.md` was read as the author's self-report. All of its members do resolve to a check proven above.

## Faults injected

None: under `light`, fault injection does not run.

## Gate

From `services/core`, at f55b8c7:

- `uv run ruff format --check .` - 70 files already formatted
- `uv run ruff check .` - All checks passed
- `uv run mypy app` - Success: no issues found in 32 source files
- `uv run pytest -q` - **419 passed, 3 deselected**, 0 failed (2 warnings)

## Notes (outside the checks)

- `labels._pairs` pairs by amount, currency, account and window regardless of direction-by-type. As a result, a card purchase (-X on the card) and an unrelated +X deposit on checking within 3 business days become a `card_payment` pair. This is consistent with the approved plan (AC 1, 5, 13 and the "matching uses amount, currency, account, and date only" assumption), so it is not a check finding. It may matter to spec 21, because it would hide real income.
