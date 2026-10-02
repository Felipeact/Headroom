# 05 - Staging on Railway verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: 4a3f716..0d467b6e6bb6e0f0d37d74f0b98345282163920d
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

All 22 proofs exit 0 at `0d467b6` (local `development`, one commit ahead of `origin/development` at `f4bab5e`; the extra commit touches only `.specs/`). The verdict is FAIL on one proof that cannot reach its own claim (C3, precision gap) and on a literal contradiction between the checks and the binding spec's Steps. Every other check is proven with a located assertion.

## Binding sources

Step 1 is owed only under `ui`; this feature is `light`. The caller asked for contradictions with the binding spec to be noted, so the comparison was done and is recorded here.

| Source | Opened | Contradiction | Uncovered |
| --- | --- | --- | --- |
| `context/specs/05-setup-railway-staging.md` Steps | yes - read in full | `api` start command: spec says `uv run fastapi run app/main.py --port $PORT`, C20 asserts `startCommand == 'fastapi run app/main.py'` (`proofs.sh:252`); pre-deploy: spec says `uv run alembic upgrade head`, C20 asserts `['alembic upgrade head']` (`proofs.sh:251`); database service: spec names it `postgres`, C19 asserts `Postgres` (`proofs.sh:235`). The plan records the command spelling as an assumption marked `Confirmed? n` (plan.md:128); the service name comes from door 1 with no assumption row | - |
| `context/specs/05-setup-railway-staging.md` Done-when | yes | none - "merging into `development` deploys both apps" is C9 · C10 (with C11-C13 for scope); "`/healthz/ready` returns 200, and the web app loads" is C1 · C7 · C8 | - |
| `AGENTS.md` Deployment, Security and data handling | yes | none - staging deploys only from `development` (C13, C19); secrets only in Railway variables (C14, C15, C16) | - |

Note on the contradiction row: the behaviour the spec asks for holds - `fastapi-cli` declares `envvar="PORT"` for `--port` in the installed version (checked from `fastapi_cli.cli` source), and C1 shows the deployed API answering through Railway's routed port; C3/C4 show the pre-deploy migration runs and gates the deploy. The finding is that the checks assert a different literal from the binding source with no user confirmation recorded; it is closed either by the user confirming plan.md:128 (and the `Postgres` name) or by changing the settings.

## Checks

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `/healthz/ready` on the api staging domain -> `200`, body exactly `{"status":"ok"}` | `proofs.sh c1 c2 c3 c6 c7 c8` exit 0, `PASS c1` | `proofs.sh:72` - `http_check c1 "https://$(domain_of api)/healthz/ready" 200 '{"status":"ok"}'`; `proofs.sh:68-69` - `[ "$status" = "$3" ]`, `[ "$body" = "$4" ]` (exact string compare); domain from `proofs.sh:31` `railway domain list --service api` | PASS |
| C2 | `/healthz/live` -> `200`, body exactly `{"status":"ok"}` | same run, `PASS c2` | `proofs.sh:74` - `http_check c2 ".../healthz/live" 200 '{"status":"ok"}'`; `proofs.sh:68-69` | PASS |
| C3 | deploy logs of latest SUCCESS api deployment show `Context impl PostgresqlImpl`, and `alembic current` exits 0 "which needs the `alembic_version` table" | same run, `PASS c3` | `proofs.sh:79` - `railway logs "$id" ... --deployment --lines 1000 \| grep -q 'Context impl PostgresqlImpl'`; `proofs.sh:81` - `railway ssh --service api ... -- alembic current >/dev/null`. Precision gap: installed Alembic `runtime/migration.py:524-525` - `if not self._has_version_table(): return ()`, so `alembic current` exits 0 with no `alembic_version` table; the proof cannot fail on the AC 3 table requirement it claims. Verifier confirmed by a read-only `railway ssh ... inspect(get_engine()).has_table("alembic_version")` -> `True`, so the behaviour holds today, but no proof asserts it | FAIL (proof does not reach the table half of its claim) |
| C4 | `railway up` of an export whose `migrations/env.py` raises -> api deployment `FAILED`; latest SUCCESS id unchanged; C1 still passes | `proofs.sh c4 c5` (background); `Deploy failed: Pre-deploy command failed`, `PASS c4` | `proofs.sh:103` - injects `raise SystemExit("spec 05 c4 fault")` into `services/core/migrations/env.py`; `proofs.sh:95` - `x=d[0]; assert x['id']!='$before' and x['status']=='FAILED'`; `proofs.sh:98` - `[ "$before" = "$after" ]`; `proofs.sh:99` - `c1` | PASS |
| C5 | export whose `/healthz/ready` answers `503` -> api deployment `FAILED`; latest SUCCESS id unchanged; C1 still passes | `proofs.sh c4 c5` exit 0; `Attempt #14 failed with HTTP 503`, `Deploy failed: Healthcheck failure`, `PASS c5` | `proofs.sh:108-115` - appends a route override returning `_R(status_code=503)` for `/healthz/ready` to `app/main.py`; `proofs.sh:95`, `:98`, `:99` as C4 | PASS |
| C6 | Postgres has zero domains and zero TCP proxies in staging | `PASS c6` | `proofs.sh:120` - `assert d['domains']==[]`; `proofs.sh:122` - `assert d['proxies']==[]` | PASS |
| C7 | web `/` -> `200`, `content-type` starts `text/html`, body contains `<html` | `PASS c7` | `proofs.sh:132` - `head -1 \| grep -q ' 200'`; `proofs.sh:133` - `grep -iq '^content-type: text/html'`; `proofs.sh:134` - `grep -q '<html' "$body"` | PASS |
| C8 | Chromium 375x812: visible `main`, zero console errors, `scrollWidth <= 375` | `PASS c8` | `web-check.mjs:20` - `viewport: { width: 375, height: 812 }`; `web-check.mjs:27` - `page.locator("main").first().isVisible()`; `web-check.mjs:29` - `if (scrollWidth > 375) failures.push(...)`; `web-check.mjs:30` - `if (consoleErrors.length) failures.push(...)`; `web-check.mjs:23` collects `message.type() === "error"` | PASS |
| C9 | after CI succeeds for commit A, api has a `SUCCESS` deployment for commit A's SHA | `proofs.sh c9 ... c22` exit 0, `PASS c9` | `proofs.sh:143` - `ci_succeeded "$sha"` (`proofs.sh:61` `conclusion = "success"`); `proofs.sh:144` - `has_deployment_for api "$sha" = yes`, where `proofs.sh:57` prints `yes` only `if 'SUCCESS' in s` | PASS |
| C10 | after CI succeeds for commit W, web has a `SUCCESS` deployment for commit W's SHA | same run, `PASS c10` | `proofs.sh:150-151` - `ci_succeeded`, `has_deployment_for web "$sha" = yes` | PASS |
| C11 | api has nothing or only `SKIPPED` for commits W and N, >= 5 min after CI | same run, `PASS c11` | `proofs.sh:166` - `settled_since_ci` (`proofs.sh:160` `>= timedelta(minutes=5)`); `proofs.sh:167-168` - `has_deployment_for api "$w"/"$n" = no`, where `proofs.sh:57` prints `no` only `if s<={'SKIPPED'}` | PASS |
| C12 | web has nothing or only `SKIPPED` for commits A and N, >= 5 min after CI | same run, `PASS c12` | `proofs.sh:174-176` - `settled_since_ci`, `has_deployment_for web "$a"/"$n" = no` | PASS |
| C13 | api and web track `development`; every deployed SHA is an ancestor of `origin/development` | same run, `PASS c13` | `proofs.sh:185` - `assert d['services']['$id']['source']['branch']=='development'`; `proofs.sh:188` - `git merge-base --is-ancestor "$sha" origin/development` for every `commitHash` in the last 100 deployments (`proofs.sh:40` `--limit 100`) | PASS |
| C14 | `.railway/railway.ts`: one `://` line, the door 3 template; every `${{` names `Postgres`; no `token`/`secret`/`railway.internal`/`.up.railway.app` | same run, `PASS c14` | `proofs.sh:196` - `grep -c '://' = 1`; `proofs.sh:197` - `grep -F -q "\"$DB_TEMPLATE\""`; `proofs.sh:198` - `grep -v -q '\${{Postgres\.' && fail`; `proofs.sh:199` - `grep -E -i -q 'token\|secret\|railway\.internal\|\.up\.railway\.app' && fail`. Read against `.railway/railway.ts:31` (the only `://` line) | PASS |
| C15 | `git ls-files` has exactly one `.env*` path, `services/core/.env.example` | same run, `PASS c15` | `proofs.sh:205` - `[ "$found" = "services/core/.env.example" ]` | PASS |
| C16 | raw api `DATABASE_URL` equals the door 3 template exactly | same run, `match`, `PASS c16` | `proofs.sh:211` - `ok=v==sys.argv[1]` with `sys.argv[1]` = `$DB_TEMPLATE` (`proofs.sh:11`) | PASS |
| C17 | `Postgres`, `api`, `web` each in a region starting `us-east` | same run, `PASS c17` | `proofs.sh:219` - `assert names.get(n) and all(r.startswith('us-east') for r in names[n])` for `('Postgres','api','web')`. Reads `railway service list` regions, not `environment config` as the check text says; same claim, different source. `.railway/railway.ts:4` pins `us-east4-eqdc4a` | PASS |
| C18 | no environment other than staging has api/web deployments | same run, `PASS c18` | `proofs.sh:229` - `assert n['serviceInstances']['edges']==[]` for every non-staging environment from `railway status --json`. Stronger than the check text (no service instance at all, so no deployment possible), but reads `railway status`, not `railway deployment list` as checks.md says | PASS |
| C19 | staging services exactly `Postgres`/`api`/`web`; api `/services/core`, web `/frontend`, repo `Felipeact/Headroom`, branch `development`, `checkSuites` true | same run, `PASS c19` | `proofs.sh:235` - `assert sorted(s['name'] for s in d)==['Postgres','api','web']`; `proofs.sh:240` - `assert (rootDirectory, repo, branch, checkSuites)==('$dir','Felipeact/Headroom','development',True)` | PASS |
| C20 | live build/deploy settings equal the listed literals | same run, `PASS c20` | `proofs.sh:250` - `builder=='RAILPACK' and watchPatterns==['/services/core/**']`; `:251` - `preDeployCommand==['alembic upgrade head']`; `:252` - `startCommand=='fastapi run app/main.py'`; `:253` - `healthcheckPath=='/healthz/ready'`; `:254` - web `RAILPACK`, `['/frontend/**']`; `:255` - web `healthcheckPath=='/'` | PASS |
| C21 | ruff format/check, mypy, pytest; lint, typecheck, test, build all exit 0 | `proofs.sh c21` exit 0, `PASS c21` | `proofs.sh:261` - `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q`; `proofs.sh:263` - `npm run lint && npm run typecheck && npm test && npm run build` | PASS |
| C22 | `railway config plan --detailed-exit-code` exits 0; `.railway/package.json` pins `railway` `3.12.0` | same run, `PASS c22` | `proofs.sh:269` - `railway_iac config plan --detailed-exit-code ... \|\| fail`; `proofs.sh:270` - `assert d['dependencies']=={'railway':'3.12.0'}`; `.railway/package.json` pins `"railway": "3.12.0"`. The plan runs against the linked environment; `railway status` shows it is `staging` | PASS |

## Level and precision

- C3 (precision gap, the FAIL): AC 3 requires the staging database to contain `alembic_version`; `alembic current` exits 0 without it (Alembic `migration.py:524-525`). The log grep proves the pre-deploy migration connected to Postgres, not that the table exists. A proof such as `railway ssh ... -- python -c "...inspect(get_engine()).has_table('alembic_version')"` asserting `True` would close it; the verifier ran exactly that read-only and got `True`.
- C1, C2, C5, C7: claims naming a status and body are proven at the boundary (real HTTPS to the staging domain); no level gap.
- C17, C18: the proofs read different CLI commands from the ones checks.md names (`service list` / `status` instead of `environment config` / `deployment list`). Both settle the claim (C18 more strictly); recorded as a check-text drift, not a gap.
- C13: covers the 100 most recent deployments per service (`proofs.sh:40`); all existing deployments today fall inside that window.
- C9/C10 read the CI run with `.[0]` (`proofs.sh:61`), the latest run for that SHA; adequate for one run per commit.

## Coverage

Not recomputed: the `Coverage` recompute runs under `standard` and `ui`, and this feature is `light`.

## Faults injected

Fault injection is not owed under `light`. C4 and C5 are themselves fault-injection proofs against staging and were run as part of step 2 (see the Checks table).

## Swept existing

- validation (C16; existing - AD-001 rejects any other scheme at start): present at `services/core/app/settings.py:17-18` - `if not value.startswith(DATABASE_SCHEME): raise ValueError(...)`, with `DATABASE_SCHEME = "postgresql+psycopg://"` at `settings.py:6`. Holds.
- idempotency (existing - `alembic upgrade head` at head is a no-op, spec 03 C12): present at `.specs/features/03-setup-database/checks.md:55` (second `alembic upgrade head` exits 0). Holds.

## Gate

`bash .specs/features/05-setup-railway-staging/proofs.sh c1 c2 c3 c6 c7 c8` - 6 passed; `proofs.sh c9 c10 c11 c12 c13 c14 c15 c16 c17 c18 c19 c20 c22` - 13 passed; `proofs.sh c21` - 1 passed; `proofs.sh c4 c5` - 2 passed. 0 proofs failed; C3 fails on evidence, not on exit code.
