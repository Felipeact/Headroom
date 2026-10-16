# Spec 33: Security review verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 0e577b5^..82f90a2 (round 3 scope: fix range 861e43a..82f90a2, one commit)
**Round**: 3 - scoped
**Verifier**: independent fresh sub-agent (author != verifier). I did not build the feature or write rounds 1-2. I ran read-only over the real tree at HEAD 82f90a2 and wrote only this file.

All 32 checks pass with located evidence. The three new checks, C30-C32, assert what their claims say. Each one failed under a fault injected in a scratch worktree. C5, C6 and C8 still hold with the new keying. The door 7 and door 8 rows and S6 were added without rewriting any approved row or check. These items from round 2 still stand: C27 rests on the user's statement, C14 and C15 owe a staging run, and the precision gaps on C21 and C22 remain. The C20 precision gap from round 2 is now resolved. None of these changes a verdict.

## Scope of this round - verified at 82f90a2

- `git diff 861e43a..HEAD --stat` touches 6 files:
  - `checks.md` (+17/-2)
  - `plan.md` (+3)
  - `services/core/app/auth.py` (+6/-3)
  - `services/core/app/ratelimit.py` (+14/-3)
  - `services/core/tests/test_api_hardening.py` (+34)
  - `services/core/tests/test_security_rules.py` (+10/-4)
- Nothing under `frontend/` changed, so C14's live header run is carried from a40d9b8 (through 861e43a).
- Checks re-judged against the diff:
  - C1-C11: they share `auth.py` and `ratelimit.py`, and the `X-Real-IP` change affects every IP key.
  - C19 and C21: `_rejected` changed, and these checks need `401` with the challenge.
  - C20: its test was rewritten.
  - C30-C32: new.
  - Every other check is carried. Its proof still re-ran at HEAD, and its citations were refreshed.
- Proofs re-ran in full at 82f90a2, batched by target:
  - one pytest invocation for all 32 pytest proof names
  - one vitest invocation
  - `run_rules_tests.py`
  - `check_csp_pass.py`
- Citation refresh: the C20 test grew by 6 lines. Every citation into `test_security_rules.py` after `:199` moved down by 6, and I re-read each one at 82f90a2. The new tests in `test_api_hardening.py` are appended at `:255-286`, so earlier lines did not move.
- Nothing was non-PASS in round 2.

## Additivity of the spec changes - verified at 82f90a2

`git diff 861e43a..HEAD -- .specs/features/33-launch-security-review/` shows these changes:

- **`plan.md`:** additions only. It adds Landing rows 7 and 8, plus a note that review finding F1 needed no new door. No existing row changed.
- **`checks.md`:**
  - Line 6, the header count, goes from 29 to 32 checks and from 6 to 8 doors.
  - Section S6 (C30-C32) is new.
  - Two Coverage rows grew without losing a member:
    - "rate-limit keys" goes from 4 to 5. It adds C30 to the rejected-auth member and adds the member "IP and token unsubscribe C31".
    - "one-way doors" goes from 6 to 8. It adds C30 to door 5 and adds doors 7 and 8.
  - The text of C1-C29 is unchanged.

## Steps skipped by profile

- Step 1 (check the checks against their binding sources) does not run under `light`.
- Step 4 (fault injection) is not required under `light`. The caller asked for it as an option, and I ran one fault each on C30, C31 and C32. The results are below.
- The coverage recompute does not run under `light`. I read the `Coverage` table in `checks.md` but did not recompute it. The two rows that changed match the new checks.

## Checks - proofs verified at 82f90a2

**Proof run A.** One invocation from `services/core` with `DATABASE_URL=postgresql+psycopg://postgres:@127.0.0.1:61509/headroom`:

`uv run pytest tests/test_api_hardening.py tests/test_security_rules.py tests/test_plaid_webhook.py tests/test_bookkeeper_access.py tests/test_auth.py -v -p no:cacheprovider -k "<every name from every pytest Proof line in checks.md, C1-C32>"`

Result: **35 passed, 44 deselected, exit 0.** Each named test appears in the output individually as PASSED. That includes `test_verified_user_not_blocked_by_ip`, `test_unsubscribe_limit_per_token`, `test_real_ip_names_the_client` and `test_docs_off_unless_enabled`.

**Proof run B.** From `frontend`: `npx vitest run tests/security-headers.test.ts --reporter=verbose`. Result: 2 passed. Both `config sends the enforced headers` and `csp is report only` show a check mark.

**Proof run C.** From `services/core`: `uv run python ../../.specs/features/33-launch-security-review/run_rules_tests.py`. Result: "41 passed" and "ran 21 API tests and 0 web tests: exit 0".

**Proof run D.** `python .specs/features/33-launch-security-review/check_csp_pass.py` printed "ok: every screen recorded, every violation decided" and exited 0.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | A request with `Origin` gets 403 problem+json "Browser requests are not allowed." and no business is created. Without `Origin`, not 403. | A: `test_origin_refused` PASSED | `services/core/tests/test_api_hardening.py:72-75` `status_code == 403`, `PROBLEM_JSON`, detail, `business_count() == before`; `:79-80` `!= 403`. Not affected by the fix: the origin check is in `app/security.py`, which the diff does not touch. | PASS |
| C2 | Probes with `Origin` answer 200 | A: `test_probes_ignore_origin` PASSED | `services/core/tests/test_api_hardening.py:86-87` `== 200` | PASS |
| C3 | No `access-control-*` header on any answer, including the 429 | A: `test_no_cors_headers` PASSED | `services/core/tests/test_api_hardening.py:102` `last.status_code == 429`; `:106` `not [n for n in names if n.startswith("access-control-")]` | PASS |
| C4 | 300 requests answer 200. The 301st answers 429 with Retry-After from 1 to 60. A second user still gets 200. | A: `test_user_limit` PASSED | `services/core/tests/test_api_hardening.py:113` `== 200`; `:116-118` `429`, `PROBLEM_JSON`, `1 <= int(retry-after) <= 60`; `:119` `== 200`. `hit_user` is unchanged: `app/ratelimit.py:99-104` | PASS |
| C5 | Two users on one IP send 100 requests and all answer 200. Requests that fail authentication: 60 answer 401, the 61st answers 429. | A: `test_ip_limit_counts_only_rejected` PASSED | `services/core/tests/test_api_hardening.py:128` `== 200`; `:132` `== 401`; `:134` `== 429`. The block now runs only on the failing path: `app/auth.py:48-50` inside `_rejected`, and the pre-verification call was removed from `verified_clerk_user_id` (`:58-90`). Still holds with the new keying, because the test sends no `X-Real-IP`. | PASS |
| C6 | Public routes: 30 requests, then 429. The right-most `X-Forwarded-For` entry is the key, and a different right-most IP is unaffected. | A: `test_public_routes_ip_limit` PASSED | `services/core/tests/test_api_hardening.py:142-145` 30 × `404`, then `429` with retry-after; `:149-150` webhook 30 × `401`, then `429`; `:154` spoofed left entry `== 429`; `:156` other IP `== 404`. Still holds with the new keying: every unsubscribe call uses the same token `UNSUBSCRIBE` (`:24`), so the key `"{ip} {path}"` (`app/ratelimit.py:131-135`) works per IP for this test. With no `X-Real-IP`, `client_ip` falls through to the right-most `X-Forwarded-For` (`:73-75`). | PASS (see finding 2 on the wording) |
| C7 | The window clears after 61 s, and Retry-After equals the seconds left | A: `test_window_resets` PASSED | `services/core/tests/test_api_hardening.py:166-167` `== 429`, `== 19`; `:170` `== 404` | PASS |
| C8 | The rejection log holds only the route template and key_kind, with no token, sub or IP | A: `test_rejection_log_is_scrubbed` PASSED | `services/core/tests/test_api_hardening.py:192-195` `{(route, key_kind)} == {("/v1/me","user"), ("/v1/unsubscribe/{token}","ip")}`; `:196-199` exact field set; `:206-207` `secret not in api_log` for the token, sub, both IPs and `secret-token-value`. Still holds with the new keying: the new compound key `"{ip} {path}"`, which contains the token, is only an in-memory dict key (`app/ratelimit.py:136`, `:144`). The log still gets `_public_template(...)` (`:138`), and `rejected()` logs only `route` and `key_kind` (`:80`). | PASS |
| C9 | HSTS, nosniff and no-store on the 200, 401, 404, 403 and 429 | A: `test_headers_on_every_v1_answer` PASSED | `services/core/tests/test_api_hardening.py:225-228` | PASS |
| C10 | 500 probe calls answer 200 | A: `test_probes_not_limited` PASSED | `services/core/tests/test_api_hardening.py:234-235`. `PUBLIC_PREFIXES` is unchanged (`app/ratelimit.py:23`, `:120`). | PASS |
| C11 | Jobs do not import the HTTP middleware | A: `test_jobs_do_not_load_http_middleware` PASSED | `services/core/tests/test_api_hardening.py:252` `returncode == 0` | PASS |
| C12 | The six enforced web headers | B: `config sends the enforced headers` passed | `frontend/tests/security-headers.test.ts:18-23` (frontend untouched; carried from 861e43a, re-run at 82f90a2) | PASS |
| C13 | The CSP is report-only, with `frame-ancestors 'none'` and `default-src 'self'` | B: `csp is report only` passed | `frontend/tests/security-headers.test.ts:29-31` (carried from 861e43a, re-run at 82f90a2) | PASS |
| C14 | A local production build sends all six headers. **The staging run is gated.** | Carried from a40d9b8 through 861e43a (`headers-check.sh http://localhost:3300` exit 0). `git diff 861e43a..HEAD --stat` touches nothing under `frontend/`. | `.specs/features/33-launch-security-review/headers-check.sh:6-13`, `:24` | PASS (local only, carried from 861e43a; staging gated) |
| C15 | Playwright pass at 375 px; each CSP violation has a decision | D: exit 0 at 82f90a2 | `.specs/features/33-launch-security-review/csp-pass.md:12-21`; `context/security/rules.md:20-34`; `check_csp_pass.py:24-27,38-41` (carried from 861e43a) | PASS (recorded manual run; staging owed) |
| C16 | 28 business routes: a stranger gets 404 and A's rows are unchanged | A: `test_stranger_denied_on_every_business_route` PASSED | `services/core/tests/test_security_rules.py:109-110` `routes == expected`, `len(routes) == 28`; `:120-121` `== 404`, `"Business not found."`; `:122` `business_rows(business_a) == before` | PASS |
| C17 | Every non-business /v1 route is USER_SCOPED or PUBLIC | A: `test_every_v1_route_is_classified` PASSED | `services/core/tests/test_security_rules.py:132` `other == USER_SCOPED` union the PUBLIC /v1 routes | PASS |
| C18 | A wrong role gets 403 on the 13 owner-only routes | A: `test_bookkeeper_gets_403_from_owner_routes` PASSED | `services/core/tests/test_bookkeeper_access.py:183-184` (untouched) | PASS |
| C19 | Every non-public /v1 route answers 401 with `WWW-Authenticate: Bearer` | A: `test_unauthenticated_gets_401_with_challenge` and `test_every_v1_route_requires_token` PASSED | `services/core/tests/test_security_rules.py:147` `len(routes) == 35`; `:157-158` `== 401`, `== "Bearer"`; `services/core/tests/test_auth.py:213`. `_rejected` still returns the 401 with the challenge (`app/auth.py:51-55`). | PASS |
| C20 | The docs routes are absent when unset or `false`, and present when `true`. The export writes `contracts/openapi.json` with the flag unset. | A: `test_docs_off_unless_enabled` PASSED | `services/core/tests/test_security_rules.py:182-184` `isdisjoint` / `isdisjoint` / `<=`; `:186` env without `API_DOCS_ENABLED`, `cwd=tmp_path` (`:191`, no `.env.local`); `:197` `exported.returncode == 0`; `:198` `contract.stat().st_mtime_ns > before`; `:199` `"/v1/me" in json.loads(...)["paths"]`. The export resolves the path from its own file (`app/export_openapi.py:13`), so it writes the real contract. `git status --porcelain` was identical before and after run A, so the content is unchanged. | PASS (round-2 precision gap resolved) |
| C21 | Exactly the 4 public routes skip the token check, and nothing exists outside /v1 and /healthz | A: `test_public_list_is_exactly_four` and `test_only_public_v1_route` PASSED | `services/core/tests/test_security_rules.py:211` `public == {...}`; `:217` `outside == {"/healthz/live","/healthz/ready"}`; `:218` `len(PUBLIC) == 4`; `services/core/tests/test_plaid_webhook.py:244-246` | PASS (latent gap stands, finding 5) |
| C22 | rules.md has R1-R8, one row per security bullet, each with a Proof or a Written check | A: `test_rules_table_has_a_row_per_rule` PASSED | `services/core/tests/test_security_rules.py:239` `len(bullets) == 8`; `:240` `== [R1..R8]`; `:242-246` proof-or-written | PASS (precision gap stands, finding 6) |
| C23 | Every test named in rules.md exists and passes | A: `test_rules_table_tests_exist` PASSED; C: 41 passed, exit 0 | `services/core/tests/test_security_rules.py:261` `source.is_file()`; `:263` `f"def {function}(" in source` | PASS |
| C24 | The 422, 500 and 502 bodies leak nothing | A: `test_error_bodies_leak_nothing` PASSED | `services/core/tests/test_security_rules.py:317` `status_code == code`; `:319` `secret not in response.text` | PASS |
| C25 | 8 bad webhook headers get 401 and no sync; a valid one gets 200 | A: 6 webhook tests PASSED | `services/core/tests/test_plaid_webhook.py:71`, `:74`, `:174` (untouched) | PASS |
| C26 | Only `.env.example` is tracked, and no secret patterns are found | A: `test_no_env_files_or_secrets_tracked` PASSED | `services/core/tests/test_security_rules.py:349` all `.env.example`; `:360` `hits == []` | PASS |
| C27 | access.md lists the 8 services. Each row has a person, role, reason, `2FA: yes` and a date within 90 days. No person holds two roles. **Rests on a user statement.** | A: `test_access_table_complete` PASSED | `services/core/tests/test_security_rules.py:416` `any(row[0] == service ...)` over `ACCESS_SERVICES` (`:394-403`); `:419` `person and role and reason`; `:420` `two_factor == "yes"`; `:422` `age <= timedelta(days=90)`; `:425` `len(held) == 1` (carried from 861e43a, re-run at 82f90a2) | PASS |
| C28 | incident-response.md has its five parts, the numbered First hour steps name the secrets, and clients are notified before the OPC | A: `test_incident_plan_has_its_parts` PASSED | `services/core/tests/test_security_rules.py:370` section headings; `:373` `assert steps`; `:381` `name in first`; `:383` `notify.index("clients") < notify.index("Office of the Privacy Commissioner")` | PASS |
| C29 | A rehearsal record exists with every required part, and `Last rehearsed:` matches it. **Rests on the recorded tabletop.** | A: `test_rehearsal_recorded` PASSED | `services/core/tests/test_security_rules.py:435` `date.fromisoformat(stamp)`; `:436-437` Date/Scenario/Participants; `:442` `len(timings) == len(steps)`; `:443-445` the "What the plan got wrong" section is non-empty; `:446` `f"Last rehearsed: {stamp}" in plan` | PASS |
| C30 | After 60 failing requests from `203.0.113.80`, the 61st gets 429, and a valid token from the same IP gets 200 | A: `test_verified_user_not_blocked_by_ip` PASSED | `services/core/tests/test_api_hardening.py:257-258` IP `203.0.113.80`, `Bearer not-a-token`; `:260` 60 × `== 401`; `:261` `== 429`; `:262` `client.get("/v1/me", headers=new_headers(ip)).status_code == 200` with the same `X-Forwarded-For`. Code: `app/auth.py:48-50`. Fault killed at `:262`. | PASS |
| C31 | Unsubscribe is keyed by IP and token: 31 different tokens all get 404; one token's 31st request gets 429; another token from the same IP then gets 404 | A: `test_unsubscribe_limit_per_token` PASSED | `services/core/tests/test_api_hardening.py:268-270` 31 distinct tokens, each `== 404`; `:272-273` 30 × `== 404`; `:274` `== 429`; `:275` `another-token` `== 404`, all from IP `192.0.2.50` (`:267`). Code: `app/ratelimit.py:131-136`, `:144`. Fault killed at `:270`. | PASS |
| C32 | `X-Real-IP` names the client: 30 requests with `X-Real-IP: 192.0.2.60` and a different right-most XFF each get 404, the 31st gets 429; `X-Real-IP: 192.0.2.61` gets 404 | A: `test_real_ip_names_the_client` PASSED | `services/core/tests/test_api_hardening.py:280-282` 30 × `{"X-Real-IP": "192.0.2.60", "X-Forwarded-For": f"198.51.100.{i}"}` `== 404`; `:283-284` same real IP with a fresh XFF `== 429`; `:285-286` `192.0.2.61` `== 404`. Code: `app/ratelimit.py:70-75`. Fault killed at `:284`. | PASS |

## Faults injected - verified at 82f90a2

I ran these in a scratch worktree: `git worktree add --detach <scratchpad>/wt HEAD`. I never touched the real tree and never used `git stash`. The tests ran from the worktree's `services/core` with the real tree's venv python and a copied `.env.local`. `python -c "import app.ratelimit; print(app.ratelimit.__file__)"` confirmed the worktree's module was the one loaded. After each fault I ran `git checkout -- app` inside the worktree. Afterwards I removed the worktree with `git worktree remove --force` and `git worktree prune`. `git worktree list` now shows only the main tree.

| Mutation | Location | Killed |
| --- | --- | --- |
| restored the pre-fix IP block before verification: `ratelimit.check_ip_not_blocked(_ip(request), _route(request))` ahead of `if credentials is None:` | `app/auth.py:67` (worktree) | yes - `test_api_hardening.py:262` `assert 429 == 200` (C5 still passed) |
| keyed unsubscribe by IP only: `f"{ip} {scope['path']}"` changed to `ip` | `app/ratelimit.py:132` (worktree) | yes - `test_api_hardening.py:270` `assert 429 == 404` (C6 still passed) |
| ignored `X-Real-IP`: `if real:` changed to `if False:` | `app/ratelimit.py:71` (worktree) | yes - `test_api_hardening.py:284` `assert 404 == 429` (C6 still passed) |

Each fault leaves the older checks green and fails only the new check, so C30-C32 test behaviour that C1-C29 did not cover.

## Swept existing - carried from 861e43a

- The dependency-failure row `test_key_fetch_fails` is still at `services/core/tests/test_plaid_webhook.py:142`, asserting `== 502` at `:150`. The file is untouched by the fix.
- The `validation` sweep row cites C6 for parsing the right-most `X-Forwarded-For` entry. Door 8 now puts `X-Real-IP` ahead of it, and that precedence is proven by C32 (`test_api_hardening.py:283-284`).
- The `n/a` rows are approved policy.

## Findings

1. **C30-C32 assert their claims (verified).** Each claim's numbers, IPs and statuses appear literally at the cited lines, and each test failed under its own fault.
2. **C6 wording vs door 7 (observation, not failing).** C6 says "`POST /v1/unsubscribe/{token}` from one IP: 30 requests ... the 31st answers 429". Since door 7, that is true only when all the requests use the same token. The test does use one token (`UNSUBSCRIBE`, `test_api_hardening.py:24`), so the assertion still holds. Door 7 narrows door 2 in `plan.md`, and C31 states the per-token rule. Leaving C6's text unchanged follows the additive rule, but a reader of C6 alone could misread the limit as per IP.
3. **Door 8 trust in `X-Real-IP` (observation, accepted in the door).** `client_ip` trusts any non-empty `X-Real-IP` (`app/ratelimit.py:70-71`). That is safe only if Railway's edge overwrites a client-supplied `X-Real-IP`. Railway documents the header as the client address. Whether it overwrites a client-supplied value is not proven here, and no check can prove it in-process. The door names this source. This is a deployment assumption, not a check failure.
4. **Round-2 C20 precision gap: resolved.** The export now runs with `API_DOCS_ENABLED` removed from the environment and from a cwd with no `.env.local` (`test_security_rules.py:186-192`). The test asserts that the contract was rewritten and contains `/v1/me` (`:198-199`). The tracked `contracts/openapi.json` came out byte-identical: `git status --porcelain` was unchanged after run A.
5. **C21 latent inventory gap (still stands, carried from 861e43a).** The /v1 inventory comes from `app.openapi()["paths"]`, so a future route with `include_in_schema=False` would escape C17, C19 and C21. No such route exists today.
6. **C22 precision gap (still stands, carried from 861e43a).** A `Written check:` cell passes with only a `Last run:` date (`test_security_rules.py:242-246`). The test never asserts the numbered steps.
7. **C15 is a recorded manual run, and the staging pass is still owed.** `check_csp_pass.py` checks the record, not the screens.
8. **C14's staging run is gated.** Only the local build is proven. That run is carried from 861e43a.

## Gate - verified at 82f90a2

- `uv run pytest <5 files> -k "<all 32 proof names>" -v` from `services/core`: 35 passed, 0 failed
- `npx vitest run tests/security-headers.test.ts --reporter=verbose` from `frontend`: 2 passed, 0 failed
- `run_rules_tests.py`: 41 passed, exit 0
- `check_csp_pass.py`: exit 0
- `headers-check.sh`: carried from 861e43a (exit 0 at a40d9b8). The frontend is unchanged since then.
- `git status --porcelain` was identical before the round, after run A (which rewrites `contracts/openapi.json` with identical content), and after the worktree was removed. The entries are:
  - ` M services/core/.env.example` (the user's)
  - `?? .playwright-mcp/`
  - `?? .specs/features/33-launch-security-review/verification.md` (this report)

## User-statement and gated checks

- C27: the 2FA state and the access list come from the owner's statement (open question 1, AD-134).
- C29: the rehearsal record was written from a tabletop exercise with the user (open question 2).
- C14: the staging header run is owed after the next deploy.
- C15: the staging CSP pass is owed. The local pass is recorded.
