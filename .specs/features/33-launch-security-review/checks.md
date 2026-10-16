# Spec 33: Security review checks

Profile: light
Plan: `.specs/features/33-launch-security-review/plan.md`

32 checks in 6 slices · 8 one-way doors (4 approved, 2 found while writing the checks, 2 found in review) · 3 open, of which 2 block go-live

Unless noted, `uv run` proofs run from `services/core` and `npx vitest` proofs from `frontend`. API tests use `TestClient(app)` and the `Caller` helpers of `tests/test_businesses.py` and `tests/tokens.py`, as `tests/test_bookkeeper_access.py` does; the limiter reads its time from one function the tests replace, so no test sleeps. New API test files: `tests/test_api_hardening.py` (S1) and `tests/test_security_rules.py` (S3, S4, S5). New web test: `tests/security-headers.test.ts`. No test calls Plaid, Clerk, Resend or PostHog.

Plan corrections found while writing these checks, both additive (plan.md `Landing` rows 5 and 6, written before the code):

- Door 2 said `/v1` gets 60 requests a minute per IP before authentication. The web server is the only caller of `/v1` (AD-017), so every user shares its IP and that limit would throttle the whole product. The per-IP limit on `/v1` counts only requests that fail authentication (`401`); signed-in traffic is limited per user (C5).
- FastAPI serves `/docs`, `/redoc` and `/openapi.json` with no login, which AC 13's "exactly four public routes" would have excluded without saying so. They are off unless `API_DOCS_ENABLED=true` (C20).

## Checks

### S1 - The API refuses browsers and floods · `app/main.py`, `app/ratelimit.py`, `app/security.py`, `app/settings.py`, tests · ~8 files · 40 KB · ~12k

**C1** - A request with `Origin: https://evil.example` to `GET /v1/me`, `POST /v1/businesses`, `POST /v1/webhooks/plaid` and `POST /v1/unsubscribe/{token}` answers `403` `application/problem+json` with detail `"Browser requests are not allowed."`; the `POST /v1/businesses` call, sent with a valid token and body, creates no `businesses` row; the same requests without `Origin` do not answer `403` (AC 1, door 1)
Proof: `uv run pytest tests/test_api_hardening.py -k "origin_refused"`

**C2** - `GET /healthz/live` and `GET /healthz/ready` with an `Origin` header answer `200` (AC 1, assumption: probes exempt)
Proof: `uv run pytest tests/test_api_hardening.py -k "probes_ignore_origin"`

**C3** - No response carries a header whose name starts with `access-control-`: checked on `OPTIONS /v1/me` with and without `Origin`, `GET /v1/me` `200`, the `403` of C1, and a `429` (AC 2, door 1)
Proof: `uv run pytest tests/test_api_hardening.py -k "no_cors_headers"`

**C4** - One Clerk user making 300 requests to `GET /v1/me` inside one minute gets `200` each time; the 301st answers `429` `application/problem+json` with `Retry-After` an integer from 1 to 60; a second user at the same moment still gets `200` (AC 3, door 2)
Proof: `uv run pytest tests/test_api_hardening.py -k "user_limit"`

**C5** - Signed-in traffic from one IP is not limited per IP: 100 valid requests from two users sharing the IP `203.0.113.7` all answer `200`. Requests that fail authentication from one IP: the first 60 in a minute answer `401`, the 61st answers `429` (AC 3, door 5)
Proof: `uv run pytest tests/test_api_hardening.py -k "ip_limit_counts_only_rejected"`

**C6** - `POST /v1/unsubscribe/{token}` from one IP: 30 requests in a minute answer `404` (unknown token), the 31st answers `429` with `Retry-After`; `POST /v1/webhooks/plaid` unsigned: 30 answer `401`, the 31st `429`; the IP is the right-most `X-Forwarded-For` entry, so a request with `X-Forwarded-For: 1.1.1.1, 203.0.113.7` counts against `203.0.113.7` and changing the left entry does not give a fresh allowance; a different right-most IP is unaffected (AC 4, door 2)
Proof: `uv run pytest tests/test_api_hardening.py -k "public_routes_ip_limit"`

**C7** - After 61 seconds on the replaced clock the counter is clear, and the `Retry-After` of a `429` equals the whole seconds left in the window (AC 3, 4)
Proof: `uv run pytest tests/test_api_hardening.py -k "window_resets"`

**C8** - A `429` logs one `ratelimit.rejected` event whose fields are the route template (`/v1/unsubscribe/{token}`, never the token in the path) and `key_kind` (`user` or `ip`), and the captured log holds neither the bearer token, the user's `sub` nor the client IP (AC 5)
Proof: `uv run pytest tests/test_api_hardening.py -k "rejection_log_is_scrubbed"`

**C9** - `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff` and `Cache-Control: no-store` are on a `200` from `/v1/me`, a `401` without a token, a `404` for a stranger, the `403` of C1 and the `429` of C4 (AC 6)
Proof: `uv run pytest tests/test_api_hardening.py -k "headers_on_every_v1_answer"`

**C10** - `/healthz/*` is never counted: 500 calls from one IP in a minute all answer `200` (assumption: probes exempt)
Proof: `uv run pytest tests/test_api_hardening.py -k "probes_not_limited"`

**C11** - Importing `app.jobs.run_due` in a fresh interpreter does not import `app.ratelimit` or `app.security` (Impact: jobs)
Proof: `uv run pytest tests/test_api_hardening.py -k "jobs_do_not_load_http_middleware"`

### S2 - The web app sends its headers · `frontend/lib/security-headers.ts`, `frontend/next.config.ts`, test · ~4 files · 12 KB · ~3k

**C12** - `next.config.ts`'s `headers()` returns, for source `/:path*`, exactly `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `X-Frame-Options: DENY` and a `Content-Security-Policy-Report-Only` header (AC 7, door 3)
Proof: `npx vitest run tests/security-headers.test.ts -t "config sends the enforced headers"`

**C13** - The report-only policy contains `frame-ancestors 'none'` and `default-src 'self'`, and no header named `Content-Security-Policy` (enforcing) is in the list (AC 7, door 3)
Proof: `npx vitest run tests/security-headers.test.ts -t "csp is report only"`

**C14** - Against a production build served locally (`npm run build`, `npm start`), `curl -I` on `/sign-in` shows all six headers of C12 and `/healthz` shows them too (AC 7). Gated: the staging run of the same script needs the branch pushed and deployed, which needs the user's go-ahead
Proof: `bash .specs/features/33-launch-security-review/headers-check.sh http://localhost:3000`

**C15** - Playwright over the local build at 375 px, signed out (`/sign-in`) and signed in on the sample business (`/`, `/alerts`, `/settings/banks`, `/settings/email`, `/onboarding/*` where reachable): every screen renders its content, the console shows no error other than CSP report-only violations, and each violation is written into `context/security/rules.md` with a decision (AC 8). The run is recorded in `.specs/features/33-launch-security-review/csp-pass.md`
Proof: `python3 .specs/features/33-launch-security-review/check_csp_pass.py` (exits 0 only when `csp-pass.md` lists every screen above with `ok` and every violation row has a decision)

### S3 - Every endpoint denies another business · `tests/test_security_rules.py` · 1 file · 14 KB · ~4k

**C16** - Table-driven over every route under `/v1/businesses/{business_id}` in the OpenAPI document (28 today: 13 owner-only, 14 shared, 1 bookkeeper-only, taken from `OWNER_ONLY`, `SHARED`, `BOOKKEEPER_ONLY` of `tests/test_bookkeeper_access.py`): a signed-in member of business B calling it with business A's ID answers `404` with detail `"Business not found."`, and business A's `businesses`, `memberships`, `audit_log` and `bank_connections` row counts are unchanged (AC 10)
Proof: `uv run pytest tests/test_security_rules.py -k "stranger_denied_on_every_business_route"`

**C17** - Every `/v1` route that does not start with `/v1/businesses/{business_id}` is in exactly one of two sets, or the test fails: `USER_SCOPED` (`GET`/`POST /v1/businesses`, `GET /v1/me`, `GET`/`PUT /v1/me/email-preferences`, `GET /v1/invitations/{token}`, `POST /v1/invitations/{token}/accept`) or `PUBLIC` (C21); adding a route to neither fails (AC 9)
Proof: `uv run pytest tests/test_security_rules.py -k "every_v1_route_is_classified"`

**C18** - A caller with a role outside a route's roles gets `403` with detail `"You don't have permission to do this."` on all 13 owner-only routes and changes nothing (AC 11)
Proof: `uv run pytest tests/test_bookkeeper_access.py -k "bookkeeper_gets_403_from_owner_routes"`

**C19** - Every `/v1` route except the `PUBLIC` ones answers `401` with `WWW-Authenticate: Bearer` for a missing token, an expired token and a token signed with another key (AC 12)
Proof: `uv run pytest tests/test_security_rules.py -k "unauthenticated_gets_401_with_challenge"` and `uv run pytest tests/test_auth.py -k "every_v1_route_requires_token"`

**C20** - `app.routes` holds no route for `/docs`, `/redoc` or `/openapi.json` when `API_DOCS_ENABLED` is unset or `false`, and holds all three when it is `true`; `uv run python -m app.export_openapi` still writes `contracts/openapi.json` with it unset (AC 13, door 6)
Proof: `uv run pytest tests/test_security_rules.py -k "docs_off_unless_enabled"`

**C21** - Walking `app.routes` and the included routers, the routes with no `current_user` dependency are exactly `POST /v1/webhooks/plaid`, `POST /v1/unsubscribe/{token}`, `GET /healthz/live` and `GET /healthz/ready` (4 of 4), and no route outside `/v1` and `/healthz` exists (AC 13, door 4)
Proof: `uv run pytest tests/test_security_rules.py -k "public_list_is_exactly_four"` and `uv run pytest tests/test_plaid_webhook.py -k "only_public_v1_route"`

### S4 - Each AGENTS.md rule has a proof · `context/security/rules.md`, `tests/test_security_rules.py` · ~3 files · 20 KB · ~5k

**C22** - `context/security/rules.md` has one row per top-level bullet under "Security and data handling" in `AGENTS.md` (8 today, counted by the test from `AGENTS.md`), numbered R1-R8 in order, each row holding either a `Proof:` cell naming tests or a `Written check:` cell with numbered steps and a `Last run:` ISO date (AC 14)
Proof: `uv run pytest tests/test_security_rules.py -k "rules_table_has_a_row_per_rule"`

**C23** - Every test named in `rules.md` (form `services/core/tests/<file>.py::<function>` or `frontend/tests/<file>.test.ts`) exists, and running exactly those tests exits 0 (AC 15)
Proof: `uv run pytest tests/test_security_rules.py -k "rules_table_tests_exist"` and `uv run python ../../.specs/features/33-launch-security-review/run_rules_tests.py`

**C24** - A failing request leaks nothing: a `422` whose body carries `access-sandbox-00000000-0000-0000-0000-000000000000`, `Bearer abc.def.ghi` and the 12-digit string `123456789012` in submitted fields, a `500` raised with a message holding the same three values, and a `502` from a failing Plaid link-token call: no response body contains any of the three (AC 16, R1)
Proof: `uv run pytest tests/test_security_rules.py -k "error_bodies_leak_nothing"`

**C25** - A Plaid webhook with no `Plaid-Verification` header, a non-JWT, an HS256 token, an unsigned token, a wrong signing key, a stale `iat`, a mismatched body hash and an expired key each answers `401` and the sync fake is never called; a webhook signed with the valid key answers `200` (AC 17, R3)
Proof: `uv run pytest tests/test_plaid_webhook.py -k "bad_header_rejected or wrong_key_rejected or stale_iat or body_hash_mismatch or expired_key or sync_updates_available_syncs"`

**C26** - `git ls-files` lists no file whose name starts with `.env` except `.env.example`, and no tracked file under `services/core/app`, `frontend/app`, `frontend/components`, `frontend/lib`, `.railway` or `.github` matches a Plaid access token, a Clerk or Stripe secret key, a Resend key or a private key block (patterns fixed in the test) (AC 18, R8)
Proof: `uv run pytest tests/test_security_rules.py -k "no_env_files_or_secrets_tracked"`

### S5 - People, access and incident plan · `context/security/*.md`, `tests/test_security_rules.py` · ~5 files · 18 KB · ~5k

**C27** - `context/security/access.md` has one row for each of the 8 services (Clerk, Railway, GitHub, Resend, PostHog, Sentry, Plaid, the domain registrar), and each row holds a person, a role, a reason, `2FA: yes` and a `Checked:` ISO date no older than 90 days; no row lists a person twice with different roles. Gated: the people, roles and 2FA state are the user's to report (open question 1) (AC 19, 20)
Proof: `uv run pytest tests/test_security_rules.py -k "access_table_complete"`

**C28** - `context/security/incident-response.md` holds the sections Detect, Decide, First hour, Notify and Client notice; First hour is a numbered list naming Plaid access tokens, `TOKEN_ENCRYPTION_KEYS`, `CLERK_SECRET_KEY`, `RESEND_API_KEY` and the Railway database password; Notify names clients before the Office of the Privacy Commissioner of Canada; Client notice holds a template with `<what happened>`, `<what data>`, `<what we did>` and `<what you should do>` (AC 21)
Proof: `uv run pytest tests/test_security_rules.py -k "incident_plan_has_its_parts"`

**C29** - A rehearsal record `context/security/rehearsal-<YYYY-MM-DD>.md` exists with the date, the scenario, the participants, a time for each First hour step, and a section "What the plan got wrong" (at least one line, or the words `nothing`); `incident-response.md` carries a `Last rehearsed:` date equal to the record's. Gated: the rehearsal is the user's, with the agent facilitating and recording (open question 2) (AC 22)
Proof: `uv run pytest tests/test_security_rules.py -k "rehearsal_recorded"`

### S6 - Review fixes (the-judge F1-F3, 2026-10-16, added after approval at the user's request) · `app/auth.py`, `app/ratelimit.py`, `tests/test_api_hardening.py` · 3 files · 18 KB · ~5k

**C30** - After 60 requests failing authentication from IP `203.0.113.80` (the 61st answers `429`, C5), a request from the same IP with a valid token answers `200` (door 5, review F1)
Proof: `uv run pytest tests/test_api_hardening.py -k "verified_user_not_blocked_by_ip"`

**C31** - `POST /v1/unsubscribe/{token}` is limited per client IP and token: from one IP, 31 requests each with a different token all answer `404`; after one token's 31st request answers `429`, a different token from the same IP answers `404` (door 7, review F2)
Proof: `uv run pytest tests/test_api_hardening.py -k "unsubscribe_limit_per_token"`

**C32** - `X-Real-IP` names the client when present: 30 unsubscribe requests with `X-Real-IP: 192.0.2.60` and a different right-most `X-Forwarded-For` entry on each answer `404` and the 31st answers `429`; the same request with `X-Real-IP: 192.0.2.61` answers `404` (door 8, review F3)
Proof: `uv run pytest tests/test_api_hardening.py -k "real_ip_names_the_client"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| API refusal statuses (2) | `403` browser origin C1 · `429` over the limit C4, C5, C6 | - |
| web page statuses (2) | `200` C14 · `307` C14 (`/` while signed out) | - |
| origin-refused route kinds (4) | `/v1` read C1 · `/v1` write C1 · webhook C1 · unsubscribe C1 | - |
| rate-limit keys (5) | user C4 · IP rejected-auth C5, C30 · IP public routes C6 · IP and token unsubscribe C31 · probes exempt C10 | - |
| `/v1` answers carrying the headers (5) | `200` C9 · `401` C9 · `404` C9 · `403` C9 · `429` C9 | - |
| web security headers (6) | HSTS C12 · nosniff C12 · Referrer-Policy C12 · Permissions-Policy C12 · X-Frame-Options C12 · CSP report-only C12, C13 | - |
| business routes denied to a stranger (28) | `PATCH /` C16 · `POST /invitations` C16 · `DELETE /members/{user_id}` C16 · `POST /bank/link-token` C16 · `POST /bank/connections` C16 · `GET /bank/connections` C16 · `GET /bank/transactions` C16 · `PATCH /bank/accounts/{account_id}` C16 · `POST /bank/connections/{connection_id}/link-token` C16 · `POST /bank/connections/{connection_id}/repair` C16 · `DELETE /bank/connections/{connection_id}` C16 · `PUT /minimum-balance` C16 · `POST /alerts/{alert_id}/dismiss` C16 · `GET /` C16 · `GET /members` C16 · `GET /recurring-patterns` C16 · `GET /expected-payments` C16 · `POST /expected-payments` C16 · `PUT /expected-payments/{payment_id}` C16 · `DELETE /expected-payments/{payment_id}` C16 · `GET /forecast` C16 · `GET /upcoming` C16 · `GET /minimum-balance` C16 · `GET /forecast/status` C16 · `GET /alerts` C16 · `GET /alerts/{alert_id}` C16 · `GET /dashboard` C16 · `PUT /me/alert-emails` C16 | - |
| non-business `/v1` routes (9) | `GET /v1/businesses` C17 · `POST /v1/businesses` C17 · `GET /v1/me` C17 · `GET /v1/me/email-preferences` C17 · `PUT /v1/me/email-preferences` C17 · `GET /v1/invitations/{token}` C17 · `POST /v1/invitations/{token}/accept` C17 · `POST /v1/webhooks/plaid` C17, C21 · `POST /v1/unsubscribe/{token}` C17, C21 | - |
| public routes (4) | `POST /v1/webhooks/plaid` C21, C25 · `POST /v1/unsubscribe/{token}` C21, C6 · `GET /healthz/live` C21, C2 · `GET /healthz/ready` C21, C2 | - |
| token rejections (3) | missing C19 · expired C19 · other key C19 | - |
| Plaid webhook rejections (8) | no header C25 · non-JWT C25 · HS256 C25 · unsigned C25 · wrong key C25 · stale `iat` C25 · body hash C25 · expired key C25 | - |
| AGENTS.md security rules (8) | R1 never return or log secrets C24, `tests/test_log.py` · R2 encrypt tokens `tests/test_bank_connect.py::test_token_encrypted` · R3 webhook signature C25 · R4 Clerk token C19 · R5 permissions C16, C18 · R6 cross-business C16 · R7 synthetic data, a written check row C22 · R8 secrets only in environment C26; all joined by C22, C23 | - |
| security documents (3) | `access.md` C27 · `incident-response.md` C28 · rehearsal record C29 | - |
| one-way doors (8) | 1 origin rule C1-C3 · 2 limiter C4-C8 · 3 web headers C12-C15 · 4 route inventory C17, C21 · 5 `/v1` IP limit counts rejected only C5, C30 · 6 docs off by default C20 · 7 unsubscribe per IP and token C31 · 8 client IP from `X-Real-IP` C32 | - |
| startup config (2 assemblies) | `api` app C1, C4, C9 · `jobs` process does not load the middleware C11 | - |

- Claims naming a status code or a route: C1, C4, C5, C6, C9, C16, C19, C21 - each proof crosses the HTTP boundary through `TestClient`; C14 crosses it for the web with `curl -I`
- Level gap: C12 and C13 prove the header list in the config object. Only C14 (local build) and its staging run prove Next.js sends them; the staging run is gated on a push and deploy
- Level gap: C4-C8 prove one in-process counter. Counters reset on deploy and do not span replicas (door 2); nothing here proves behaviour with two `api` instances
- Level gap: C15 proves no screen breaks under the report-only policy; it cannot prove the policy would be correct enforced
- No other check claims more than the single case its proof exercises

## Swept

- validation: C1 (`Origin`), C6 (`X-Forwarded-For` right-most parsing), C24 (hostile input in bodies), C26 (patterns)
- failure modes: C24 (`422`, `500`, `502`), C25 (webhook failures), C7 (window reset after a limit)
- idempotency: n/a - the limiter and headers keep no state a retry could duplicate; a retried request after `Retry-After` is an ordinary new request (C7)
- authorization: C16, C18, C19, C21 (strangers, roles, tokens, the public list)
- concurrency: n/a - the limiter counts in one process under the ASGI event loop with no await between read and write; two `api` replicas are the out-of-scope case recorded in door 2 and the level gap above
- data lifecycle: n/a - no table is added; counters live in memory and are dropped at deploy (door 2); the documents are kept in git
- dependency failure: C24 (a failing Plaid call returns `502` with nothing leaked), C25 (the webhook key fetch failing is `test_key_fetch_fails`, existing)
- state transitions: n/a - no entity with states is added; the limiter's window reset is C7
- observability: C8 (`ratelimit.rejected` fields), C15 (CSP violations recorded)

## Out of scope

See `plan.md`.

## Handoff

- S1 ~12k in `services/core` (8 files), S2 ~3k in `frontend` (4 files), S3 ~4k, S4 ~5k, S5 ~5k in `services/core/tests` and `context/security`; total ~29k, under the 150k budget. `wc -c`: `app/main.py` 4.2 KB, `app/problems.py` 3.4 KB, `app/settings.py` 5.9 KB, `next.config.ts` 0.9 KB, `tests/test_bookkeeper_access.py` 8 KB
- Mechanism: one builder
