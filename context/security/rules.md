# Security rules and their proofs

One row for each bullet under "Security and data handling" in `AGENTS.md` (spec 33). A row names the
tests that prove the rule, or a written check with steps and the date it was last run. The test
`tests/test_security_rules.py::test_rules_table_tests_exist` fails when a named test is missing.

| Rule | Bullet | Proof |
| --- | --- | --- |
| R1 | Never log, print or return Plaid tokens, Clerk session tokens, account numbers or raw provider data | Proof: `services/core/tests/test_security_rules.py::test_error_bodies_leak_nothing`, `services/core/tests/test_log.py::test_secret_named_keys_redacted`, `services/core/tests/test_log.py::test_token_patterns_redacted_in_strings`, `services/core/tests/test_sentry.py::test_event_redacted_before_send`, `services/core/tests/test_api_hardening.py::test_rejection_log_is_scrubbed` |
| R2 | Encrypt Plaid access tokens with Fernet before storing them | Proof: `services/core/tests/test_bank_connect.py::test_token_encrypted`, `services/core/tests/test_settings.py::test_token_encryption_keys_rejected` |
| R3 | Verify each Plaid webhook's `Plaid-Verification` signature before doing any work | Proof: `services/core/tests/test_plaid_webhook.py::test_bad_header_rejected`, `services/core/tests/test_plaid_webhook.py::test_wrong_key_rejected`, `services/core/tests/test_plaid_webhook.py::test_stale_iat`, `services/core/tests/test_plaid_webhook.py::test_body_hash_mismatch`, `services/core/tests/test_plaid_webhook.py::test_expired_key` |
| R4 | Verify the Clerk session token on every API request | Proof: `services/core/tests/test_auth.py::test_every_v1_route_requires_token`, `services/core/tests/test_security_rules.py::test_unauthenticated_gets_401_with_challenge`, `services/core/tests/test_security_rules.py::test_public_list_is_exactly_four` |
| R5 | Enforce permissions on the server | Proof: `services/core/tests/test_bookkeeper_access.py::test_bookkeeper_gets_403_from_owner_routes`, `services/core/tests/test_bookkeeper_access.py::test_every_business_route_is_classified` |
| R6 | Every endpoint that returns customer data denies a user from another business | Proof: `services/core/tests/test_security_rules.py::test_stranger_denied_on_every_business_route`, `services/core/tests/test_security_rules.py::test_every_v1_route_is_classified` |
| R7 | Use only synthetic data and the Plaid sandbox | Written check: 1. Run `git grep -nIiE "plaid_env\s*=\s*production" -- . ":!context" ":!.specs"` and confirm no match outside documents. 2. Confirm `python -m app.fixtures.load` refuses a non-local host (`services/core/tests/test_fixture_load.py::test_refuses_non_local_database`). 3. Open the Plaid dashboard and confirm local and staging use sandbox keys. 4. Search the repository for a real customer name or account number; there is none. Last run: 2026-10-15 |
| R8 | Keep secrets only in environment variables | Proof: `services/core/tests/test_security_rules.py::test_no_env_files_or_secrets_tracked` |

## Content-Security-Policy report-only violations

The web app sends `Content-Security-Policy-Report-Only` (spec 33, door 3). Each violation seen while
opening every screen is listed here with a decision. The policy is not enforced until this list is
empty or every row says "allow in the policy".

| Screen | Violation | Decision |
| --- | --- | --- |
| `/sign-in` | Clerk scripts from `*.clerk.accounts.dev` blocked by `default-src 'self'` | Allow `script-src` and `connect-src` for the Clerk frontend host before enforcing |
| `/sign-in` | Clerk worker from a `blob:` URL | Allow `worker-src blob:` before enforcing |
| `/sign-in` | Clerk telemetry to `clerk-telemetry.com` | Allow `connect-src` for it, or turn Clerk telemetry off |
| `/sign-in` | Clerk images from `img.clerk.com` and `data:` images | Allow `img-src` for both before enforcing |
| `/sign-in` | Sentry events to `*.ingest.us.sentry.io` | Allow `connect-src` for the Sentry ingest host before enforcing |
| `/sign-in` | Next.js and Clerk inline scripts and inline styles | Needs a per-request nonce (`script-src` with `'nonce-...'`) before enforcing; do not add `'unsafe-inline'` |
