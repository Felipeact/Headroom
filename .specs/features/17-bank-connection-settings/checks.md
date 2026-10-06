# 17 - Bank connection settings checks

Profile: light
Plan: `.specs/features/17-bank-connection-settings/plan.md`

55 checks in 5 slices · 7 one-way doors · 0 open

- **API commands** run from `services/core/` (`uv run pytest ...`). **Web commands** run from `frontend/` (`npx vitest run ...`). Commands that are not one test live in `.specs/features/17-bank-connection-settings/proofs.sh` (`bash proofs.sh c<n>`).
- **Plaid:** API tests use a fake `PlaidClient` (spec 14's `SyncFake` pattern, spec 15's nightly pattern). Only the C26 and C48 proofs call the real Plaid sandbox.
- **Plaid errors** in claims are `PlaidError(error_type=..., error_code=...)`. "Login error" means `error_type="ITEM_ERROR", error_code="ITEM_LOGIN_REQUIRED"`. "Other Plaid error" means `error_type="API_ERROR", error_code="INTERNAL_SERVER_ERROR"`.
- **Routes:** `link-token` means `POST /v1/businesses/{business_id}/bank/connections/{connection_id}/link-token`, `repair` means `POST .../connections/{c}/repair`, and `disconnect` means `DELETE .../connections/{c}`.
- **Web tests** render the page with the API client mocked, as `tests/accounts-page.test.tsx` does. Times are rendered for a business in `America/Toronto` with the clock fixed at `2026-10-06T14:00:00Z` (10:00 local).

## Checks

### S1 - The owner sees every bank and its sync status · 14 files · 150 KB · ~38k

**C1** - A connection with `login_required` true and `last_synced_at` null is synced successfully with `now = 2026-10-06T06:04:00Z`. Afterwards `last_synced_at` is `2026-10-06T06:04:00Z` and `login_required` is false (AC 1)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "sync_success_records_time"`

**C2** - `GET .../bank/connections` gives `status`, table-driven over 5 stored states (`login_required`, `failed_nights`, `last_synced_at`):
- true, 3, set -> `login_required`
- true, 0, null -> `login_required`
- false, 3, set -> `sync_failing`
- false, 2, set -> `synced`
- false, 0, null -> `syncing`

and gives `last_synced_at` as stored (ISO 8601 UTC) or null (AC 2)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "status_precedence"`

**C3** - The migration adds `login_required` and `last_synced_at` to `bank_connections`. A row that existed before the upgrade has `login_required` false and `last_synced_at` null. Inserting a null `login_required` fails with `IntegrityError`. Downgrade removes both columns (plan Impact, stored data; doors 1, 2)
Proof: `uv run pytest tests/test_migrations.py -k "connection_settings_upgrade_downgrade"`

**C4** - Rendering `/settings` calls `redirect("/settings/banks")` (AC 3)
Proof: `npx vitest run tests/settings-nav.test.tsx -t "settings redirects to banks"`

**C5** - The settings section navigation has, in order, the links Business (`/settings/business`), Bank connections (`/settings/banks`), Members (`/settings/members`), Email preferences (`/settings/email`) and Your data (`/settings/data`). On `/settings/banks` only Bank connections has `aria-current="page"` (AC 4)
Proof: `npx vitest run tests/settings-nav.test.tsx -t "section navigation"`

**C6** - Each of the 4 placeholder sections (Business, Members, Email preferences, Your data) renders its title as a heading and the "coming soon" text (AC 4)
Proof: `npx vitest run tests/settings-nav.test.tsx -t "placeholder sections"`

**C7** - Status lines, table-driven over 5 connections, in order of `created_at`:
- `synced`, `last_synced_at` `2026-10-06T06:04:00Z` -> "Synced today at 2:04 AM"
- `synced`, `last_synced_at` `2026-10-03T06:04:00Z` -> "Synced Oct 3 at 2:04 AM"
- `syncing` -> "Syncing…"
- `login_required` -> badge "Needs attention"
- `sync_failing` -> badge "Needs attention"

The 5 bank names appear in the order the API gave them (AC 5)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "status lines"`

**C8** - The time formatter gives "today at 2:04 AM" for `2026-10-06T06:04:00Z`, "Oct 3 at 2:04 AM" for `2026-10-03T06:04:00Z`, and "Oct 5 at 11:30 PM" for `2026-10-06T03:30:00Z` (still Oct 5 in Toronto), at the fixed clock in `America/Toronto` (AC 5)
Proof: `npx vitest run tests/format.test.ts -t "synced time"`

**C9** - Account rows, table-driven over 3 accounts:
- checking "Operating checking", mask `2381`, `balance_cents` 800000 -> "Operating checking", "••2381 · Checking", "$8,000"
- line of credit, mask `7702`, `available_cents` 2000000 -> "••7702 · Credit", "$20,000" with "available" on the line below
- credit card, mask `5530`, `balance_cents` 245000 -> "••5530 · Credit card", "$2,450" with "owed" on the line below

(AC 6) (amended 2026-10-06 to match the binding mockup, approved by the user)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "account rows"`

**C10** - The `/settings/banks` loading component renders at least one skeleton card with `aria-busy="true"` (AC 7)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "loading skeleton"`

**C11** - With `items: []`, the page shows the heading "No bank connected yet", the text "Connect your bank to see your 13-week forecast." and a "Connect your bank" button, and no bank card (AC 8)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "empty state"`

**C12** - When the connections request answers `500` or throws, the page shows "We couldn't load your bank connections. Check your connection and try again." and a "Try again" button, and Sentry's capture is called once (AC 9)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "load error"`

**C13** - In the running app at 375×812 on `/settings/banks` with one bank: the page's `scrollWidth` is at most 375, every button, switch and link is at least 44px tall, Tab reaches "Connect another bank", each switch, "Make primary" and "Disconnect", and an axe scan finds no violation (AC 10)
Proof: `bash .specs/features/17-bank-connection-settings/proofs.sh c13`

### S2 - The owner changes which accounts count as cash, and the primary account · 6 files · 45 KB · ~11k

**C14** - Turning on the "Counts as cash" switch of a savings account calls the update action with `{ included: true }` for that account. After the action resolves, the page re-renders from the API (AC 11)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "toggle counts as cash"`

**C15** - A credit card and a line of credit row each show "Credit never counts as cash" and no switch. Every account with `included` false shows "Not available" in the Primary column and no primary radio (AC 12) (amended 2026-10-06 to match the binding mockup, approved by the user)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "credit rows"`

**C16** - The primary account's radio is labelled "Primary" and checked; every other included account has an unchecked radio labelled "Make primary". Choosing "Make primary" on another included account calls the update action with `{ primary: true }` for it (AC 13) (amended 2026-10-06 to match the binding mockup, approved by the user)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "make primary"`

**C17** - When the update action returns `{ error: "saveFailed" }`, the switch returns to its previous state and the page shows "We couldn't save that change. Try again." (AC 14)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "save failed"`

**C18** - In the running app, through the Plaid sandbox: an owner turns a savings account into cash and makes it primary on `/settings/banks`, reloads, and sees the switch on and that account's "Primary" radio checked (AC 11, AC 13) (amended 2026-10-06 to match the binding mockup, approved by the user)
Proof: `bash .specs/features/17-bank-connection-settings/proofs.sh c18`

### S3 - A bank that needs a login shows a banner and can be repaired · 16 files · 210 KB · ~53k

**C19** - A sync that fails with the login error sets `login_required` true and leaves the connection's transactions, cursor and `last_synced_at` as they were, table-driven over 2 paths: `sync_connection` called directly (raises `PlaidError`), and `sync_in_background` (logs, does not raise) (AC 15)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "login_error_recorded"`

**C20** - A nightly run (`run_due` at `2026-10-06T06:00:00Z`) whose sync fails with the login error sets `login_required` true, and records the failure as spec 15 does: `nightly_attempts` 1 and `next_nightly_attempt_at` `2026-10-06T07:00:00Z`. The retry run at `2026-10-06T07:00:00Z`, with the fake now succeeding, leaves `login_required` false and `last_synced_at` `2026-10-06T07:00:00Z` (AC 1, AC 15)
Proof: `uv run pytest tests/test_bank_connection_nightly.py -k "nightly_login_error"`

**C21** - A sync that fails with the other Plaid error leaves `login_required` false (AC 15)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "other_error_not_login"`

**C22** - A signed webhook `{"webhook_type": "ITEM", "webhook_code": "ERROR", "item_id": <stored>, "error": {"error_code": "ITEM_LOGIN_REQUIRED", ...}}` answers `200` `{"status": "ok"}` and sets that connection's `login_required` true. Another connection of the same business is unchanged (AC 16)
Proof: `uv run pytest tests/test_plaid_item_webhooks.py -k "item_error_login_required"`

**C23** - Table-driven over 4 signed webhooks, each answering `200` with no sync started and no column of any connection changed: `ITEM` / `ERROR` with `error_code` `INSTITUTION_DOWN`; `ITEM` / `ERROR` with `"error": null`; `ITEM` / `PENDING_DISCONNECT`; `ITEM` / `ERROR` `ITEM_LOGIN_REQUIRED` for an `item_id` that is not stored (door 6)
Proof: `uv run pytest tests/test_plaid_item_webhooks.py -k "item_webhooks_ignored"`

**C24** - A signed `ITEM` / `LOGIN_REPAIRED` webhook for a stored item answers `200` and runs exactly one sync of that connection. With the fake's sync succeeding, `login_required` is false and `last_synced_at` is set afterwards (AC 1, AC 17)
Proof: `uv run pytest tests/test_plaid_item_webhooks.py -k "login_repaired_syncs"`

**C25** - `needs_attention`, table-driven over 4 states (`login_required`, `failed_nights`): true, 0 -> true; false, 3 -> true; true, 3 -> true; false, 2 -> false (AC 18)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "needs_attention_table"`

**C26** - Against the real Plaid sandbox: connect TD Canada Trust, sync it, call `/sandbox/item/reset_login` on the item, sync again. The connection's `status` in `GET .../bank/connections` is `login_required`, and `link-token` answers `200` with a non-empty `link_token` (AC 15, AC 21, AC 26 API half)
Proof: `bash .specs/features/17-bank-connection-settings/proofs.sh c26`

**C27** - A `login_required` card shows a banner with role `alert` reading "TD Canada Trust asked you to log in again. Until you do, your forecast is missing this bank's latest data." and a "Reconnect" button (AC 19)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "login banner"`

**C28** - A `sync_failing` card shows a banner reading "We couldn't sync TD Canada Trust for 3 nights. Until it works again, your forecast is missing this bank's latest data." and a "Reconnect" button. A `synced` card shows no banner (AC 20)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "sync failing banner"`

**C29** - `link-token` answers `200` with `link_token` and `expiration`. The fake received one link token request whose access token is the connection's decrypted token, whose products are empty, and whose `webhook` is the `PLAID_WEBHOOK_URL` setting (AC 21)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "update_link_token"`

**C30** - When Link in update mode calls `onSuccess`, the page calls the repair action with the business and connection IDs and never calls the connect action. The repair action posts to `/v1/businesses/{business_id}/bank/connections/{connection_id}/repair` and revalidates `/settings/banks` on `200` (AC 22)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "update mode success"`
Proof: `npx vitest run tests/bank-settings-actions.test.ts -t "repair action"`

**C31** - `repair` on a `login_required` connection whose sync succeeds answers `200` with the `Connection` JSON, `status` `synced` and `last_synced_at` set (AC 23)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "repair_succeeds"`

**C32** - `repair` whose sync fails with the login error answers `409` `application/problem+json` with detail "Your bank still needs you to log in.", and the connection is still `login_required` (AC 24)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "repair_still_login"`

**C33** - Table-driven over `link-token` and `repair` with the fake raising the other Plaid error: each answers `502` `application/problem+json` with detail "We couldn't reach our bank connection provider. Try again." (AC 25)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "plaid_failure_502"`

**C34** - When the repair action returns an error, the card shows "We couldn't reconnect TD Canada Trust. Try again.". When Link's `onExit` is called with no error, no message appears (AC 25)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "reconnect errors"`

**C35** - In the running app, through the Plaid sandbox: an owner with TD Canada Trust connected has its login reset by `tests/sandbox_reset_login.py` (which refuses to run unless `PLAID_ENV` is `sandbox`), and `/settings/banks` shows the C27 banner. "Reconnect", then Link with `user_good` / `pass_good`, returns the card to "Synced today at …" with no banner and no reload (AC 26, spec "Done when" 1)
Proof: `bash .specs/features/17-bank-connection-settings/proofs.sh c35`

### S4 - The owner disconnects a bank · 12 files · 170 KB · ~43k

**C36** - Pressing "Disconnect" on TD Canada Trust opens a dialog titled "Disconnect TD Canada Trust?" with the text "Headroom stops syncing this bank and removes its accounts and transactions. This can't be undone.", a "Cancel" button and a "Disconnect" button. Pressing Escape, and separately "Cancel", closes it and the disconnect action is not called (AC 27)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "disconnect dialog"`

**C37** - `disconnect` of a connection with 2 accounts and 3 transactions answers `204` with an empty body. The fake's `remove_item` was called once with the decrypted access token. Afterwards the database holds no `bank_connections` row with that ID, no `bank_accounts` row with that `connection_id`, and none of the 3 transactions (AC 28)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_deletes"`

**C38** - With `remove_item` raising `ITEM_NOT_FOUND` (`error_type="ITEM_ERROR"`), `disconnect` answers `204` and deletes as in C37 (AC 29)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_item_not_found"`

**C39** - With `remove_item` raising the other Plaid error, `disconnect` answers `502` `application/problem+json` with detail "We couldn't reach our bank connection provider. Try again.", and the connection, its accounts, its transactions and its audit entries are exactly as before (AC 30)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_plaid_fails"`

**C40** - When the disconnect action returns an error, the dialog stays open and shows "We couldn't disconnect TD Canada Trust. Try again." (AC 30)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "disconnect error"`

**C41** - After C37's disconnect, `audit_log` has exactly one new entry: `action` `bank_connection.disconnected`, `actor_user_id` the caller's user ID, `target_type` `bank_connection`, `target_id` the connection's ID, `details` `{"institution_id": <its institution>, "account_count": 2}` (AC 31)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_audited"`

**C42** - Primary account after a disconnect, table-driven over 3 cases, bank A disconnected:
- A holds the primary; bank B has included checking accounts with balances 10,000 and 50,000 cents -> the 50,000 account is primary
- A holds the primary; B has no included account -> no account of the business is primary
- B holds the primary -> B's primary is unchanged

(AC 32)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_primary"`

**C43** - Savings on bank A -1,000,000 and checking on bank B +1,000,000, both dated 2026-09-14, are `internal_transfer` and paired. After disconnecting A, B's transaction is `normal` with a null link (AC 33)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_relabels"`

**C44** - C43's disconnect publishes exactly one `transactions.synced` event after the commit, with `business_id` the business, payload `connection_id` A's ID, `added` 0, `modified` 0, `removed` 1, `relabeled` 1, `balances_changed` true (AC 34)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_publishes"`

**C45** - After a disconnect: no `bank_connections` row holds the old `access_token_ciphertext`; `repository.nightly_candidates` does not list the connection; a signed `TRANSACTIONS` / `SYNC_UPDATES_AVAILABLE` webhook for its item answers `200` and the fake's `sync_transactions` is not called; `sync_in_background` for the old connection ID returns without raising and logs `bank_sync.sync_skipped` with the business and connection IDs (AC 35, spec "Done when" 2)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_stops_syncing"`

**C46** - A sync of connection A holds its lock inside a blocking fake. A disconnect of A started on a second thread does not return until the sync is released. Then the sync commits, the disconnect answers `204`, neither raises, and A's rows are gone (AC 36)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "disconnect_waits_for_sync"`

**C47** - When the disconnect action succeeds, the dialog closes, the toast "TD Canada Trust disconnected" appears, and the action revalidates `/settings/banks`. The disconnect action sends `DELETE` to `/v1/businesses/{business_id}/bank/connections/{connection_id}` (AC 37)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "disconnect success"`
Proof: `npx vitest run tests/bank-settings-actions.test.ts -t "disconnect action"`

**C48** - Against the real Plaid sandbox: connect TD Canada Trust, `disconnect` answers `204`, and Plaid `/accounts/get` with the old access token then fails with `ITEM_NOT_FOUND` (AC 28, spec "Done when" 2)
Proof: `bash .specs/features/17-bank-connection-settings/proofs.sh c48`

**C49** - In the running app, through the Plaid sandbox: an owner with two banks disconnects RBC Royal Bank through the dialog, and its card disappears without a reload while TD Canada Trust's stays (AC 37)
Proof: `bash .specs/features/17-bank-connection-settings/proofs.sh c49`

### S5 - Every new route is the owner's alone · 3 files · 45 KB · ~11k

**C50** - Table-driven over `link-token`, `repair` and `disconnect`: called by an owner of another business with business A's IDs, each answers `404` "Business not found."; called by A's owner with a connection ID of business B, and with a random UUID, each answers `404` "Bank connection not found.". The fake records no Plaid call, and both businesses' connections, accounts and transactions are unchanged (AC 38)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "foreign_connection_404"`

**C51** - Table-driven over the 3 routes with membership role `viewer` (monkeypatched, as `test_non_owner_gets_403`): each answers `403` "You don't have permission to do this.", with no Plaid call and nothing changed. A malformed `connection_id` (`not-a-uuid`) answers `422` on each route (AC 39)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "non_owner_403"`

**C52** - With the fake's access token `access-sandbox-c52-secret` and a Plaid error whose message is `c52-plaid-message`, after `link-token`, a failing `repair`, a failing `disconnect` and a successful `disconnect`: neither string appears in any response body, any captured log line, or any audit entry's `details` (AC 40)
Proof: `uv run pytest tests/test_bank_connection_settings.py -k "no_secrets_leak"`

**C53** - `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` match a fresh export. The contract has the 3 new operations, and `Connection` has `status` with exactly the enum `syncing`, `synced`, `login_required`, `sync_failing` and a nullable `last_synced_at` (Surface, door 3)
Proof: `bash .specs/features/17-bank-connection-settings/proofs.sh c53`

**C55** - The existing statuses of the two changed routes still hold: `GET /v1/businesses/{business_id}/bank/connections` answers `403` for a `viewer`, `404` for a non-member and `422` for `not-a-uuid`; `POST /v1/webhooks/plaid` answers `401` for a bad signature, `422` for a malformed body and `502` when the key fetch fails (Surface, signature changes)
Proof: `uv run pytest tests/test_bank_accounts.py tests/test_plaid_webhook.py -k "non_owner_gets_403 or non_member_gets_404 or patch_validation_malformed_ids or bad_header_rejected or malformed_body or key_fetch_fails"`

**C54** - Every AGENTS.md check for the API and the web app passes: ruff format and check, mypy, pytest, lint, typecheck, vitest and build
Proof: `bash .specs/features/17-bank-connection-settings/proofs.sh c54`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET .../bank/connections` statuses (4) | 200 C2 · 403 C55 · 404 C55 · 422 C55 | - |
| `POST .../link-token` statuses (5) | 200 C29 · 403 C51 · 404 C50 · 422 C51 · 502 C33 | - |
| `POST .../repair` statuses (6) | 200 C31 · 403 C51 · 404 C50 · 409 C32 · 422 C51 · 502 C33 | - |
| `DELETE .../connections/{c}` statuses (5) | 204 C37 · 403 C51 · 404 C50 · 422 C51 · 502 C39 | - |
| `POST /v1/webhooks/plaid` statuses (4) | 200 C22, C23, C24 · 401 C55 · 422 C55 · 502 C55 | - |
| connection `status` values (4) | `syncing` C2 · `synced` C2 · `login_required` C2 · `sync_failing` C2 | - |
| status precedence rows (5) | C2, table-driven over all 5 | - |
| `needs_attention` rows (4) | C25, table-driven over all 4 | - |
| paths that record a login error (5) | direct sync C19 · background sync (webhook and connect) C19 · nightly C20 · repair C32 · `ITEM` / `ERROR` webhook C22 | - |
| paths that set `last_synced_at` (4) | direct sync C1 · webhook background sync C24 · nightly C20 · repair C31 | - |
| item webhook codes (6) | `ERROR` + `ITEM_LOGIN_REQUIRED` C22 · `ERROR` + other code C23 · `ERROR` + null error C23 · `LOGIN_REPAIRED` C24 · `PENDING_DISCONNECT` C23 · unknown item C23 | - |
| doors (7) | 1 C3, C19, C25 · 2 C1, C3 · 3 C2, C53 · 4 C29, C31, C32, C37 · 5 C37, C39, C46 · 6 C22, C23, C24 · 7 C44 | - |
| `remove_item` outcomes (3) | success C37 · `ITEM_NOT_FOUND` C38 · other error C39 | - |
| what a disconnect deletes (4) | connection row C37 · accounts C37 · transactions C37 · token C45 | - |
| primary after a disconnect (3) | reassigned C42 · none left C42 · untouched C42 | - |
| after-disconnect sync paths (4) | nightly C45 · webhook C45 · queued background C45 · running sync C46 | - |
| settings sections (5) | Business C5, C6 · Bank connections C5 · Members C5, C6 · Email preferences C5, C6 · Your data C5, C6 | - |
| screen `/settings/banks` states (5) | loading C10 · empty C11 · error C12 · partial (banner) C27, C28 · loaded C7, C9 | - |
| balance displays (3) | cash-side C9 · line of credit C9 · credit card C9 | - |
| status line displays (4) | synced today C7, C8 · synced earlier C7, C8 · syncing C7 · needs attention C7 | - |
| page-side failures (4) | load C12 · save C17 · reconnect C34 · disconnect C40 | - |
| relations (3) | connection -> accounts deleted C37 · accounts -> transactions deleted C37 · link set null and relabelled C43 | - |
| "Done when" (2) | 1 C26, C35 · 2 C45, C48 | - |

- Claims naming a status code or response shape: C2, C29, C31-C33, C37-C39, C50, C51 - each proof calls the route through `TestClient`.
- The connect path's first background sync is not asserted separately for `last_synced_at`; it runs the same `sync_in_background` as C24. Sampling gap stated, not hidden.
- C13, C18, C35, C49 run against the local app and the Plaid sandbox, and need `.env.local` in both apps.

## Swept

- validation: C51 (malformed `connection_id` is `422`); the new routes take no body
- failure modes: C19, C21, C39 (Plaid fails first, so nothing is deleted), C33
- idempotency: C38 (a repeated disconnect after Plaid already removed the item still succeeds), C24 (a second `LOGIN_REPAIRED` only runs another sync)
- authorization: C50, C51
- concurrency: C46 (disconnect waits for a running sync); lock order connection then accounts is AD-058's, unchanged
- data lifecycle: C37, C45 (hard delete of connection, accounts, transactions, token), C3 (backfill of existing rows)
- dependency failure: C33, C39, C34, C40
- state transitions: C1 (login required -> cleared on success), C19, C22 (-> login required), C24, C31, C32
- observability: C45 (`bank_sync.sync_skipped`), C52 (no secrets in logs, responses, audit); the disconnect logs `bank_connection.disconnected` with IDs only, sampled by C52

## Handoff

- Estimate, from `wc -c` of the files each slice reads or writes, divided by 4: S1 = 38k (bank_sync service, api, models, migration, settings pages, format, en.json, tests); S2 = 11k (account card reuse, actions, tests); S3 = 53k (service sync paths, webhooks, plaid port, nightly tests, Link update mode, sandbox helper, e2e); S4 = 43k (service disconnect, repository, dialog, tests); S5 = 11k. Running total 156k, of which about 35k is the same service, api and test files counted again in S3 and S4. Counted once, about 121k, under the 150k budget - one builder.
- Mechanism: one builder (fits; no ask).

- **Boundary:** C1-C55 closed at the web commit after `ffc230a` (API at `ffc230a`). Proofs green there: every named pytest and vitest proof; `proofs.sh c13 c18 c26 c35 c48 c49 c53 c54` (c26, c48 and the four e2e against the real Plaid sandbox); API suite 467 passed; web 224 passed; lint, typecheck, build. Regression e2e green with `--workers=1`: shell, choose-accounts, bank-connect, onboarding (spec 07's C42 left out, as specs 12 and 13 did)
- **Settled mid-build:**
  - User-approved (2026-10-06): C9, C15, C16, C18 and plan AC 6, 12, 13 amended to the binding mockup - primary is a radio labelled "Primary" / "Make primary", a line of credit reads "Credit", and "available" / "owed" sit under the amount.
  - Each account row's primary radio is a Radix `RadioGroup` of its own. One group around the table (spec 13's pattern, with the root at `tabIndex={-1}`) left no radio reachable by Tab, which C13 caught.
  - Existing tests changed to the approved contract, no assertion loosened: two exact `Connection` key sets gain `status` and `last_synced_at`; spec 15's three-failed-nights test fails with a non-login error (AD-061); two onboarding tests expect `connectBank`'s new third argument; spec 07's shell C9 expects `/settings/banks`; spec 13's `Connection` fixture gains the two fields.
  - Test-setup fixes, no assertion changed: per-test Plaid transaction IDs; the empty-state test looks for no table instead of no region (sonner's Toaster is a region); e2e waits for the first sync by reloading, uses the visible Link iframe, skips Link's phone screen, and fills the username only when update mode asks for it.
  - `Toaster` gets `customAriaLabel` from messages, and the skeleton gets `role="status"`, for spec 07's C20 and C18.
  - The C8 proof lives in `tests/format.test.ts`, as named, beside the older `lib/format.test.ts`.
- **Abandoned:** a single radio group per bank (above)

