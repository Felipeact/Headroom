# 05 - Staging on Railway checks

Profile: light
Plan: `.specs/features/05-setup-railway-staging/plan.md`

22 checks in 4 slices · 3 one-way doors in force (1, 3, 4; door 2 superseded) · 0 open

Every proof is a named function in `.specs/features/05-setup-railway-staging/proofs.sh`, run from the repository root as `bash .specs/features/05-setup-railway-staging/proofs.sh cN`. Each function exits non-zero on failure and prints `PASS cN` on success. The functions read Railway only through the documented `@railway/cli` 5.63.1 commands `domain list`, `deployment list`, `logs`, `ssh`, `environment config`, `environment list`, `service list`, `service status`, `tcp-proxy list`, `up` and `config plan`, always with `--environment staging` (and `--json` where the command offers it), and parse JSON with `python3` (no `jq` on this machine). Domains are read from `railway domain list`, never hard-coded. `environment config --json` carries raw variable values, so the proofs print only names and pass/fail, never a value. Under Git Bash on Windows, `railway config plan` runs as `env _=<railway.exe> <railway.exe> config plan`, because the SDK checks the CLI version through `$_` (plan assumption).

## Checks

### S1 - The API deploys to staging and reaches its database · 1 file + proofs · ~6k

**C1** - `curl` on `https://<api staging domain>/healthz/ready`, where the domain comes from `railway domain list --service api --environment staging --json`, returns HTTP `200` with body exactly `{"status":"ok"}` (AC 1, spec Done-when 2)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c1`

**C2** - `curl` on `https://<api staging domain>/healthz/live` returns HTTP `200` with body exactly `{"status":"ok"}` (AC 2)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c2`

**C3** - The deploy logs of the latest `SUCCESS` `api` deployment contain Alembic's `Context impl PostgresqlImpl` line, and inside the running `api` container (`railway ssh --service api --environment staging`) `sqlalchemy.inspect(app.db.get_engine()).has_table('alembic_version')` prints `True` (AC 3, door 3)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c3`

**C4** - Fault injection: `railway up <export>/services/core --path-as-root --service api --environment staging --ci`, on a `git archive HEAD` export in the scratchpad whose `migrations/env.py` raises at import, produces an `api` deployment with status `FAILED`; afterwards the latest `SUCCESS` deployment id is unchanged and C1 still passes (AC 4)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c4`

**C5** - Fault injection: the same command on an export whose `app/main.py` makes `GET /healthz/ready` answer `503` produces an `api` deployment with status `FAILED`; afterwards the latest `SUCCESS` deployment id is unchanged and C1 still passes (AC 5)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c5`

**C6** - `railway domain list --service Postgres --environment staging --json` lists zero domains and `railway tcp-proxy list --service Postgres --environment staging --json` lists zero proxies (AC 6)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c6`

### S2 - The web app deploys to staging and loads · 1 file + proofs · ~4k

**C7** - `curl` on `https://<web staging domain>/` returns HTTP `200` with a `content-type` starting `text/html` and a body containing `<html` (AC 7, spec Done-when 2)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c7`

**C8** - `node .specs/features/05-setup-railway-staging/web-check.mjs <web staging domain>`, using `chromium` from the installed `@playwright/test` with a 375 × 812 viewport, finds a visible `main` element, sees zero `console` messages of type `error`, and measures `document.documentElement.scrollWidth` ≤ 375 (AC 8)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c8`

### S3 - A push to `development` deploys only what changed · proofs only · ~4k

The build pushes three commits to `development`, one at a time and each with the user's go-ahead: commit N changes only files outside both app folders (`.railway/`, `.specs/`, `context/`), commit W changes only `frontend/README.md`, and commit A changes only `services/core/README.md`. The proofs read their SHAs from `git log` by commit subject.

**C9** - After the `web` and `api` checks for commit A succeed, `railway deployment list --service api --environment staging --json` contains a deployment with status `SUCCESS` whose commit SHA is commit A's (AC 9)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c9`

**C10** - After the `web` and `api` checks for commit W succeed, `railway deployment list --service web --environment staging --json` contains a deployment with status `SUCCESS` whose commit SHA is commit W's (AC 10)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c10`

**C11** - The `api` deployment list holds, for commit W's SHA and for commit N's SHA, either nothing or only records with status `SKIPPED` (Railway's record of a commit whose files match no watch pattern; it never builds), checked at least 5 minutes after commit N was pushed (AC 11)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c11`

**C12** - The `web` deployment list holds, for commit A's SHA and for commit N's SHA, either nothing or only records with status `SKIPPED`, checked at least 5 minutes after commit N was pushed (AC 12)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c12`

**C13** - `railway environment config --environment staging --json` gives the source branch `development` for both `api` and `web`, and every commit SHA in both services' deployment lists passes `git merge-base --is-ancestor <sha> origin/development`, so nothing from `ci/spec-04-proof` or any other branch reached staging (AC 13)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c13`

### S4 - No staging secret lives in the repository, and staging matches the reviewed settings · `.railway/` + proofs · ~6k

**C14** - In `.railway/railway.ts`, the only line containing `://` is the door 3 template, every `${{...}}` in the file names `Postgres`, and the file matches none of `token`, `secret`, `railway.internal`, `.up.railway.app` (case-insensitive) (AC 14)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c14`

**C15** - `git ls-files` lists exactly one path matching `(^|/)\.env`, and it is `services/core/.env.example` (AC 15)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c15`

**C16** - The raw (unrendered) `DATABASE_URL` of `api` in `staging`, read from `railway environment config --environment staging --json`, equals exactly `postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}`; the proof prints only `match` or `mismatch` (AC 16, door 3)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c16`

**C17** - `railway service list --environment staging --json` lists, for each of `Postgres`, `api` and `web`, only regions whose name starts with `us-east` (AC 17, door 1)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c17`

**C18** - In `railway status --json`, every environment other than `staging` has zero service instances, so no `api` or `web` deployment can exist there (AC 18, door 1)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c18`

**C19** - `railway service list --environment staging --json` names exactly `Postgres`, `api` and `web`; the staging config gives `api` root directory `/services/core` and `web` root directory `/frontend`, both with repo `Felipeact/Headroom`, branch `development` and `checkSuites` `true` (door 1, door 4)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c19`

**C20** - `railway environment config --environment staging --json` gives `api` `build.builder` `RAILPACK`, `build.watchPatterns` exactly `["/services/core/**"]`, `deploy.preDeployCommand` exactly `["alembic upgrade head"]`, `deploy.startCommand` `fastapi run app/main.py` and `deploy.healthcheckPath` `/healthz/ready`, and `web` `build.builder` `RAILPACK`, `build.watchPatterns` exactly `["/frontend/**"]` and `deploy.healthcheckPath` `/` (door 4)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c20`

**C22** - `railway config plan --detailed-exit-code` against the linked `staging` environment exits 0 with `.railway/railway.ts` at `HEAD`, and `.railway/package.json` pins `railway` to exactly `3.12.0` (AC 19, door 4)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c22`

**C21** - In `services/core/`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy app` and `uv run pytest` all exit 0; in `frontend/`, `npm run lint`, `npm run typecheck`, `npm test` and `npm run build` all exit 0 (AGENTS.md "Before you finish a task"; this spec adds no app code, so this guards against a regression)
Proof: `bash .specs/features/05-setup-railway-staging/proofs.sh c21`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| Landing doors in force (3) | door 1 topology C17 · C18 · C19 · door 3 `DATABASE_URL` C16 · C3 · door 4 IaC C19 · C20 · C22 | - |
| Surface routes (0) | none - the plan's `Surface` adds no route | - |
| staging services (3) | `Postgres` C6 · C17 · C19 · `api` C1 · C17 · C19 · `web` C7 · C17 · C19 | - |
| staging URLs probed (3) | api `/healthz/ready` C1 · api `/healthz/live` C2 · web `/` C7 · C8 | - |
| deploy triggers (5) | api folder changed C9 · web folder changed C10 · api folder untouched C11 · web folder untouched C12 · other branch C13 | - |
| failed-deploy causes (2) | pre-deploy exits non-zero C4 · health check never `200` C5 | - |
| startup config: `DATABASE_URL` reader (2 containers) | app container via `get_settings()` C1 · pre-deploy container via `migrations/env.py` C3 | - |
| finish-checks from AGENTS.md (8) | `ruff format --check` C21 · `ruff check` C21 · `mypy app` C21 · `pytest` C21 · `lint` C21 · `typecheck` C21 · `test` C21 · `build` C21 | - |

- Claims naming a status code, route or response shape: C1, C2, C5, C7. Each proof sends a real HTTPS request to the staging domain.
- No other check claims more than the single case its proof exercises.

## Swept

- validation: C16 (staging `DATABASE_URL` carries the psycopg scheme the AD-001 validator requires); existing - AD-001 rejects any other scheme at start
- failure modes: C4, C5
- idempotency: existing - `alembic upgrade head` at head is a no-op (spec 03 C12), and every `api` deploy reruns it in C3
- authorization: C6 (the database is not reachable from outside); n/a for the probes: AD-002 makes `/healthz/*` public and they return no customer data
- concurrency: n/a - no migration revision exists yet, so two overlapping pre-deploys have nothing to race on; spec 11's first revision must revisit this
- data lifecycle: n/a - the staging database holds only `alembic_version` and, later, synthetic data; backups are out of scope
- dependency failure: C5 (a database that does not answer keeps `/healthz/ready` at `503`, and Railway fails that deploy instead of routing to it)
- state transitions: C1 and C9/C10 (deployment reaches `SUCCESS`), C4 and C5 (deployment ends `FAILED` and the previous `SUCCESS` keeps serving)
- observability: C3 (the pre-deploy migration is visible in the deploy logs); the structured logger and Sentry are spec 08

## Handoff

- S1-S4 touch `.railway/` (~8 KB with the generated README), two READMEs (~2 KB), `proofs.sh` (~12 KB new) and `web-check.mjs` (~2 KB new), and read `plan.md` + `checks.md` (~35 KB): ~59 KB / 4 ≈ 15k, plus Railway CLI and SDK output read while provisioning (~40k) ≈ 55k, under the 150k budget, so one builder
- Mechanism: one builder (no ask, under budget)
- Preconditions met on 2026-10-01: `railway login` done, tree on `development` with spec 04 Done, wait-for-CI answered yes
- **Settled mid-build:** door 2 superseded by door 4 (IaC), the user's choice after Railway rejected Config as Code. C4/C5 inject the fault in the code, not in a config file. C14, C19, C20 rewritten for door 4; C22 added for AC 19; C9/C10 wait for CI (user answered yes)
- **Settled mid-build (2):** Railway writes a `SKIPPED` deployment record for a push that matches no watch pattern, seen for commit N on 2026-10-01; C11/C12 now name it explicitly and C9/C10 require `SUCCESS` (stricter). C3's `railway ssh` needed an SSH key: the user approved creating `~/.ssh/id_ed25519`, registered with Railway as `headroom-dev`; the `ssh.railway.com` ED25519 host key was trusted on first use
- **Abandoned:** `railway up <export>` without `--path-as-root` fails with `prefix not found` when the export is outside the linked directory
- **Verifier round 1 (FAIL) fixes:** C3's proof asserted `alembic current` exit 0, which Alembic returns even with no version table; the proof now queries `has_table('alembic_version')`. C17/C18 text aligned with the commands their proofs read
- **After done (2026-10-01):** a plain `railway service redeploy` rebuilt the newest deployment, which was a C5 fault upload, and failed its health check (staging kept serving). C4/C5 now finish by redeploying `api` from source and waiting for `SUCCESS`, so the newest deployment is always a good one
