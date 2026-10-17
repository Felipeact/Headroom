# Flinks as a second bank provider - checks

Profile: light
Plan: `.specs/features/17a-bank-flinks-provider/plan.md`

36 checks in 4 slices · 5 one-way doors · 3 open, of which 2 block go-live (Flinks credentials; RBC authenticator proof)

API proofs run from `services/core`, web proofs from `frontend`.

## Checks

### S1 - The schema and the seam carry a provider, with Plaid unchanged · 37 files · 522 KB (rename by `sed`, ~8 read) · ~25k

**C1** - After upgrade, every pre-existing `bank_connections` row has `provider = 'plaid'`, and the `plaid_*` columns are named `provider_item_id`, `provider_institution_id`, `provider_account_id`, `provider_transaction_id` (AC 1)
Proof: `uv run pytest tests/test_bank_provider_migration.py -k "existing_rows_become_plaid"`

**C2** - Downgrade restores the four `plaid_*` column names and drops `provider`, with the rows intact (AC 1)
Proof: `uv run pytest tests/test_bank_provider_migration.py -k "downgrade_restores_plaid_names"`

**C3** - Inserting `provider = 'other'` fails on `ck_bank_connections_provider`; `plaid` and `flinks` both insert (AC 2)
Proof: `uv run pytest tests/test_bank_provider_migration.py -k "provider_check_constraint"`

**C4** - `(provider, provider_item_id)` is unique, and `(business_id, provider, provider_institution_id)` is unique, so the same institution ID under the other provider inserts (door 1)
Proof: `uv run pytest tests/test_bank_provider_migration.py -k "provider_uniques"`

**C5** - The existing Plaid connect, accounts, sync, nightly, settings, webhook and fixture suites pass with only column renames (AC 3)
Proof: `uv run pytest tests/test_bank_connect.py tests/test_bank_accounts.py tests/test_bank_connection_nightly.py tests/test_bank_connection_settings.py tests/test_plaid_webhook.py tests/test_plaid_item_webhooks.py tests/test_nightly_sync.py tests/test_fixture_load.py`
Proof: `git diff <base> -- services/core/tests | grep -E "^-\s+assert" | grep -vE "plaid_(item|account|transaction|institution)_id|len\(routes\) =="` prints nothing (route-count tripwires go up with the new route, which strengthens them)

**C6** - `GET .../bank/connections` returns `provider: "plaid"` for a Plaid connection and `"flinks"` for a Flinks one (AC 4)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "list_shows_provider"`

### S2 - An owner connects a bank through Flinks · ~12 files · ~140 KB · ~35k

**C7** - `connect-url` returns `200` with `connect_url` on `https://toolbox-iframe.private.fin.ag/v2/`, whose query has the generated `authorizeToken`, `jsRedirect=true`, `daysOfTransactions=Days365`, `language=en` and `demo=true`, and `origin` `https://toolbox-iframe.private.fin.ag` (AC 5)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "connect_url_sandbox"`

**C8** - With `FLINKS_INSTANCE=acme`, `connect_url` is on `https://acme-iframe.private.fin.ag/v2/` and carries no `demo` parameter (AC 5)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "connect_url_production_has_no_demo"`

**C9** - With any of the four `FLINKS_*` settings unset, `connect-url` returns `404` `application/problem+json`, table-driven over all 4 (AC 6)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "connect_url_not_configured"`

**C10** - A bookkeeper member gets `403` and a user from another business gets `404` from `connect-url` and from a Flinks `POST .../connections` (AC 7)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "connect_url_denied or flinks_connect_denied"`

**C11** - A Flinks connect returns `201` and stores one connection with `provider='flinks'`, `provider_item_id = sha256(login_id)`, the loginId decryptable from `access_token_ciphertext`, accounts with `mask` = `LastFourDigits`, and a `bank_connection.created` audit entry whose details include `provider: "flinks"` (AC 8, door 4)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "flinks_connect_stores_connection"`

**C12** - Flinks account `Type` maps `Chequing`→`checking`, `Savings`→`savings`, `CreditCard`→`credit_card`, `LineOfCredit`→`line_of_credit`, and an unknown value→`other`, table-driven over all 5 (AC 8)
Proof: `uv run pytest tests/test_flinks_client.py -k "account_type_mapping"`

**C13** - A Flinks connect queues `sync_in_background` for the new connection once (AC 8)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "flinks_connect_queues_first_sync"`

**C14** - A Flinks connect calls `SetScheduledRefresh` with `{"loginId": <id>, "isActivated": true}` (AC 9)
Proof: `uv run pytest tests/test_flinks_client.py -k "enable_nightly_refresh_body"`
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "flinks_connect_enables_refresh"`

**C15** - `POST .../connections` returns `422` for each of: `flinks` with `public_token`, `plaid` with `login_id`, both fields, neither field, and a `login_id` that isn't a UUID, table-driven over all 5. Plaid with only `public_token` (no `provider`) still returns `201` (AC 10)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "connect_body_validation"`

**C16** - A second Flinks connect to the same `InstitutionId` for the business returns `409` and leaves one connection (AC 11)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "flinks_duplicate_institution_is_409"`

**C17** - When `GetAccountsDetail` answers `202` and all 3 async polls answer `202`, connect returns `503` with detail "Your bank is still preparing your accounts. Try again in a minute.", stores no connection, and does not call `DeleteCard`. A retry with the same `login_id` that gets `200` returns `201` (AC 12)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "flinks_connect_still_preparing"`

**C18** - The HTTP client polls `GetAccountsDetailAsync/{RequestId}` with a 10 s interval through an injected sleep, and stops after the given budget (3 on connect, 30 in a sync) (door 3)
Proof: `uv run pytest tests/test_flinks_client.py -k "async_poll_budget"`

**C19** - A Flinks `4xx`/`5xx` or an `httpx.TimeoutException` becomes `FlinksError` carrying only the HTTP status and `FlinksCode`, and connect answers `503` problem details. The client passes `timeout=15` (AC 13)
Proof: `uv run pytest tests/test_flinks_client.py -k "errors_carry_only_code or timeout_is_15s"`
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "flinks_failure_is_503"`

**C20** - Captured logs from a full Flinks connect, sync and failure contain neither the loginId, an `AccountNumber` value, nor the holder fields of the fake response, and no response JSON returns the loginId (AC 13, AC 14)
Proof: `uv run pytest tests/test_bank_connect_flinks.py -k "no_secrets_in_logs_or_responses"`

**C21** - Every `GetAccountsDetail` body sent has `WithAccountIdentity: false` and `WithKYC: false`. `AccountNumber` is never stored (no column receives it) (AC 14)
Proof: `uv run pytest tests/test_flinks_client.py -k "accounts_detail_body_excludes_identity"`

### S3 - Flinks connections sync like Plaid connections · ~8 files · ~120 KB · ~30k

**C22** - A first Flinks sync (`last_synced_at` null) requests `DaysOfTransactions: Days365`. The next requests `Days90` (AC 15)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "first_sync_days365_then_days90"`

**C23** - A Flinks transaction with `Credit: 12.345` stores `amount_cents = 1234` (half-even), and `Debit: 50.10` stores `-5010`. Both have `pending = false`, `description` = `Description` and `date` = `Date` (AC 16)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "transaction_values_and_sign"`

**C24** - Syncing the same Flinks response twice adds then changes nothing (`added` N, then 0/0/0). A response with one changed amount reports `modified = 1`, and the row count is unchanged (AC 17)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "resync_is_idempotent_and_modifies"`

**C25** - A stored Flinks transaction missing from the next response is still stored, and `removed = 0` (AC 18)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "absent_transaction_is_kept"`

**C26** - After a Flinks sync, `last_synced_at` = `Login.LastRefresh` when that is earlier than `now`, and = `now` when `LastRefresh` is later or missing (AC 19, door 5)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "last_synced_at_follows_last_refresh"`

**C27** - A Flinks sync writes `balance_cents`/`available_cents` from `Balance.Current`/`Balance.Available`, relabels the business, and publishes one `transactions.synced` with `connection_id`. A sync that changes nothing publishes none (AC 19)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "balances_relabel_and_event"`

**C28** - `run_nightly_syncs` syncs a due Flinks connection through `Authorize` with `MostRecentCached: true`, and a failing one follows the 1, 2, 4-hour retry schedule into `failed_nights` like Plaid (AC 20)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "nightly_syncs_flinks or nightly_flinks_retries"`
Proof: `uv run pytest tests/test_flinks_client.py -k "authorize_cached_body"`

**C29** - A sync whose `Authorize` fails with `INVALID_LOGIN` or `DISABLED_LOGIN` (both, table-driven) sets `login_required = true`, and `status` reads `login_required`. Any other `FlinksCode` leaves it false (AC 21)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "login_codes_set_login_required"`

**C30** - Disconnecting a Flinks connection calls `DeleteCard` with its loginId and returns `204`. When `DeleteCard` fails, the local rows are still deleted and `bank_connection.orphaned` is logged with `connection_id` and no loginId (AC 22)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "disconnect_flinks"`

**C31** - `POST .../connections/{id}/link-token` for a Flinks connection returns `409` with detail "Reconnect this bank: disconnect it, then connect it again." (AC 23)
Proof: `uv run pytest tests/test_bank_sync_flinks.py -k "flinks_link_token_is_409"`

**C32** - Against the Flinks sandbox: connect `FlinksCapital`/`Greatday`, sync twice, and every transaction `Id` from the first sync is matched by the second (assumption: stable IDs). Runs only with `-m flinks_sandbox`, and is blocked by open question 1
Proof: `uv run pytest -m flinks_sandbox tests/test_bank_flinks_sandbox.py -k "transaction_ids_are_stable"`

### S4 - The owner chooses the provider on screen · ~16 files · ~75 KB · ~20k

**C33** - With a connect URL, `ConnectBank` renders "Connect with Plaid", "Connect with Flinks" and the RBC hint from `messages/en.json`. Without one, it renders only the Plaid action, and a non-404 loader failure calls `Sentry.captureException` (AC 24, AC 25)
Proof: `npx vitest run tests/connect-bank.test.tsx -t "provider choice"`
Proof: `npx vitest run tests/bank-api-flinks.test.ts -t "connect url loader"`

**C34** - Choosing Flinks opens a dialog with the iframe and a loading indicator until `load`. Esc closes it and focus returns to the Flinks button. A `message` whose `origin` differs is ignored. A `REDIRECT` message from the matching origin calls `connectBank` with `{provider: "flinks", loginId}` (AC 26, AC 27)
Proof: `npx vitest run tests/flinks-connect.test.tsx -t "dialog loading and focus"`
Proof: `npx vitest run tests/flinks-connect.test.tsx -t "message origin"`

**C35** - The connect action posts `{provider: "flinks", login_id}`. On `503` it returns `stillPreparing`, and the screen shows "Your bank is still preparing your accounts. Try again in a minute." with a Retry that re-posts the same loginId. `409` shows the existing already-connected error (AC 28)
Proof: `npx vitest run tests/connect-bank-action.test.ts -t "flinks"`
Proof: `npx vitest run tests/flinks-connect.test.tsx -t "still preparing retry"`

**C36** - The bank settings card shows "via Plaid" or "via Flinks", and a Flinks connection needing attention shows "Disconnect it, then connect it again." with no Reconnect button (AC 29)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "provider"`

**C37** - On `/onboarding/bank` at 375 px: no horizontal scroll, both actions reachable by Tab, targets at least 44 px, and axe reports no violations with the Flinks dialog closed and open (AC 30). The Flinks-configured run needs sandbox credentials (open question 1). Until then, the run with Flinks off proves the Plaid-only layout
Proof: `npx playwright test e2e/bank-connect.spec.ts -g "C43|flinks layout keyboard and axe"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `POST /v1/businesses/{business_id}/bank/flinks/connect-url` statuses (4) | 200 C7 · 403 C10 · 404 C9, C10 · 503 C19 | - |
| `POST /v1/businesses/{business_id}/bank/connections` statuses (6) | 201 C11, C15 · 403 C10 · 404 C10 · 409 C16 · 422 C15 · 503 C17, C19 | - |
| `GET /v1/businesses/{business_id}/bank/connections` statuses (1) | 200 C6 | - |
| `POST /v1/businesses/{business_id}/bank/connections/{connection_id}/link-token` new status (1) | 409 C31 | - |
| Landing doors (5) | 1 C1, C3, C4 · 2 C24, C28 · 3 C18, C19 · 4 C11, C20, C21 · 5 C26 | - |
| connect body combinations (5) | flinks+public_token C15 · plaid+login_id C15 · both C15 · neither C15 · bad UUID C15 | - |
| `FLINKS_*` settings unset (4) | C9, table-driven over all 4 | - |
| Flinks `Type` mapping (5) | C12, table-driven over all 5 | - |
| login-required `FlinksCode` (3) | `INVALID_LOGIN` C29 · `DISABLED_LOGIN` C29 · other C29 | - |
| connect-bank surfaces (3) | onboarding step 3 C33, C37 · choose-accounts "Connect another bank" C33 · bank settings C33, C36 | - |
| screen states (4) | loading C34 · error C35 · Flinks off/empty C33 · unauthorised C10 (the API denies; the page keeps `auth.protect()`) | - |
| startup config: Flinks client wiring (3 assemblies) | API dependency `get_bank_providers` C7 · jobs `nightly_bank_sync` C28 · test harness override C11 | - |

- Claims naming a status code, route or response shape: C6, C7, C9, C10, C11, C15, C16, C17, C19, C31. Each has a proof through the FastAPI `TestClient`.
- C32 and C37 (with Flinks on) are blocked by open question 1 (Flinks sandbox credentials). The verification report records them as blocked, not passed.

## Swept

- validation: C15 (body combinations, UUID), C9 (settings)
- failure modes: C17 (still preparing, nothing stored), C30 (DeleteCard fails, local delete continues)
- idempotency: C24 (resync), C17 (retry with the same loginId after 503)
- authorization: C10. Existing `require_owner` (AD-031) guards both routes.
- concurrency: existing. AD-046 / AD-058 lock order (connection, then accounts) is reused unchanged by the Flinks sync path, and C4's unique index settles two racing connects (the existing `DuplicateBankError` path).
- data lifecycle: C30 (DeleteCard removes Flinks-held data), C25 (no deletion from absence)
- dependency failure: C19 (error/timeout → 503), C28 (nightly retries)
- state transitions: C29 (`login_required`), C26 (freshness feeds the existing status precedence)
- observability: C20 (no secrets in logs), C30 (`bank_connection.orphaned`)

## Handoff

- S1 = 37 files, 522 KB on disk, but the rename is a `sed` over identifiers that loads none of those files into context. The read set is `models.py`, `repository.py`, the migration, its test and `fixtures/plaid.py`: ~95 KB → ~25k
- S2 = `flinks.py` (new), `service.py`, `api.py`, `settings.py`, tests: ~140 KB → ~35k, total 60k
- S3 = `service.py` sync/nightly/disconnect (already read), `jobs/nightly.py`, the sync tests: ~120 KB → ~30k, total 90k
- S4 enters the web at ~75 KB → ~20k, total 110k, under the 150k budget. One builder.
- Mechanism: one builder (the estimate fit the budget)
- **Boundary:** C1-C37 closed at `bd3a9a0` (C32 and the Flinks-on part of C37 are blocked by open question 1: no Flinks sandbox credentials)
- **Settled mid-build:** the institution unique was renamed `uq_bank_connections_business_provider_institution` (63-character limit, plan Landing 1a). Callers pass `flinks=` as a keyword instead of a `BankProviders` holder (plan Landing 2a), so the startup-config member "API dependency" is `get_flinks_client`. The CSP change became a violation row in `context/security/rules.md`, following that file's precedent (AD-130), instead of a policy edit. The log redactor now hides the loginId in httpx's `DeleteCard/{loginId}` request line. The Plaid audit details stay unchanged (no `provider` key) so that C5 holds. The migration downgrade refuses while a Flinks connection exists.
- **Abandoned:** S1's `sed` rename also rewrote `tests/test_migrations.py`, which checks older revisions that still have `plaid_*` columns. Restored in `8503eb3`.
- **Round 1 fixes (verification round 1):** F1: the log/Sentry redactor gains `login_id`, `loginid`, `accountnumber`, `holder`, `username`, `api-key` and `auth-key`, and a malformed Flinks answer becomes `FlinksError(INVALID_RESPONSE)` with its context dropped (503, not a 500 with raw frames). F2: `LastRefresh` also parses in yyyy/MM/dd form. F4: there is no institution-name fallback for `InstitutionId`. G2: added e2e `flinks layout keyboard and axe`, which skips as blocked while Flinks is not configured. G3: C5's grep proof now excludes the route-count tripwire lines (the claim is unchanged). G4: added choose-accounts provider-choice tests.
