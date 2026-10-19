# Yodlee as a second bank provider - checks

Profile: light
Plan: `.specs/features/17b-bank-yodlee-provider/plan.md`

49 checks in 8 slices · 7 one-way doors · 3 open, of which 1 blocks the build (sandbox shapes) and 2 block go-live (RBC authenticator proof; Yodlee agreement)

API proofs run from `services/core`, web proofs from `frontend`. Profile `light` is the default (AGENTS.md declares none). Because this touches secrets and a screen, `standard` would add the recomputed coverage join; say so if you want it raised.

## Checks

### S1 - The schema and the seam accept a Yodlee provider, with Plaid unchanged · 6 files · ~50 KB · ~12k

**C1** - `bank_connections` accepts `provider = 'yodlee'` and `'plaid'`, and rejects `'other'` on `ck_bank_connections_provider` (AC 1, door 1)
Proof: `uv run pytest tests/test_bank_yodlee_migration.py -k "provider_check_accepts_yodlee"`

**C2** - The downgrade fails while a `yodlee` connection exists and deletes nothing (AC 2)
Proof: `uv run pytest tests/test_bank_yodlee_migration.py -k "downgrade_refuses_with_yodlee_rows"`

**C3** - With no `yodlee` rows, the downgrade restores the check to `provider IN ('plaid')` (door 1)
Proof: `uv run pytest tests/test_bank_yodlee_migration.py -k "downgrade_restores_plaid_only"`

**C4** - The existing Plaid connect, accounts, sync, nightly, settings, webhook and fixture suites pass, and no existing assertion was weakened or removed; the only edited assertions are the two route-count tripwires in `services/core/tests/test_security_rules.py` (28 to 30 and 35 to 37, one per new route) (AC 3)
Proof: `uv run pytest tests/test_bank_connect.py tests/test_bank_accounts.py tests/test_bank_connection_nightly.py tests/test_bank_connection_settings.py tests/test_plaid_webhook.py tests/test_plaid_item_webhooks.py tests/test_plaid_client.py`
Proof: `git diff <base>..HEAD -- services/core/tests | grep -E "^-\s+assert"` prints exactly `assert len(routes) == 28` and `assert len(routes) == 35`, both in `test_security_rules.py`, and nothing else

**C5** - `GET .../bank/connections` returns `provider: "yodlee"` for a Yodlee connection and `"plaid"` for a Plaid one (AC 4)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "list_shows_provider"`

### S2 - Yodlee is reached through one port that fails safely · 3 files · ~35 KB · ~10k

**C6** - With any one of the six `YODLEE_*` settings unset, `GET .../bank/providers` omits `yodlee` and `POST .../yodlee/fastlink` returns `404`, for each of the six settings (AC 5)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "off_when_any_setting_unset"` (table-driven, 6 cases)

**C7** - A Yodlee call that exceeds 15 s raises `YodleeError` with `http_status` `None` (AC 6)
Proof: `uv run pytest tests/test_yodlee_client.py -k "timeout_raises_yodlee_error"`
Proof: `uv run pytest tests/test_yodlee_client.py -k "timeout_is_15_seconds"`

**C8** - A Yodlee error response yields a `YodleeError` whose `http_status` and `error_code` are set and whose message and attributes contain none of the response body (AC 7)
Proof: `uv run pytest tests/test_yodlee_client.py -k "error_carries_no_body"`

**C9** - The client returns a DEBIT of 25.00 as `+25.0` and a CREDIT of 25.00 as `-25.0` (positive is money out) (AC 8)
Proof: `uv run pytest tests/test_yodlee_client.py -k "debit_credit_sign"`

**C10** - Given POSTED and PENDING transactions, the client returns only the POSTED ones (AC 9)
Proof: `uv run pytest tests/test_yodlee_client.py -k "only_posted"`

**C11** - A synced DEBIT of 25.00 CAD is stored with `amount_cents = -2500` and a CREDIT of 25.00 with `2500` (AC 8, one sign flip)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "stored_amount_sign"`

### S3 - An owner can open FastLink · 3 files · ~45 KB · ~12k

**C12** - `GET .../bank/providers` returns `200` with `providers == ["plaid", "yodlee"]` when configured and `["plaid"]` when not (AC 5, door 7 surface)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "providers_lists_yodlee"`

**C13** - For a business with no Yodlee user, `POST .../yodlee/fastlink` registers `hr-<business id hex>` once and returns `200` with `fastlink_url`, a user-scoped `access_token`, `config_name` and `expires_in` (AC 10, doors 2 and 7)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "fastlink_registers_user"`

**C14** - A second call for the same business does not register the user again (AC 11)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "fastlink_does_not_register_twice"`

**C15** - With `connection_id` of that business's Yodlee connection, the response carries the edit-mode launch parameters for that provider account (AC 12)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "fastlink_edit_mode"`

**C16** - With `connection_id` of a Plaid connection the route returns `409` (AC 13)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "fastlink_plaid_connection_409"`

**C17** - When Yodlee fails, the route returns `503` as `application/problem+json` and the body contains no Yodlee detail (AC 14)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "fastlink_yodlee_failure_503"`

**C18** - After a fastlink call, the captured logs and Sentry events contain neither the access token, the client secret nor the admin login name (AC 15, door 7)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "fastlink_secrets_not_logged"`
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "no_yodlee_secret_in_logs_or_sentry"`
Proof: `uv run pytest tests/test_log.py -k "yodlee"`

**C19** - The user token is requested with the business's `hr-` loginName and never with `YODLEE_ADMIN_LOGIN_NAME` (AC 40)
Proof: `uv run pytest tests/test_yodlee_client.py -k "user_token_never_admin"`

### S4 - An owner can connect a bank through FastLink · 3 files · ~60 KB · ~15k

**C20** - Posting `provider = yodlee` and a `provider_account_id` returns `201`; the connection stores `provider_item_id` = that ID, the encrypted loginName (decrypts to `hr-<business id hex>`), an audit entry, and a first sync is scheduled (AC 16, door 2)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "connect_stores_connection"`

**C21** - Of a checking CAD, a savings CAD, a checking USD and a credit-card account, only the checking CAD account is stored `included` (AC 17)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "connect_includes_checking_cad_only"`

**C22** - Connecting the same Yodlee institution twice for one business returns `409` and stores no second connection (AC 18)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "connect_duplicate_409"`

**C23** - `provider = yodlee` with `public_token`, `provider = plaid` with `provider_account_id`, and neither field each return `422` (AC 19)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "connect_field_mismatch_422"` (table-driven, 3 cases)

**C24** - When Yodlee returns no accounts for the provider account, nothing is stored, the provider account is deleted at Yodlee, and the route returns `503` (AC 20)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "connect_failure_cleans_up"`

**C25** - A synced Yodlee transaction with ID `123` is stored with `provider_transaction_id = "yodlee:123"` (door 5)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "transaction_id_prefixed"`

### S5 - A Yodlee connection syncs like a Plaid one · 4 files · ~120 KB · ~28k

**C26** - Syncing a Yodlee connection with 3 POSTED transactions adds 3 rows and publishes one `transactions.synced` with `added = 3` (AC 21, door 4)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "sync_upserts_and_publishes"`

**C27** - Syncing the same snapshot a second time adds 0, modifies 0, removes 0 and publishes no event (AC 22)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "sync_twice_changes_nothing"`

**C28** - A first sync (`last_synced_at` null) requests 730 days back and a later sync requests 90 days back (AC 23)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "sync_window_first_and_later"`

**C29** - With the provider account last refreshed 10 hours before now, `last_synced_at` is that earlier time; with it refreshed after now, `last_synced_at` is now (AC 24, door 6)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "last_synced_at_is_earlier_of"`

**C30** - When Yodlee reports the bank needs a new login, `login_required` becomes true and the connection `status` reads `login_required` (AC 25)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "login_required_status"`

**C31** - The nightly job syncs a due Yodlee connection, retries a failure after 1 hour, and ends the night after the fourth failure with `failed_nights` 1 (AC 26, door 4)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "nightly_syncs_due_yodlee"`

**C32** - When a Yodlee call fails halfway through a sync, no transaction, balance or `last_synced_at` changes (AC 27)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "sync_failure_rolls_back"`

### S6 - An owner can repair and disconnect a Yodlee bank · 2 files · ~55 KB · ~12k

**C33** - Disconnecting calls Yodlee's delete first, and only then removes the connection, its accounts and its transactions (AC 28)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "disconnect_deletes_remote_first"`

**C34** - When Yodlee's delete fails with a non-"not found" error, the route returns `503` and the connection, accounts and transactions remain (AC 29)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "disconnect_remote_failure"`
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "repair_and_disconnect_over_http"`

**C35** - When Yodlee says the provider account does not exist, the disconnect succeeds and removes the local rows (AC 30)
Proof: `uv run pytest tests/test_bank_sync_yodlee.py -k "disconnect_remote_not_found"`

**C36** - `POST .../link-token` for a Yodlee connection returns `409` (AC 31)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "link_token_409"`

### S7 - The connect-bank screen offers Yodlee · 10 files · ~75 KB · ~22k

**C37** - The connect-bank screen shows a Yodlee action when `providers` includes `yodlee`, and only the Plaid action otherwise (AC 32)
Proof: `npx vitest run tests/connect-bank.test.tsx -t "yodlee action"`

**C38** - While FastLink is opening, the Yodlee action is disabled and a loading message from `en.json` is announced (AC 33)
Proof: `npx vitest run tests/yodlee-connect.test.tsx -t "loading"`

**C39** - When the fastlink route fails, the error message from `en.json` shows and the action can be retried (AC 34)
Proof: `npx vitest run tests/yodlee-connect.test.tsx -t "error and retry"`

**C40** - FastLink's `onSuccess` with `providerAccountId` `42` calls the connect server action with `provider = yodlee` and `provider_account_id = "42"` (AC 35)
Proof: `npx vitest run tests/yodlee-connect.test.tsx -t "success posts provider account"`
Proof: `npx vitest run tests/connect-yodlee-bank-action.test.ts -t "sends the yodlee provider"`

**C41** - Closing FastLink without success returns the screen to its initial state and calls no connect action (AC 36)
Proof: `npx vitest run tests/yodlee-connect.test.tsx -t "close returns to start"`

**C42** - Every string the new components render comes from `messages/en.json` (AC 37)
Proof: `npx vitest run tests/yodlee-connect.test.tsx -t "copy from messages"`

**C43** - For a Yodlee connection with status `login_required`, settings offers a reconnect that opens FastLink in edit mode and then calls the repair action (AC 38)
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "yodlee reconnect"`

**C44** - On the running app at 375 px width, the connect-bank screen with the Yodlee action has no axe violations, every control is at least 44 px tall, and the action is reachable and activated by keyboard alone (AC 37)
Proof: `npx playwright test e2e/bank-yodlee.spec.ts`

**C45** - The Content-Security-Policy-Report-Only header allows `https://cdn.yodlee.com` in `script-src` and the FastLink host in `frame-src` (Impact, config)
Proof: `npx vitest run tests/security-headers.test.ts -t "yodlee"`

**C50** - On the first activation of the Yodlee action, and of the settings reconnect, the element `#container-fastlink` is in the document when `window.fastlink.open` is called, so no error shows; after a failed open, the container is gone (the-judge F1, user decision 2026-10-19; AC 32, AC 38)
Proof: `npx vitest run tests/yodlee-connect.test.tsx -t "container exists when fastlink opens"`
Proof: `npx vitest run tests/bank-settings-page.test.tsx -t "reconnect container exists when fastlink opens"`

### S8 - Access and secrets · 3 files · ~30 KB · ~8k

**C46** - A user from another business gets `404` from `GET .../bank/providers`, `POST .../yodlee/fastlink` and `POST .../bank/connections` with `provider = yodlee` (AC 39)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "other_business_denied"` (table-driven, 3 routes)

**C47** - A business member who is not an owner gets `403` from the same three routes (AC 39)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "non_owner_denied"` (table-driven, 3 routes)

**C48** - An unknown business ID gets `404` from the same three routes (AC 39)
Proof: `uv run pytest tests/test_bank_connect_yodlee.py -k "unknown_business_404"` (table-driven, 3 routes)

**C49** - The deploy check fails when staging and production share a Yodlee client ID or secret, and prints no value (AC 41)
Proof: `uv run pytest ../../.specs/features/34-launch-production/test_check_no_shared_credentials.py -k "yodlee"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /v1/businesses/{business_id}/bank/providers` statuses (3) | 200 C12 · 403 C47 · 404 C46, C48 | - |
| `POST /v1/businesses/{business_id}/bank/yodlee/fastlink` statuses (5) | 200 C13 · 403 C47 · 404 C6, C46, C48 · 409 C16 · 503 C17 | - |
| `POST /v1/businesses/{business_id}/bank/connections` statuses (6) | 201 C20 · 403 C47 · 404 C46, C48 · 409 C22 · 422 C23 · 503 C24 | - |
| `POST /v1/businesses/{business_id}/bank/connections/{connection_id}/link-token` new status (1) | 409 C36 | - |
| `YODLEE_*` settings (6) | `YODLEE_API_URL`, `YODLEE_CLIENT_ID`, `YODLEE_CLIENT_SECRET`, `YODLEE_ADMIN_LOGIN_NAME`, `YODLEE_FASTLINK_URL`, `YODLEE_FASTLINK_CONFIG_NAME` each C6, table-driven over all 6 | - |
| one-way doors (7) | 1 C1, C3 · 2 C13, C20 · 3 C7, C8 · 4 C26, C31 · 5 C25 · 6 C29 · 7 C13, C18 | - |
| entities (3) | `bank_connections` C20 · `bank_accounts` C21 · `bank_transactions` C25 | - |
| account kinds on connect (4) | checking CAD C21 · savings CAD C21 · checking USD C21 · credit card C21 | - |
| connect field combinations (3) | yodlee+`public_token` C23 · plaid+`provider_account_id` C23 · neither C23 | - |
| callers of the Yodlee client (3 assemblies) | API app C13 · nightly job C31 · background first sync C20 | - |
| roles denied on the 3 new routes (2) | other business C46 · non-owner C47 | - |

- Claims naming a status code, route or response shape: C6, C12-C17, C20, C22-C24, C36, C46-C48 - each proof crosses the HTTP boundary through the test client
- C4's second proof is a tripwire on edited assertions, not a behaviour test
- No other check claims more than the single case its proof exercises

## Swept

- validation: C23, C21
- failure modes: C24, C32, C34
- idempotency: C27, C14
- authorization: C46, C47, C48, C19
- concurrency: existing - the connection row lock and account locks that `_sync_locked` takes for Plaid (AD-046, AD-053) cover Yodlee because it runs through the same function; C31 exercises the nightly claim
- data lifecycle: C33, C35
- dependency failure: C7, C8, C17, C32
- state transitions: C30
- observability: C18

## Handoff

Estimates are bytes read plus bytes written, divided by four, from `wc -c` on the files each slice touches.

- S1 = 12k (migration, `models.py` check text, test_migrations neighbour); S2 = 10k (new `yodlee.py` ~25 KB, settings 6 KB); both in `bank_sync`/settings, total 22k
- S3-S4 = 27k (`api.py` 16 KB, `service.py` connect path); total 49k, still the API surface
- S5-S6 = 40k (`service.py` 45 KB read, new tests); total 89k, API complete
- S7 = 22k (about 10 web files, 60 KB); total 111k
- S8 = 8k; total 119k, under the 150k budget - one builder

Mechanism: one builder.

- **Boundary:** C1-C49 closed; proofs green at `62e719f` (API 1182 passed, web 421 passed, `npm run build`, Playwright C44)
- **Settled mid-build:**
  - Door 2a (`YODLEE_TEST_LOGIN_NAME`): the sandbox refuses `POST /user/register` with `Y820`; the user supplied one sandbox test user.
  - The user approved the plan with a second button for every owner, where the API offers Yodlee.
  - Yodlee failures answer `503` as the plan's `Surface` says; the Plaid routes answer `502`. Both stay.
  - C45 is met by `script-src` and `frame-src` directives added to the report-only CSP in `frontend/lib/security-headers.ts`; the plan's Impact said the same.
  - The Plaid connect call now sends `provider: "plaid"` (the generated type requires it), so one assertion in `frontend/tests/connect-bank-action.test.ts` gained the key, as in spec 17a.
  - `tests/test_security_rules.py` route counts went 28 -> 30 and 35 -> 37, and `tests/test_bookkeeper_access.py` lists the two new owner-only routes.
- **Abandoned:** nothing. The spec 34 shared-credential check allows `YODLEE_FASTLINK_CONFIG_NAME` (a name, not a credential).
- **Not proven by any check:** whether RBC with an authenticator app connects through Yodlee in production, and the live `register_user` call (the sandbox cannot register). Both block go-live (plan Open questions 2 and 3).

