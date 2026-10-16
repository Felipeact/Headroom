# 05 - Staging on Railway verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 4a3f716..ebb410e
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

Round 2 was scoped by the fix diff `0d467b6..ebb410e` and by the two round-1 findings that were not PASS: the C3 precision gap, and the contradictions with the binding spec. All 22 proofs ran again in full at `ebb410e`, which is local `development` and has not been pushed. Every proof exited 0.

The fix touched `proofs.sh` (C3 only), `checks.md` (the text of C3, C17 and C18, plus a Handoff line), `plan.md` (Assumptions), and `context/specs/05-setup-railway-staging.md` (an "As built" note). It also committed the round-1 `verification.md` and the lessons files. The edit to `proofs.sh` added 3 lines after line 81, so every citation below line 81 has moved by +3 and has been refreshed.

## Binding sources

Verified at `ebb410e`. Step 1 is owed only under the `ui` profile. It is kept here because round 1 raised a contradiction under it.

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| `context/specs/05-setup-railway-staging.md` Steps | yes - re-read at `ebb410e` | none - round 1's three deviations were resolved by the user, as the next two rows show. The spec's own "As built (confirmed with the user on 2026-10-01)" note (spec line 22) states each one: the database service is named `Postgres`; the API starts with `fastapi run app/main.py` and migrates with `alembic upgrade head`, without `uv run`. Those are exactly the literals C19 asserts (`proofs.sh:238`) and C20 asserts (`proofs.sh:254-255`). | - |
| `.specs/features/05-setup-railway-staging/plan.md` Assumptions | yes | none - plan.md:128 (command spelling) now reads `Confirmed? y`. plan.md:129 is a new row for the database service name `Postgres`, also `y`, and says the user confirmed it on 2026-10-01 after the Verifier flagged it. The records say what the coordinator claimed. | - |
| `context/specs/05-setup-railway-staging.md` Done-when | yes - carried from `0d467b6`, untouched by the fix | none - "merging into `development` deploys both apps" is covered by C9 and C10, with C11-C13 for scope. "`/healthz/ready` returns 200, and the web app loads" is covered by C1, C7 and C8. | - |
| `AGENTS.md` Deployment, Security and data handling | yes - carried from `0d467b6`, untouched by the fix | none - staging deploys only from `development` (C13, C19). Secrets live only in Railway variables (C14, C15, C16). | - |

The new Handoff line in checks.md was also checked: it records the round-1 fixes accurately.

## Checks

The proofs were re-run in full at `ebb410e` in three invocations:
- `proofs.sh c1 c2 c3 c6 c7 c8 c9 c10 c11 c12 c13 c14 c15 c16 c17 c18 c19 c20 c22`: exit 0, with every `PASS cN` printed
- `proofs.sh c4 c5`: exit 0
- `proofs.sh c21`: exit 0

Citations were refreshed for `proofs.sh`, the only proof file the fix touched. The `web-check.mjs` and `.railway/` citations are carried from `0d467b6`, since those files are unchanged.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `/healthz/ready` on the api staging domain returns `200` with body exactly `{"status":"ok"}` | `PASS c1` | `proofs.sh:72` - `http_check c1 "https://$(domain_of api)/healthz/ready" 200 '{"status":"ok"}'`; `proofs.sh:68-69` - `[ "$status" = "$3" ]`, `[ "$body" = "$4" ]` | PASS |
| C2 | `/healthz/live` returns `200` with body exactly `{"status":"ok"}` | `PASS c2` | `proofs.sh:74` - `http_check c2 ".../healthz/live" 200 '{"status":"ok"}'`; `proofs.sh:68-69` | PASS |
| C3 | the deploy logs show `Context impl PostgresqlImpl`, and `has_table('alembic_version')` prints `True` inside the running api container | `PASS c3` | `proofs.sh:79` - `railway logs "$id" ... --deployment --lines 1000` piped to `grep -q 'Context impl PostgresqlImpl'`; `proofs.sh:83-84` - `railway ssh ... -- python -c "...print(inspect(get_engine()).has_table('alembic_version'))"`, keeping the last stdout line; `proofs.sh:85` - `[ "$has_table" = "True" ]`, else `fail c3`. The round-1 precision gap is closed: a missing table prints `False` and fails, and an ssh failure leaves the value empty and fails. | PASS |
| C4 | `railway up` of an export whose `migrations/env.py` raises gives an api deployment `FAILED`; the latest SUCCESS id is unchanged and C1 still passes | `Deploy failed: Pre-deploy command failed`, `PASS c4` | `proofs.sh:106` - injects `raise SystemExit(...)` into `env.py`; `proofs.sh:98` - `x=d[0]; assert x['id']!='$before' and x['status']=='FAILED'`; `proofs.sh:101` - `[ "$before" = "$after" ]`; `proofs.sh:102` - `c1` | PASS |
| C5 | an export whose `/healthz/ready` answers `503` gives an api deployment `FAILED`; the latest SUCCESS id is unchanged and C1 still passes | `Attempt #14 failed with HTTP 503`, `Deploy failed: Healthcheck failure`, `PASS c5` | `proofs.sh:111-118` - overrides the route to `return _R(status_code=503)` (`:117`); `proofs.sh:98`, `:101` and `:102` as in C4 | PASS |
| C6 | Postgres has zero domains and zero TCP proxies | `PASS c6` | `proofs.sh:123` - `assert d['domains']==[]`; `proofs.sh:125` - `assert d['proxies']==[]` | PASS |
| C7 | web `/` returns `200`, `text/html` and a body containing `<html` | `PASS c7` | `proofs.sh:135` - `head -1` piped to `grep -q ' 200'`; `proofs.sh:136` - `grep -iq '^content-type: text/html'`; `proofs.sh:137` - `grep -q '<html' "$body"` | PASS |
| C8 | at 375x812: a visible `main`, zero console errors, `scrollWidth <= 375` | `PASS c8` | `web-check.mjs:20` - `viewport: { width: 375, height: 812 }`; `web-check.mjs:27` - `page.locator("main").first().isVisible()`; `web-check.mjs:29` - `if (scrollWidth > 375)`; `web-check.mjs:30` - `if (consoleErrors.length)` | PASS |
| C9 | after CI succeeds for commit A, api has a `SUCCESS` deployment for its SHA | `PASS c9` | `proofs.sh:61` - `conclusion = "success"`; `proofs.sh:147` - `has_deployment_for api "$sha" = yes`, where `proofs.sh:57` prints `yes` only `if 'SUCCESS' in s` | PASS |
| C10 | after CI succeeds for commit W, web has a `SUCCESS` deployment for its SHA | `PASS c10` | `proofs.sh:154` - `has_deployment_for web "$sha" = yes`; `proofs.sh:57` | PASS |
| C11 | api has nothing or only `SKIPPED` for commits W and N, at least 5 minutes after CI | `PASS c11` | `proofs.sh:163` - `>= timedelta(minutes=5)`; `proofs.sh:170-171` - `has_deployment_for api ... = no`, where `proofs.sh:57` prints `no` only `if s<={'SKIPPED'}` | PASS |
| C12 | web has nothing or only `SKIPPED` for commits A and N, at least 5 minutes after CI | `PASS c12` | `proofs.sh:163`; `proofs.sh:178-179` - `has_deployment_for web ... = no` | PASS |
| C13 | api and web track `development`; every deployed SHA is an ancestor of `origin/development` | `PASS c13` | `proofs.sh:188` - `assert ...['source']['branch']=='development'`; `proofs.sh:191` - `git merge-base --is-ancestor "$sha" origin/development` over the last 100 deployments (`proofs.sh:40`) | PASS |
| C14 | `.railway/railway.ts` has only the door 3 template as a `://` line, only `Postgres` references, and no forbidden patterns | `PASS c14` | `proofs.sh:199` - `grep -c '://' = 1`; `proofs.sh:200` - `grep -F -q "\"$DB_TEMPLATE\""`; `proofs.sh:201` - `grep -v -q '\${{Postgres\.' && fail`; `proofs.sh:202` - `grep -E -i -q` on `token`, `secret`, `railway\.internal`, `\.up\.railway\.app`, then `&& fail`; `.railway/railway.ts:31` is the only `://` line | PASS |
| C15 | the only tracked `.env*` file is `services/core/.env.example` | `PASS c15` | `proofs.sh:208` - `[ "$found" = "services/core/.env.example" ]` | PASS |
| C16 | the raw api `DATABASE_URL` equals the door 3 template exactly | `match`, `PASS c16` | `proofs.sh:214` - `ok=v==sys.argv[1]`, with `$DB_TEMPLATE` from `proofs.sh:11` | PASS |
| C17 | `railway service list` gives only `us-east` regions for `Postgres`, `api` and `web` | `PASS c17` | `proofs.sh:222` - `assert names.get(n) and all(r.startswith('us-east') for r in names[n])`. The check text now names the command the proof reads. | PASS |
| C18 | `railway status` shows zero service instances in every environment other than staging | `PASS c18` | `proofs.sh:232` - `assert n['serviceInstances']['edges']==[]`. The check text now names the command the proof reads. | PASS |
| C19 | the services are exactly `Postgres`, `api` and `web`; root directories, repo, branch `development` and `checkSuites` true | `PASS c19` | `proofs.sh:238` - `assert sorted(...)==['Postgres','api','web']`; `proofs.sh:243` - `assert (rootDirectory, repo, branch, checkSuites)==('$dir','Felipeact/Headroom','development',True)` | PASS |
| C20 | the live build and deploy settings equal the listed literals | `PASS c20` | `proofs.sh:253` - `RAILPACK` and `['/services/core/**']`; `:254` - `preDeployCommand==['alembic upgrade head']`; `:255` - `startCommand=='fastapi run app/main.py'`; `:256` - `healthcheckPath=='/healthz/ready'`; `:257` - web `RAILPACK` and `['/frontend/**']`; `:258` - web `healthcheckPath=='/'` | PASS |
| C21 | the api and web finish-checks all exit 0 | `proofs.sh c21` exit 0, `PASS c21` | `proofs.sh:264` - `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q`; `proofs.sh:266` - `npm run lint && npm run typecheck && npm test && npm run build` | PASS |
| C22 | `railway config plan --detailed-exit-code` exits 0; `railway` is pinned at `3.12.0` | `PASS c22` | `proofs.sh:272` - `railway_iac config plan --detailed-exit-code`, else `fail c22`; `proofs.sh:273` - `assert d['dependencies']=={'railway':'3.12.0'}` | PASS |

## Level and precision

Verified at `ebb410e`.

- **C3:** the round-1 precision gap is closed. The proof now asks the schema directly, through the same `app.db.get_engine()` the app container uses, and compares the output to exactly `True` (`proofs.sh:85`).
- **C17 and C18:** the round-1 check-text drift is closed. checks.md now names `railway service list` and `railway status`.
- **C1, C2, C5 and C7:** carried from `0d467b6`. These claims name a status code or a response shape, and each proof sends a real HTTPS request to the staging domain. There is no level gap.
- **C13:** carried from `0d467b6`. It looks only at the 100 most recent deployments per service (`proofs.sh:40`), which today covers every deployment.

## Coverage

Not recomputed. The `Coverage` recompute runs only under the `standard` and `ui` profiles, and this feature is `light`. Carried from `0d467b6`.

## Faults injected

Not owed under `light`. C4 and C5 are fault-injection proofs against staging, and both were re-run at `ebb410e` (see the Checks table). Each run left one more FAILED `api` deployment record in staging, as intended.

## Swept existing

Carried from `0d467b6`; the fix touched neither file.

- **validation:** `services/core/app/settings.py:17-18` - `if not value.startswith(DATABASE_SCHEME): raise ValueError(...)`. Holds.
- **idempotency:** `.specs/features/03-setup-database/checks.md:55` - a second `alembic upgrade head` exits 0. Holds.

## Gate

At `ebb410e`:
- `bash .specs/features/05-setup-railway-staging/proofs.sh c1 c2 c3 c6 c7 c8 c9 c10 c11 c12 c13 c14 c15 c16 c17 c18 c19 c20 c22`: 19 passed
- `proofs.sh c4 c5`: 2 passed
- `proofs.sh c21`: 1 passed

That is 22 passed and 0 failed.
