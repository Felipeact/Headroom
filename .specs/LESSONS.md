# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Plan/Checks)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - GitHub computes a pull request's mergeStateStatus lazily and can answer UNKNOWN right after a push; a proof reading it must retry until it settles.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `ci` · harmful: 0
- features: 04-setup-tests-and-ci
- evidence: .specs/features/04-setup-tests-and-ci/proofs.sh:169 (ci)
- last seen: 2026-10-02T02:53:30Z

### L-002 - When a criterion names several file kinds (.ts and .tsx), the proof must exercise each kind, not just one.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `frontend` · harmful: 0
- features: 04-setup-tests-and-ci
- evidence: AC 2 (frontend)
- last seen: 2026-10-02T02:53:31Z

### L-003 - Prove a table exists by querying the schema, not by a command that exits 0 when the table is absent
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `migrations` · harmful: 0
- features: 05-setup-railway-staging
- evidence: C3 - proofs.sh:81 (migrations)
- last seen: 2026-10-02T03:37:24Z

### L-004 - Get user confirmation before a check asserts a command or name different from the literal the binding spec gives
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `deploy` · harmful: 0
- features: 05-setup-railway-staging
- evidence: C20 - proofs.sh:251-252; plan.md:128 (deploy)
- last seen: 2026-10-02T03:37:24Z

### L-005 - When a screen renders the same control in two places (desktop nav and a phone menu Dialog), assert the per-control metric in both placements, and read sizes only after the Dialog's open animation settles.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `frontend/e2e` · harmful: 0
- features: 07-web-app-shell
- evidence: checks.md C5 / e2e/shell.spec.ts (frontend/e2e)
- last seen: 2026-10-02T16:06:57Z

### L-006 - A 'no secret in source' check must name the file set its proof scans (git-tracked or would-track), because the ignored .env.local is where the secret is meant to live.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `frontend/tests` · harmful: 0
- features: 07-web-app-shell
- evidence: checks.md C41 (frontend/tests)
- last seen: 2026-10-02T16:06:57Z

### L-007 - Pin generated files to LF in .gitattributes, because Git for Windows defaults core.autocrlf=true and a 'regenerated output is clean' check then fails on identical bytes.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `git` · harmful: 0
- features: 09-api-typed-client
- evidence: C5 - proofs.sh:28-29 (git)
- last seen: 2026-10-02T20:51:47Z

### L-008 - Write tr -d '\r' as an escape, never a literal control character: editors and scripted edits turn a raw CR into an LF.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `proofs` · harmful: 0
- features: 09-api-typed-client
- evidence: C16-C18 - proofs.sh:90-101 (proofs)
- last seen: 2026-10-02T20:51:47Z

### L-009 - A proof that a build fails must grep the expected error in the output, not only check the exit code.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `proofs` · harmful: 0
- features: 09-api-typed-client
- evidence: C9 - proofs.sh:50 (proofs)
- last seen: 2026-10-02T20:51:47Z

### L-010 - A no-focus-trap assertion must check where focus ends up (body or back to the first element), not just that focus took more than one value.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `frontend/e2e` · harmful: 0
- features: 09-api-typed-client
- evidence: C15 - e2e/api-check.spec.ts:40 (frontend/e2e)
- last seen: 2026-10-02T20:51:47Z

### L-011 - A test that checks an export by reading its output file must delete or alter that file first, or an already-committed current output lets a wrong path pass.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: 09-api-typed-client
- evidence: C1 - tests/test_export_openapi.py:42 (tests)
- last seen: 2026-10-02T21:02:46Z

### L-012 - A server render that forwards a short-lived session token must refresh it when it is near expiry, because a slow render can outlive the token before the API call.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `frontend/auth` · harmful: 0
- features: 10-accounts-login
- evidence: C28 - frontend/lib/api/auth.ts (frontend/auth)
- last seen: 2026-10-02T22:49:29Z

### L-013 - A check that says 'for each case in C2-C7' needs a table built from those checks' cases, counted against them, or a case gets dropped.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: 10-accounts-login
- evidence: C29 - services/core/tests/test_auth.py:217 (tests)
- last seen: 2026-10-02T22:49:29Z

### L-014 - Run axe only after animations settle when the steps before it can trigger a fade-in, such as a field error after blur.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `frontend/e2e` · harmful: 0
- features: 10-accounts-login
- evidence: C26 - frontend/e2e/auth.spec.ts:115 (frontend/e2e)
- last seen: 2026-10-02T22:49:29Z

### L-015 - Check the installed library for deprecations and CSS-variable support before fixing an integration's literal shape in a Landing row; docs pages can lag the package.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `frontend` · harmful: 0
- features: 10-accounts-login
- evidence: plan.md doors 7, 8 (frontend)
- last seen: 2026-10-02T22:49:29Z

### L-016 - Prove a screen's copy and order by rendering the real page or route component, never a tree the test assembles from parts.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `frontend/tests` · harmful: 0
- features: 11-accounts-businesses-and-access
- evidence: C26 frontend/tests/business-form.test.tsx (frontend/tests)
- last seen: 2026-10-04T17:44:56Z

### L-017 - When a mid-build settlement changes what an approved check claims, raise the check wording with the user at that moment instead of recording it only in Handoff.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `checks` · harmful: 0
- features: 11-accounts-businesses-and-access
- evidence: C39 checks.md (checks)
- last seen: 2026-10-04T17:44:56Z

### L-018 - A check that says 'with X's values' must assert every field of the response shape, not a sample.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `services/core/tests` · harmful: 0
- features: 11-accounts-businesses-and-access
- evidence: C14 services/core/tests/test_businesses.py (services/core/tests)
- last seen: 2026-10-04T17:44:56Z

### L-019 - When a check lists literal inputs, copy each literal into the test byte for byte; a near-miss (invalid JSON for a JSON string) tests a different case.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `api/tests` · harmful: 0
- features: 14-bank-transaction-sync
- evidence: C33 - services/core/tests/test_plaid_webhook.py:216 (api/tests)
- last seen: 2026-10-05T19:49:03Z

### L-020 - An optional setting a developer may keep in .env.local must be pinned in tests/conftest.py, and an 'unset' test must also disable the env file, or the local value leaks in.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `api/tests` · harmful: 0
- features: 14-bank-transaction-sync
- evidence: C38 - services/core/tests/conftest.py:29 (api/tests)
- last seen: 2026-10-05T19:49:03Z

### L-021 - Pin every database-defaulted timestamp a time-based rule reads in tests; a server now() default makes simulated-clock tests depend on the real date
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `tests, jobs` · harmful: 0
- features: 15-bank-nightly-sync-job
- evidence: verification.md round 2 finding 1; fixed in 004dc46 (tests/test_nightly_sync.py:52,148) (tests, jobs)
- last seen: 2026-10-06T02:18:12Z

### L-022 - To prove a write commits in the same transaction as another, compare against a row only that transaction writes, not rows a later transaction would also rewrite
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `repo-layer` · harmful: 0
- features: 16-bank-transaction-labels
- evidence: C21 - services/core/tests/test_transaction_labels.py:583 (repo-layer)
- last seen: 2026-10-06T02:52:38Z

### L-023 - When proving rows were deleted, count them by a key that survives the delete (business_id or saved IDs), never by joining through the parent rows that were deleted too.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `tests/bank_sync` · harmful: 0
- features: 17-bank-connection-settings
- evidence: services/core/tests/test_bank_connection_settings.py:173 (tests/bank_sync)
- last seen: 2026-10-06T16:43:23Z

### L-024 - Before writing screen checks, read the binding mockup's exact copy and controls; a check that paraphrases them (badge vs radio, type labels) forces a mid-build amendment.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `web/checks` · harmful: 0
- features: 17-bank-connection-settings
- evidence: checks.md:C9,C16 (web/checks)
- last seen: 2026-10-06T16:43:23Z

### L-025 - Never set tabIndex=-1 on a Radix RadioGroup root: no radio gets a tab stop; give each group only its radios and prove reachability with an e2e Tab walk.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `web/a11y` · harmful: 0
- features: 17-bank-connection-settings
- evidence: frontend/components/settings/account-row.tsx (web/a11y)
- last seen: 2026-10-06T16:43:23Z

### L-026 - To prove two generated lists differ in a value, compare paired elements; list inequality also passes when only the length changes.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: 18-forecast-sample-data
- evidence: C2 - tests/test_fixture_harbor_street.py:66 (tests)
- last seen: 2026-10-06T17:57:22Z

### L-027 - When a criterion names production wiring (subscriptions.register), the proof must go through that wiring, not a handler the test subscribes itself.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `events` · harmful: 0
- features: 18-forecast-sample-data
- evidence: C23 - tests/test_fixture_load.py:114 (events)
- last seen: 2026-10-06T17:57:22Z

### L-028 - Identifiers a fixture writes into globally unique columns must include the tenant or load ID, or a second load of the same fixture fails.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `fixtures` · harmful: 0
- features: 18-forecast-sample-data
- evidence: door 3 - plan.md Landing (fixtures)
- last seen: 2026-10-06T17:57:22Z

### L-029 - A rounding-rule test needs a tie that the wrong rule rounds differently; one tie both half-even and half-up agree on proves nothing.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: 19-forecast-recurring-payments
- evidence: C9 test_recurring_detection.py:292 (tests)
- last seen: 2026-10-06T22:43:27Z

### L-030 - A lock test must hold the first transaction open after its write and before its commit; a delay earlier lets it commit first and the race never happens.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `concurrency` · harmful: 0
- features: 19-forecast-recurring-payments
- evidence: C21 test_recurring_refresh.py concurrent_refreshes (concurrency)
- last seen: 2026-10-06T22:43:27Z

### L-031 - Before approving a numeric detection rule, run it against every seed of the sample data and the check's own examples; a fixed 15/16 split and a 75% share on 3 hits both failed on contact.
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `forecasting` · harmful: 0
- features: 19-forecast-recurring-payments
- evidence: plan AC 4 (two amendments) (forecasting)
- last seen: 2026-10-06T22:43:28Z

### L-032 - When a check quotes a displayed money value, write it as lib/format.ts renders it (whole dollars), not as the amount entered.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `frontend/e2e` · harmful: 0
- features: 20-forecast-expected-payments
- evidence: checks.md:341 (C45) (frontend/e2e)
- last seen: 2026-10-07T04:33:46Z

### L-033 - In a keyboard-only e2e step, type values into the focused input; locator.fill() bypasses the keyboard and does not prove the claim.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `frontend/e2e` · harmful: 0
- features: 20-forecast-expected-payments
- evidence: frontend/e2e/expected-payments.spec.ts:157 (C46) (frontend/e2e)
- last seen: 2026-10-07T04:33:47Z

### L-034 - Forward Tab from the last control before a visible Sonner toast bounces back; reach earlier controls with Shift+Tab, since body.focus() does not reset the tab start.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `frontend/e2e` · harmful: 0
- features: 20-forecast-expected-payments
- evidence: frontend/e2e/expected-payments.spec.ts:202 (C46) (frontend/e2e)
- last seen: 2026-10-07T04:33:48Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
