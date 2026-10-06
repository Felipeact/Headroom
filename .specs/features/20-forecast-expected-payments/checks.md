# 20 - Expected payments checks

Profile: light
Plan: `.specs/features/20-forecast-expected-payments/plan.md`

48 checks in 6 slices · 4 one-way doors · 0 open

- **Commands:** API commands run from `services/core/` (`uv run pytest ...`), and web commands from `frontend/` (`npx vitest run ...`, `npx playwright test ...`). Commands that are more than one test live in `.specs/features/20-forecast-expected-payments/proofs.sh` (`bash proofs.sh c<n>`).
- **"A business with a bank":** a business whose included accounts were stored through `bank_sync.service.connect_bank` with spec 12's fake Plaid client:
  - Operating (checking, `CAD`, included, primary)
  - Reserve (savings, `CAD`, included)
  - Visa (credit card, not included)

  "The owner" calls the routes through `TestClient` with a signed token (spec 10 helpers). "Today" is fixed by patching the service's clock to 2026-10-06 12:00 in `America/Toronto`, unless a check says otherwise.
- **"A valid body":** `{"description": "Acme Co, invoice 1042", "amount_cents": 800000, "date": "2026-10-20", "repeats": null}`.
- **Matching tests (S2, S3):**
  - The pure tests call the matcher with value objects: payments with `id`, `created_at`, `amount_cents`, `currency`, `date` and `repeats`, and transactions with `id`, `date`, `amount_cents`, `currency`, `pending` and `label`. Each transaction is `normal`, not pending and `CAD` unless the check says otherwise.
  - The stored tests write transactions through `bank_sync.service.sync_connection` with spec 14's `SyncFake`, after `subscriptions.register()`, so the handlers run as they do in the app.

## Checks

### S1 - The owner creates, edits, deletes and lists expected payments through the API · 9 files · 150 KB · ~38k

**C1** - The owner `POST`s a valid body with `account_id` = Reserve. The response is `201` with keys exactly `id`, `account_id`, `description`, `amount_cents`, `currency`, `date`, `repeats`, `next_date`, `overdue`, where:
- `account_id` = Reserve
- `amount_cents` = 800000
- `currency` = `CAD`
- `next_date` = "2026-10-20"
- `overdue` = false

One `expected_payments` row exists with those values (AC 1, door 3)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "create_returns_payment"`

**C2** - The owner `POST`s a valid body with no `account_id`. The response's `account_id` is Operating, the primary account (AC 2)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "defaults_to_primary"`

**C3** - Table-driven over 4 `account_id` values. Each gets `409` `application/problem+json` with detail "Choose an account you count as cash.", and no row is stored:
- Visa (credit, not included)
- Reserve after `PATCH`ing it to `included: false`
- an account of a second business
- a random UUID

(AC 3)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "account_not_cash"`

**C4** - A business with no bank connected `POST`s a valid body with no `account_id`. It gets `409` with detail "Connect a bank before adding expected payments.", and no row is stored (AC 4)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "no_primary_account"`

**C5** - Body bounds, table-driven, with today 2026-10-06. Each rejected case gets `422` `application/problem+json` and stores nothing.

| Field | Accepted (`201`) | Rejected (`422`) |
| --- | --- | --- |
| `description` | "  A  " (stored as "A"); 100 characters | "   "; 101 characters after trimming |
| `amount_cents` | 1; -1; 9999999999; -9999999999 | 0; 10000000000; -10000000000; 1.5 |
| `date` | "2026-07-08" (today - 90); "2028-10-05" (today + 730) | "2026-07-07"; "2028-10-06" |
| `repeats` | null; `weekly`; `biweekly`; `monthly`; `quarterly` | "semimonthly"; "yearly" |
| extra field | - | `"direction": "in"` |

(AC 5)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "body_bounds"`

**C6** - After creating a payment, the owner `PUT`s `{"account_id": Reserve, "description": "Acme Co, invoice 1042 (revised)", "amount_cents": -250000, "date": "2026-11-02", "repeats": "monthly"}`. The response is `200` with those values and the same `id`, and the row's `created_at` is unchanged. A `PUT` with `amount_cents` 0 gets `422`, and one with `account_id` = Visa gets `409`. Neither changes the row (AC 6)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "update_payment"`

**C7** - `DELETE` on a payment that has 1 stored match answers `204` with an empty body. Afterwards neither the `expected_payments` row nor its `expected_payment_matches` row exists (AC 7)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "delete_payment"`

**C8** - `PUT` and `DELETE` on a random UUID, and on a payment of a second business called through the first business's path, each answer `404` with detail "Expected payment not found.". The second business's payment is unchanged (AC 8)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "payment_not_found"`

**C9** - The business holds these payments:
- one-off "Bravo" on 2026-10-20
- one-off "Alpha" on 2026-10-20
- one-off "Late" on 2026-09-01, unmatched
- one-off "Paid" on 2026-10-01, matched
- monthly "Rent" from 2026-08-15, with no matches

`GET .../expected-payments` answers `200` with keys exactly `items`. The items are, in order:
- "Late" (`next_date` "2026-09-01", `overdue` true)
- "Rent" (`next_date` "2026-10-15", `overdue` false). Aug 15 and Sep 15 are past their late window, and Oct 15 is the first that isn't.
- "Alpha" (2026-10-20)
- "Bravo" (2026-10-20)

"Paid" is absent. A business with no payments gets `{"items": []}` (AC 9, AC 20)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "list_upcoming_only"`

**C10** - Access denied, table-driven over the 4 routes:
- a signed-in user who is not a member gets `404` "Business not found."
- with `accounts.service.get_membership` patched to role `viewer`, the owner gets `403` "You don't have permission to do this."

The owner of business A, with payments stored in A and in B, lists only A's IDs (AC 10)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "access_denied"`

**C11** - `GET` with `business_id` "not-a-uuid", and `PUT` and `DELETE` with `payment_id` "not-a-uuid", answer `422` `application/problem+json` (AC 11)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "invalid_ids"`

**C12** - A create, an update and a delete each write exactly one `audit_log` row:
- the `action` values are `expected_payment.created`, `expected_payment.updated` and `expected_payment.deleted`
- `target_type` is `expected_payment`, and `target_id` is the payment's ID
- no row's `details` contains the description or the amount

A `422` request writes no audit row (AC 12)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "audited"`

**C13** - The `expected_payments` table refuses bad rows. Table-driven over 2 inserts that each raise `IntegrityError` naming the constraint:
- `amount_cents` 0 -> `ck_expected_payments_amount_nonzero`
- `repeats` "yearly" -> `ck_expected_payments_repeats`

Rows with `repeats` null and with `quarterly` are accepted (door 1)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "payment_constraints"`

**C14** - The `expected_payment_matches` table refuses a second row with the same `transaction_id`, raising `IntegrityError` naming `uq_expected_payment_matches_transaction_id`. It also refuses a second row with the same `(expected_payment_id, occurrence_date)`. Deleting the payment deletes its matches (door 2)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "match_constraints"`

**C15** - The migration:
- upgrades from spec 19's head and creates both tables
- downgrades to spec 19's head, leaving neither table
- upgrades again

`alembic check` then finds no difference between the models and the database (doors 1, 2)
Proof: `uv run pytest tests/test_migrations.py -k "expected_payments_upgrade_downgrade_and_check"`

**C16** - Regenerating `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` leaves no diff. The contract has `get` and `post` on `/v1/businesses/{business_id}/expected-payments`, and `put` and `delete` on `/v1/businesses/{business_id}/expected-payments/{payment_id}` (door 3)
Proof: `bash .specs/features/20-forecast-expected-payments/proofs.sh c16`

### S2 - Real transactions are matched to expected payments · 3 files · 40 KB · ~10k

**C17** - Occurrences, table-driven over 6 payments (dates up to 2027-06-30):
- one-off 2026-10-06 -> [2026-10-06]
- `weekly` from 2026-10-06 -> 10-06, 10-13, 10-20, ...
- `biweekly` from 2026-10-06 -> 10-06, 10-20, 11-03, ...
- `monthly` from 2027-01-31 -> 2027-01-31, 02-28, 03-31, 04-30
- `monthly` from 2028-01-31 -> 2028-02-29 is second
- `quarterly` from 2026-11-30 -> 2026-11-30, 2027-02-28, 2027-05-30

(AC 13)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "occurrences"`

**C18** - Candidate edges, table-driven, against a one-off of +100000 on 2026-10-06. Each row is one transaction and whether it matches:

| Field | Matches | Does not match |
| --- | --- | --- |
| amount | 90000; 110000 | 89999; 110001; -100000 |
| date | 2026-09-29 (-7 days); 2026-10-20 (+14 days) | 2026-09-28; 2026-10-21 |
| label | `normal` pending; `normal` posted | `internal_transfer`; `card_payment` |
| currency | `CAD` | `USD` |

For a payment of -100000, -110000 matches and +100000 does not (AC 14)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "candidate_edges"`

**C19** - Assignment, over 4 cases:
- Two one-offs of +100000 on 2026-10-06, created 1 second apart, and one transaction of +100000 on 2026-10-07: only the earlier-created payment is matched.
- One one-off of +100000 on 2026-10-06 and two transactions, +104000 on 10-06 and +100000 on 10-10: the +100000 one is matched (smaller amount difference).
- One one-off, and two transactions with the same amount on 10-04 and 10-07: the 10-07 one is matched (1 day away, against 2).
- One one-off, and two identical transactions on 10-06: the smaller `id` is matched.

No transaction ID appears in two matches (AC 15)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "assignment_order"`

**C20** - The C17, C18 and C19 inputs together, shuffled with `random.Random(n)` for n in 0..4, give the same matches as the unshuffled input. With `datetime.now` patched to 2030-01-01, the matches are unchanged (AC 16)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "order_and_clock_free"`

**C21** - A business with a one-off of +800000 on 2026-10-06 syncs a pending +800000 on 2026-10-07: 1 match, holding the pending transaction's ID. A second sync removes the pending transaction and adds the posted one on 2026-10-08: 1 match, holding the posted ID. A third sync removes the posted one: 0 matches, and the payment is back on the list. A second business's planted match is unchanged throughout (AC 17)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "sync_rematches"`

**C22** - A business already holds a synced +800000 on 2026-10-05. The owner `POST`s a one-off of +800000 on 2026-10-06, and the response's payment already has 1 match: it is absent from the list. `PUT`ting it to +500000 removes the match, and it is listed again (AC 18)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "write_rematches"`

**C23** - Calling `match_expected_payments` twice with the same `Event` leaves the same `(expected_payment_id, occurrence_date, transaction_id)` set as after the first call (AC 19)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "same_event_twice"`

**C24** - The matcher is patched to sleep 0.5 seconds, and the test also sleeps after the first write. Two threads then run `match_expected_payments` for the same business at the same time, and so do a thread running it and a thread `POST`ing a payment. Both pairs return. The business ends with exactly the matches the matcher returns for its final payments and transactions, with no duplicate `transaction_id` and no `IntegrityError` (AC 19)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "concurrent_writes"`

**C25** - `next_date` and `overdue`, table-driven with today 2026-10-20:
- a monthly from 2026-09-01, with no match -> 2026-11-01, not overdue (the Sep 1 and Oct 1 windows closed on Sep 15 and Oct 15)
- a monthly from 2026-09-10 -> 2026-10-10, overdue (its window closes on Oct 24)
- a weekly from 2026-10-01 with its 10-08 occurrence matched -> 2026-10-15, overdue (the 10-01 window closed on 10-15; 10-08 is skipped as matched)
- a one-off on 2026-09-01, unmatched -> 2026-09-01, overdue
- a one-off on 2026-10-20 -> not overdue
- a one-off on 2026-10-06, matched -> absent from the list

(AC 20)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "next_date_rules"`

**C26** - The matcher is patched to raise `RuntimeError`. A sync that adds transactions still commits them. The business keeps exactly its earlier match rows, and one `event.handler_failed` log line names `match_expected_payments` and `error_type` `RuntimeError` (AC 21)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "failure_keeps_matches"`

**C27** - A sync that leaves 1 match writes exactly one `expected_payments.matched` JSON log line, with `business_id` and `matches` 1. No log line of the sync or of a `POST` contains the payment's description, the transaction's description or counterparty, or the amount (AC 22)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "matched_logged"`

### S3 - A matched payment is counted only once · 2 files · 30 KB · ~8k

**C28** - The business holds:
- a one-off "Acme" +800000 on 2026-10-06
- a quarterly "Coastal" -1450000 from 2026-11-12
- a one-off "Overdue" +100000 on 2026-08-01, unmatched
- a weekly "Old" from 2026-01-05

`open_occurrences(today=2026-10-06, until=2027-03-31)` returns:
- Acme's 2026-10-06
- Coastal's 2026-11-12 and 2027-02-12
- Overdue's 2026-08-01
- Old's occurrences from 2026-09-28 to 2027-03-29. Its earlier ones are past their late window.

Each occurrence carries its payment's `id`, `account_id`, `description`, `amount_cents`, `currency` and the date. Nothing dated after `until` is returned (AC 23)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "open_occurrences"`

**C29** - Same business. A sync adds +790000 on 2026-10-09 and -1450000 on 2026-11-13. Afterwards:
- Acme is absent from `open_occurrences` and from the list.
- Coastal's 2026-11-12 is absent, and its 2027-02-12 is still returned.
- The sum of the `amount_cents` that `open_occurrences` returns is the earlier sum - 800000 + 1450000.

(AC 24, spec 20 "Done when" 2)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "matched_counted_once"`

### S4 - Changes tell the forecast to recompute · 2 files · 25 KB · ~6k

**C30** - A recording handler is subscribed to `forecast_inputs.changed`. A successful `POST`, `PUT` and `DELETE` each record exactly one event, with:
- `business_id` = the business
- payload exactly `{"source": "expected_payments", "expected_payment_id": <id>}`

When the handler runs, the change is already readable from a new session (published after commit) (AC 25, door 4)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "event_after_commit"`

**C31** - A `409` `POST`, a `422` `POST`, a `404` `PUT` and a `404` `DELETE` record no `forecast_inputs.changed` (AC 25)
Proof: `uv run pytest tests/test_expected_payments_api.py -k "event_not_on_failure"`

**C32** - A sync that creates a match records no `forecast_inputs.changed`. `app.subscriptions.SUBSCRIPTIONS[:2]` are:
- `("transactions.synced", refresh_recurring_patterns)`
- `("transactions.synced", match_expected_payments)`

(AC 26, door 2)
Proof: `uv run pytest tests/test_expected_payment_matching.py -k "subscribed_second"`

### S5 - The sample business has the mockup's expected payments · 3 files · 50 KB · ~13k

**C33** - After `app.fixtures.load.main(["harbor_street", "--seed", "0", ...])`, the owner's list holds exactly these 4 payments, all on the Operating checking account ID:

| Description | `amount_cents` | `date` | `repeats` |
| --- | --- | --- | --- |
| "Acme Co, invoice 1042" | 800000 | 2026-10-06 | null |
| "Coastal Supply Co, quarterly order" | -1450000 | 2026-11-12 | `quarterly` |
| "Birch & Co, invoice 1057" | 960000 | 2026-11-17 | null |
| "Equipment lease deposit" | -300000 | 2026-12-07 | null |

`expected_payment_matches` holds 0 rows for the business (AC 27)
Proof: `uv run pytest tests/test_expected_payments_sample.py -k "sample_payments"`

**C34** - Running the same load a second time for the same owner leaves exactly 4 payments (AC 27)
Proof: `uv run pytest tests/test_expected_payments_sample.py -k "load_twice"`

### S6 - The owner manages expected payments on the web · 14 files · 260 KB · ~65k

**C35** - With the API loaders mocked to return the 4 sample payments, the page renders:
- the heading "Expected payments" and the line "Payments you know are coming that Headroom can't predict from your bank data."
- one button "Add expected payment"
- column headers "Date", "Description", "Account", "Repeats", "Amount", plus a header "Actions" that is visible only to screen readers

The rows are, in order:
- "Tue, Oct 6", "Acme Co, invoice 1042", "Operating checking", "Doesn't repeat", "+$8,000"
- "Thu, Nov 12", "Coastal Supply Co, quarterly order", "Operating checking", "Every 3 months", "−$14,500" (true minus)
- then the Birch and lease rows

Each row has buttons named "Edit {description}" and "Delete {description}". The +$8,000 cell has the `text-positive` class (AC 28)
Proof: `npx vitest run tests/expected-payments-page.test.tsx -t "renders the mockup rows"`

**C36** - The Repeats text, table-driven over 5 values:
- null -> "Doesn't repeat"
- `weekly` -> "Every week"
- `biweekly` -> "Every 2 weeks"
- `monthly` -> "Every month"
- `quarterly` -> "Every 3 months"

(AC 28)
Proof: `npx vitest run tests/expected-payments-page.test.tsx -t "repeats text"`

**C37** - A row whose `overdue` is true shows a badge "Overdue" with the `warning` variant, and a row with `overdue` false shows none. A row whose `account_id` isn't among the included accounts shows "Account removed" in its Account cell (AC 29, AC 30)
Proof: `npx vitest run tests/expected-payments-page.test.tsx -t "overdue and removed account"`

**C38** - With `{"items": []}`, the page shows:
- the title "No expected payments yet"
- the sentence "Add a payment you know is coming, such as a large invoice, so your forecast includes it."
- a button "Add expected payment"
- no table

(AC 31)
Proof: `npx vitest run tests/expected-payments-page.test.tsx -t "empty state"`

**C39** - When the list loader returns null (an API failure), the page shows "We couldn't load your expected payments." and a "Try again" button. The route's `loading.tsx` renders a `Skeleton` (AC 32)
Proof: `npx vitest run tests/expected-payments-page.test.tsx -t "error and loading states"`

**C40** - Activating "Add expected payment" opens a dialog titled "Add expected payment". Its fields, in DOM order:
- the "Money out" / "Money in" control, with "Money out" pressed
- "Amount", with `inputmode="decimal"`
- "Date", with `type="date"`
- "Description"
- "Account", listing exactly the included accounts with the primary selected
- "Repeats", set to "Doesn't repeat"
- the buttons "Cancel" and "Add payment"

Entering "2,300.50", Money in, 2026-11-20, "Van repair deposit" and "Every month", then submitting, calls the create action with:
- `amount_cents` 230050
- `date` "2026-11-20"
- `description` "Van repair deposit"
- `repeats` `monthly`
- the primary `account_id`

With Money out, `amount_cents` is -230050. On success the dialog closes and the toast "Expected payment added" is shown (AC 33)
Proof: `npx vitest run tests/expected-payment-dialog.test.tsx -t "add dialog"`

**C41** - "Edit Acme Co, invoice 1042" opens a dialog titled "Edit expected payment", filled with:
- "Money in" pressed
- Amount "8,000.00"
- Date "2026-10-06"
- that description, account and repeats

Its button is "Save changes". Saving calls the update action with the payment's `id`, and shows "Expected payment updated" (AC 34)
Proof: `npx vitest run tests/expected-payment-dialog.test.tsx -t "edit dialog"`

**C42** - "Delete Acme Co, invoice 1042" opens a dialog titled "Delete Acme Co, invoice 1042?" with "Cancel" and a `destructive` "Delete payment". Cancel calls no action. Confirming calls the delete action with the `id` and shows "Expected payment deleted" (AC 35)
Proof: `npx vitest run tests/expected-payment-dialog.test.tsx -t "delete confirmation"`

**C43** - Dialog validation, table-driven. Each rejected value shows an error under its field and calls no action:
- Amount: "", "0", "abc", "1.234", "100000000"
- Description: "   "

"99,999,999.99" is accepted. When the action returns a `409` with detail "Choose an account you count as cash.", the dialog stays open with the values kept and shows that detail. For a `422` it shows "We couldn't save this payment. Check the details and try again." (AC 36)
Proof: `npx vitest run tests/expected-payment-dialog.test.tsx -t "validation"`

**C44** - The server actions call the typed client with `authHeaders()`:
- create -> `POST /v1/businesses/{business_id}/expected-payments`
- update -> `PUT .../expected-payments/{payment_id}`
- delete -> `DELETE .../expected-payments/{payment_id}`

Each calls `revalidatePath("/expected-payments")` on success, and returns `{ ok: false, status, detail }` on a problem response (AC 33-36)
Proof: `npx vitest run tests/expected-payments-actions.test.ts -t "server actions"`

**C45** - In Playwright against the local API, a fresh owner with a sandbox bank (spec 17's e2e helpers) uses only the mouse to:
- add "E2E deposit" for $1,234.56, Money out, Doesn't repeat, today + 10 days
- reload: the row reads "−$1,234.56"
- edit it to $2,000.00, Every month
- reload: the row reads "−$2,000" and "Every month"
- delete it
- reload: the empty state is shown

`GET .../expected-payments` through the API, read with the owner's token, matches after each step (AC 39, spec 20 "Done when" 1)
Proof: `npx playwright test e2e/expected-payments.spec.ts -g "round trip"`

**C46** - At 375x812, for the same owner with one payment:
- `document.documentElement.scrollWidth` is at most 375
- the row's description and amount sit above its date
- the open add dialog's box equals the viewport
- every button, input and select in `main` and in the dialog is at least 44px tall

Using only the keyboard (Tab, Enter, Space and Escape), the owner:
- opens the add dialog, fills it and submits it, and the row appears
- opens Edit and then Delete on that row
- presses Escape in each dialog, and focus returns to the button that opened it

`AxeBuilder` reports 0 violations for the page, the open add dialog, the open delete dialog and the empty state (AC 37, AC 38)
Proof: `npx playwright test e2e/expected-payments.spec.ts -g "phone keyboard and axe"`

**C47** - Every AGENTS.md check passes:
- API: `ruff format --check`, `ruff check`, `mypy app`, `pytest`
- web: `lint`, `typecheck`, `test`, `build`

The new components read every string through next-intl's typed keys, so `typecheck` fails on a key that is missing from `messages/en.json` (AC 28-36: all text from `en.json`)
Proof: `bash .specs/features/20-forecast-expected-payments/proofs.sh c47`

**C48** - `app/(app)/expected-payments/page.tsx` calls `await auth.protect()` first, so a signed-out visitor never reaches the page (AD-026; Observable: unauthorised state)
Proof: `npx vitest run tests/auth-protect.test.ts -t "every page protected"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET .../expected-payments` statuses (4) | 200 C9 · 403 C10 · 404 C10 · 422 C11 | - |
| `POST .../expected-payments` statuses (5) | 201 C1, C2 · 403 C10 · 404 C10 · 409 C3, C4 · 422 C5 | - |
| `PUT .../expected-payments/{payment_id}` statuses (5) | 200 C6 · 403 C10 · 404 C8, C10 · 409 C6 · 422 C6, C11 | - |
| `DELETE .../expected-payments/{payment_id}` statuses (4) | 204 C7 · 403 C10 · 404 C8, C10 · 422 C11 | - |
| `repeats` values (5) | null C5, C17, C36 · `weekly` C5, C17, C36 · `biweekly` C5, C17, C36 · `monthly` C5, C17, C36 · `quarterly` C5, C17, C36 | - |
| body bounds (8) | description min C5 · description max C5 · amount min C5 · amount max C5 · date min C5 · date max C5 · repeats in set C5 · extra field C5 | - |
| account rule cases (5) | not included C3 · credit C3 · other business C3 · unknown C3 · no primary C4 | - |
| candidate conditions (5) | label C18 · currency C18 · sign C18 · amount 10% C18 · date -7/+14 C18 | - |
| assignment tie-breaks (4) | created order C19 · amount difference C19 · day difference C19 · transaction id C19 | - |
| rematch triggers (4) | sync C21 · create C22 · update C22 · delete C7 | - |
| `next_date` rules (5) | repeating window closed C25 · repeating window open C25 · matched occurrence skipped C25 · overdue one-off C25 · matched one-off absent C25, C9 | - |
| events (2 outcomes) | published after commit C30 · not published C31, C32 | - |
| audit actions (3) | created C12 · updated C12 · deleted C12 | - |
| screen states (5) | populated C35 · empty C38 · loading C39 · error C39 · unauthorised C48 | - |
| dialogs (3) | add C40 · edit C41 · delete C42 | - |
| toasts (3) | added C40 · updated C41 · deleted C42 | - |
| check constraints (4) | amount non-zero C13 · repeats C13 · match transaction unique C14 · match occurrence key C14 | - |
| startup config: handler subscribed (2 assemblies) | API lifespan C32 + existing `tests/test_run_due.py::test_subscriptions_reach_job_events` · jobs `run_due.main` C32 + the same existing test. Both register the one `SUBSCRIPTIONS` list (AD-055) | - |
| doors (4) | 1 C1, C13, C15 · 2 C14, C21, C24, C32 · 3 C1, C9, C16 · 4 C30 | - |
| "Done when" (3) | 1 C45 · 2 C29 · 3 C35-C42, C46 | - |

- Claims naming a status code or response shape: C1-C12, C25, C30, C31. Each proof calls the route through `TestClient` with a signed token.
- C35-C43 render the components with mocked loaders and actions. C45 and C46 are the only proofs that cross the web-to-API boundary.
- "Done when" 3 ("matches the mockup") is proven by the copy and the arrangement C35-C42 assert, not by comparing pixels. Spacing, colour and type weight are not claimed; that would need the `ui` profile.

## Swept

- validation: C5, C3, C4, C11, C43 (dialog), C13 (database)
- failure modes: C26 (a failed match rolls back and keeps the earlier set; the sync stays committed), C31 (a failed request publishes nothing), C43 (an API error keeps the dialog open)
- idempotency: C23 (same event twice), C20 (same inputs in any order), C34 (loading the sample twice)
- authorization: C10, every route; the handler takes the business only from the event
- concurrency: C24 (two matchers, and a matcher with a write, under the advisory lock)
- data lifecycle: C7 (a delete cascades to the matches), C21 (a match disappears with its transaction); no backfill (plan, Impact)
- dependency failure: n/a - no external service is called. The database failing is C26's rollback path; Plaid is reached only by the sync that publishes the event
- state transitions: C21, C22 (an occurrence moves between open and matched in both directions), C25 (open -> overdue -> window closed)
- observability: C27 (`expected_payments.matched`, nothing sensitive), C26 (`event.handler_failed`), C12 (audit)

## Handoff

- Estimate, from `wc -c` of the files each slice reads or writes, divided by 4:
  - S1 = 38k: `forecasting/api.py`, `service.py`, `models.py` and `repository.py`; `bank_sync/service.py` (45 KB); `app/audit.py`; the migration; 2 new test files; `test_migrations.py`.
  - S2 = 10k: the new matcher and its tests.
  - S3 = 8k: the service and the same test file.
  - S4 = 6k: `subscriptions.py` and `events.py`.
  - S5 = 13k: `fixtures/load.py` and `harbor_street.py`, plus a new test.
  - S6 = 65k: the page, `loading.tsx`, `actions.ts`, 4 to 5 new components, `messages/en.json`, `lib/api/` (bank is the model), `lib/format.ts`, the `ui/` dialog, select, toggle-group and badge, 3 new Vitest files, and 1 e2e file with `onboarding-steps.ts` and `bank-settings.spec.ts` as the model.
- Running total 140k, under the 150k budget, so one builder. S6 alone is 65k; the cut, if one were needed, would be at the API to web boundary after S5.
- Mechanism: one builder (fits; no ask).
