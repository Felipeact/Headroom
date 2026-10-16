# Spec 33: Security review

## Problem

Spec 33 is the next roadmap item: specs 17, 20, 27, 29, 30, 31 and 32 are Done, and 33 is `Not started`. Milestone 6 is complete; `context/Roadmap.md` has no "done" date on it yet.

Today the product holds real bank data in staging with these gaps:

- The API has no rate limit, no security headers, and no rule about browser requests. A scan of `services/core/app` and `frontend/next.config.ts` finds none of them. The web app sets no headers either.
- Several `AGENTS.md` "Security and data handling" rules have tests: token encryption (`test_bank_connect.py::test_token_encrypted`), log redaction (`test_log.py`), Plaid signature failures, Clerk token failures (`test_auth.py`). There is no list that ties each rule to its proof, and nothing proves "a user from another business is denied" for every endpoint. Cross-business tests exist in 14 files, added one spec at a time.
- Nothing is written about two-factor authentication on admin accounts, who can reach production, or what to do if customer data is exposed.

The spec gives no figures. When this ships, a hostile browser page or script gets nothing from the API, a flood from one address gets `429`, every route is proven to deny a stranger, each rule in `AGENTS.md` points at a passing test or a written check, and the team has rehearsed an exposure once.

## Flow

This reuses `app/problems.py` (RFC 9457 errors, AD-008), `require_member` and the one authenticated `/v1` router (AD-022, AD-031), the webhook and unsubscribe exceptions (AD-049, AD-109), `app.log.redact` (AD-009), the structlog logger, and the `tests/auth-protect.test.ts` pattern of failing when a rule is skipped.

1. Any request -> `app.main` ASGI middleware stack (new, door 1; placement per conventions) -> in order: security headers, browser-origin rejection, rate limit, then routing.
2. Rate limit: `app/ratelimit.py` (new, door 2) keys public routes (`/v1/webhooks/*`, `/v1/unsubscribe/*`) by client IP and `/v1` by the verified Clerk user, and answers `429` problem details with `Retry-After`.
3. Web: `frontend/next.config.ts` `headers()` (exists) adds the enforced headers and a report-only CSP to every page.
4. Proofs: a route-inventory test walks `app.routes`, and for every `/v1` route calls it as a member of business B against business A's ID and expects `404` or `403` (new `tests/test_security_rules.py`).
5. Documents: `context/security/rules.md` (every `AGENTS.md` rule -> proof) and `context/security/incident-response.md`; the rehearsal is recorded in the same folder.

## Impact

| Front | What changes |
| --- | --- |
| domain | new term: browser request - any request carrying an `Origin` header; the API serves none (AD-017), so all are refused |
| domain | existing: `/v1/webhooks/*` and `/v1/unsubscribe/*` are public by design (AD-049, AD-109); they are rate-limited by IP and never exempt |
| API | every response gains security headers; every route can answer `429`; `contracts/openapi.json` is regenerated only if the `429` response is declared on the router |
| web | every page response gains headers; no screen, no copy, so `messages/en.json` is unchanged |
| jobs | `app.main` middleware does not run in the jobs process; the limiter is never imported there |
| infra | Clerk and Railway settings (2FA, member roles) change outside the repo; `.railway/railway.ts` gains no new variable unless a limit is configurable (assumption 3) |
| stored data | nothing to migrate; no table is added |

## Relations

None - no stored-data shape change

## Surface

Only routes this adds or whose signature changes. No route is added; the signature that changes is the error and header contract of all of them.

| Route | In | Out | Status |
| --- | --- | --- | --- |
| every route (API) | any request | `Strict-Transport-Security`, `X-Content-Type-Options`, `Cache-Control: no-store` on `/v1`; problem details on refusal | `403` browser origin, `429` over the limit |
| every page (web) | any request | the headers in AC 7-8 and `Content-Security-Policy-Report-Only` | `200`, `307` as today |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. Browser origin rule | a request with an `Origin` header is `403` problem details `"Browser requests are not allowed."` on every route except `/healthz/*`; no `CORSMiddleware`, no allowlist, no `Access-Control-*` header ever sent | CORS with an allowed-origin list: the browser never calls the API (AGENTS.md, AD-017), so a list invites the first exception. Cost: a future browser client must change this rule and its test |
| 2. Rate limiter | `app/ratelimit.py`, in-process fixed windows (user decision 2026-10-15): public routes 30/min per client IP, `/v1` 300/min per Clerk user `sub`, `/v1` 60/min per IP before authentication; client IP from the right-most `X-Forwarded-For` entry Railway appends; refusal `429` with `Retry-After` in whole seconds | Postgres counters: a write on every request; Redis: a new service before a client exists. Cost: counters reset on deploy and do not span replicas, so scaling `api` beyond one instance needs this door reopened |
| 3. Web header set | enforced: `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `frame-ancestors 'none'` and `X-Frame-Options: DENY`; the CSP ships as `Content-Security-Policy-Report-Only` (user decision 2026-10-15) | Enforced CSP now: needs the exact Clerk, Sentry and Next.js allowlist and a pass over every screen; a miss blanks sign-in. Cost: until it is flipped, script injection is reported and not blocked |
| 4. Route inventory proof | `tests/test_security_rules.py` builds the list from `app.routes`; a route is `authenticated` or on the fixed `PUBLIC` list (the three webhook and unsubscribe routes plus `/healthz/*`); a new route in neither state fails the suite | A hand-written endpoint list: it rots the first time a route is added and the test still passes |
| 5. `/v1` IP limit counts rejections only (found while writing the checks; narrows door 2's `60/min per IP before authentication`) | `/v1` requests that answer `401` count 60/min per client IP, then `429`; signed-in requests are limited only per user | 60/min per IP on all `/v1` traffic: the web server is the one caller of `/v1` (AD-017), so every user shares its IP and the product would throttle itself at 60 requests a minute |
| 6. API docs off by default (found while writing the checks) | `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` unless setting `API_DOCS_ENABLED=true` (`.env.example` sets it for local work); `app.openapi()` and `python -m app.export_openapi` still work | Public `/docs` and `/openapi.json` on production: they hand a scanner the whole route list. Listing them in `PUBLIC`: AC 13 says exactly four |
| 7. Unsubscribe limit keyed by IP and token (found in review, 2026-10-16; narrows door 2's `public routes 30/min per client IP` for `/v1/unsubscribe/{token}`) | `POST /v1/unsubscribe/{token}` counts 30/min per (client IP, token); `/v1/webhooks/plaid` stays 30/min per client IP | Per IP only: the footer page posts through the web server, so every user shares its IP and one visitor submitting 30 times a minute blocks all unsubscribes. Cost accepted: one IP may try any number of distinct tokens, each one indexed lookup; tokens are `secrets.token_urlsafe(32)`, so guessing is infeasible |
| 8. Client IP from `X-Real-IP` first (found in review, 2026-10-16; narrows door 2's right-most `X-Forwarded-For`) | the client IP is `X-Real-IP` when present, else the right-most `X-Forwarded-For` entry, else the socket peer | Right-most `X-Forwarded-For` only: Railway documents `X-Real-IP` as the client address header (docs.railway.com/networking/public-networking/specs-and-limits) and does not document how it treats `X-Forwarded-For` |

- Review finding F1 (2026-10-16) needed no new door: the code checked the rejected-authentication IP block before verifying the token, so a verified user behind a blocked IP got `429`, contrary to door 5's "signed-in requests are limited only per user"; the fix brings the code to door 5
- Nothing else in this change is hard to reverse

## Criteria

### S1: The API refuses what a browser or a flood sends (P1)

**Acceptance Criteria**

1. WHEN a request to any route outside `/healthz/*` carries an `Origin` header THEN the API SHALL answer `403` problem details with detail `"Browser requests are not allowed."` and run no handler.
2. The API SHALL send no `Access-Control-*` header on any response, including `OPTIONS`.
3. WHEN a client exceeds 300 requests in a minute as one verified Clerk user THEN the API SHALL answer `429` problem details with a `Retry-After` of 1-60 whole seconds, and other users SHALL be unaffected.
4. WHEN one client IP exceeds 30 requests in a minute to `/v1/webhooks/*` or `/v1/unsubscribe/*` THEN the API SHALL answer `429` problem details with `Retry-After`.
5. IF a request is rate limited THEN the API SHALL log `ratelimit.rejected` with the route template and key kind only, never the token, user ID or IP.
6. The API SHALL send `Strict-Transport-Security`, `X-Content-Type-Options: nosniff` and `Cache-Control: no-store` on every `/v1` response, `429` and `403` included.

**Independent test:** with `TestClient`, send `Origin: https://evil.example` to `/v1/me`, then 301 requests as one user, then 31 unsubscribe posts.

### S2: The web app sends its headers (P1)

**Acceptance Criteria**

7. The web app SHALL send `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `X-Frame-Options: DENY` and `Content-Security-Policy-Report-Only` with `frame-ancestors 'none'` on every page response.
8. WHEN every screen is opened on staging with the report-only policy THEN no screen SHALL lose function, and the violations seen SHALL be listed in `context/security/rules.md` with the decision for each.

**Independent test:** `curl -I` against staging `/sign-in`; Playwright pass at 375 px over the screens, console checked.

### S3: Every endpoint denies another business (P1)

**Acceptance Criteria**

9. The system SHALL fail a test when any route under `/v1` is neither covered by the cross-business sweep nor on the fixed `PUBLIC` list.
10. WHEN a member of business B calls any business-scoped `/v1` route with business A's ID THEN the API SHALL answer `404` (`"Business not found."`) and change nothing in business A.
11. WHEN a member calls a route whose role they lack THEN the API SHALL answer `403`.
12. WHEN a request carries a missing, expired or forged Clerk token THEN every `/v1` route SHALL answer `401` with `WWW-Authenticate: Bearer`.
13. The `PUBLIC` list SHALL hold exactly `POST /v1/webhooks/plaid`, `POST /v1/unsubscribe/{token}` and the two `/healthz` probes.

**Independent test:** run `pytest tests/test_security_rules.py`; add a route with no dependency and watch it fail.

### S4: Each AGENTS.md rule has a proof (P1)

**Acceptance Criteria**

14. The system SHALL hold a `context/security/rules.md` table with one row per bullet of "Security and data handling" in `AGENTS.md`, each naming a passing test by path and name or a written check with its steps and its last-run date.
15. WHEN a row names a test THEN that test SHALL exist and pass; a test in `tests/test_security_rules.py` SHALL fail if a named test path or function is missing.
16. The system SHALL have a test proving no response body from a failing route (`422`, `500`, `502`) contains a Plaid token pattern, a `Bearer` value or an account number.
17. The system SHALL have a test proving a Plaid webhook with a missing, expired or tampered `Plaid-Verification` header does no work, and that a valid one is accepted.
18. The system SHALL keep the `.env*` rule checkable: a test fails when `git ls-files` lists any `.env*` file except `.env.example`.

**Independent test:** run the table's tests by name; delete one referenced test and watch AC 15 fail.

### S5: People, access and incident plan (P1)

**Acceptance Criteria**

19. WHERE an account can reach production (Clerk dashboard, Railway, GitHub, Resend, PostHog, Sentry, Plaid dashboard, the domain registrar) the team SHALL have two-factor authentication on, recorded per account in `context/security/access.md` with the date checked and the role held.
20. The system SHALL record who holds production access for each service in `context/security/access.md`, with a reason per person; nobody else holds it.
21. The system SHALL hold `context/security/incident-response.md` with: how exposure is detected, who decides, the first-hour steps (revoke Plaid tokens, rotate `TOKEN_ENCRYPTION_KEYS`, `CLERK_SECRET_KEY`, `RESEND_API_KEY` and the Railway database password), the order of notices (clients, then the Office of the Privacy Commissioner of Canada, as the lawyer confirms), and a template for the client notice.
22. WHEN the exposure plan is rehearsed THEN the team SHALL record the date, the scenario, who took part, the time each step took, and what the plan got wrong, and the plan SHALL be corrected in the same commit.

**Independent test:** the rehearsal itself (AC 22): a tabletop of "a Plaid access token appeared in a log line", run once on staging.

## Out of scope

| Excluded | Why |
| --- | --- |
| A WAF, bot detection or a CDN in front of the API | Railway offers none; the limiter covers v1 |
| A shared limiter store (Redis or Postgres) | Door 2; revisit when `api` runs more than one instance |
| An enforced CSP | Door 3; a follow-up once staging reports are clean |
| An external penetration test | Not in the spec; the pilot has 5-10 clients |
| Key rotation tooling and automated secret scanning in CI | Not in the spec; the plan names the manual steps |
| A SOC 2 or PIPEDA assessment | The lawyer's work (spec 35 and the Roadmap) |
| A bug-bounty or disclosure page | Spec 35 covers legal pages and support |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Limits | 30/min/IP public, 60/min/IP and 300/min/user on `/v1` | a business owner's dashboard makes a handful of calls per page; the numbers leave 10x headroom and are one constant each | n |
| Client IP | the right-most `X-Forwarded-For` entry | Railway's proxy appends it; the left entries are client-controlled | n |
| Health probes | exempt from the origin rule and the limiter | Railway calls them every few seconds with no `Origin` | n |
| `Origin` on Plaid webhooks | refused like any other | Plaid's server sends none | n |
| Where the documents live | `context/security/` (`rules.md`, `access.md`, `incident-response.md`, `rehearsal-<date>.md`) | `context/` holds the project's documents; the spec says "written check" without a place | n |
| Who rehearses and attests 2FA | the user, with the agent drafting the documents and recording what the user reports | the agent cannot reach Clerk, Railway or GitHub settings; AD-117 and AD-127 set the precedent for user-confirmed evidence | n |
| Limit configuration | constants in `app/ratelimit.py`, not settings | nobody tunes them before the pilot; a setting is a new variable on three Railway services | n |

**Open questions:**

| # | Kind | Question | Until answered |
| --- | --- | --- | --- |
| 1 | blocks go-live | The list of people with production access per service, and whether each has 2FA on | AC 19-20 cannot be marked Done; the code proofs run without it |
| 2 | blocks go-live | A date and participants for the rehearsal | spec 33's second "Done when" item and spec 34 |
| 3 | open | Whether the lawyer wants a named privacy officer and a notice deadline in the plan | the plan names "the lawyer confirms" meanwhile |

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| all `/v1` routes | error shape and codes | AC 1, 3, 10-12; problem details (AD-008) |
| all `/v1` routes | who may call | AC 10-13 |
| all `/v1` routes | rate limit behaviour | AC 3-5 |
| all `/v1` routes | versioning | n/a - no route is added or renamed |
| `POST /v1/webhooks/plaid`, `POST /v1/unsubscribe/{token}` | rate limit and who may call | AC 4, 13, 17 |
| web pages | empty, loading, error states | n/a - no screen is added |
| web pages | headers | AC 7-8 |
| document `rules.md`, `access.md` | structure and next action | AC 14, 19, 20 |
| document `incident-response.md` | structure, reader's next action | AC 21: numbered first-hour steps a person can follow at 02:00 |
| command `pytest tests/test_security_rules.py` | output and exit codes | AC 9, 15, 18; non-zero on any miss |

## Sources

- `context/specs/33-launch-security-review.md` - the five Build items and two Done-when items
- `AGENTS.md` "Security and data handling" and "Frontend rules" - the rules the table covers
- `.specs/STATE.md` AD-008, AD-009, AD-017, AD-021, AD-022, AD-031, AD-036, AD-038, AD-049, AD-109, AD-117, AD-127 - the constraints this conforms to

