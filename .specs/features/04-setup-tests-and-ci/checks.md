# 04 - Tests and CI checks

Profile: light
Plan: `.specs/features/04-setup-tests-and-ci/plan.md`

17 checks in 3 slices · 2 one-way doors · 0 open, of which 0 block

Every proof is a named function in `.specs/features/04-setup-tests-and-ci/proofs.sh`, run from the
repository root with `bash .specs/features/04-setup-tests-and-ci/proofs.sh <cN>`. Each exits
non-zero on failure and prints `PASS cN` on success. The frontend proofs assert on exit codes of
the npm scripts; the CI and settings proofs assert on the workflow file and on GitHub's own
records through `gh`. C11, C12 and C15 read the throwaway pull request from `ci/spec-04-proof`
into `development`; its number is recorded under `## Handoff` once it exists.

## Checks

### S1 - The frontend checks run locally · ~8 files · ~6k

**C1** - In `frontend/`, the `typecheck` script is exactly `next typegen && tsc --noEmit`, and `npm run typecheck` exits 0 on the committed code with no `.next/` folder and no `next-env.d.ts` present, as on a fresh clone (AC 1; amended with the user on 2026-10-01 - plain `tsc --noEmit` fails on a fresh clone because Next generates `LayoutProps` and `next-env.d.ts`)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c1`

**C2** - With a temporary file `frontend/app/zz-type-error.tsx` containing `const n: number = "not a number"`, `npm run typecheck` exits non-zero and reports an error in `zz-type-error.tsx`; the file is removed afterwards (AC 2)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c2`

**C3** - With `CI` unset, `npm test` in `frontend/` exits 0 on its own within 120 seconds (no watch mode), uses the `jsdom` environment, and its output reports `app/page.test.tsx` passing, a test that renders `app/page.tsx` with `@testing-library/react` (AC 3)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c3`

**C4** - With temporary always-failing files `frontend/e2e/zz-canary.test.ts` and `frontend/e2e/zz-canary.spec.ts` in place, `npm test` still exits 0; both files are removed afterwards (AC 4, door 2)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c4`

**C5** - `frontend/playwright.config.ts` sets `testDir` to `./e2e` and a `webServer` on `http://localhost:3000`, and `npm run test:e2e` exits 0 with at least one passing test in `frontend/e2e/` that loads `/` (AC 5, door 2)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c5`

**C6** - `npm run lint` and `npm run build` in `frontend/` both exit 0 (AC 6)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c6`

### S2 - CI runs both jobs on every pull request · 1 file + remote · ~3k

**C7** - `.github/workflows/ci.yml` has `name: CI`, triggers on `pull_request` with branches exactly `development` and `main` and on `push` with branches exactly `development`, and has exactly two jobs, `web` and `api`, neither with a `name:` override (AC 7, door 1)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c7`

**C8** - Job `web` runs in `frontend/`, and its `run` steps are, in this order, `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, each as its own step (AC 8)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c8`

**C9** - Job `api` runs in `services/core/`, has a step using `astral-sh/setup-uv`, and its `run` steps end with, in this order, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy app`, `uv run pytest`, each as its own step (AC 9)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c9`

**C10** - Job `api` declares a `postgres:17` service mapped to port `5432` and sets `DATABASE_URL` to `postgresql+psycopg://` on `localhost:5432`; in the green run of C11, the `api` job log shows pytest's summary with `passed` and no `skipped` (AC 10)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c10`

**C11** - A `CI` run for event `pull_request` on branch `ci/spec-04-proof` has conclusion `success`, with jobs `web` and `api` both `success` (AC 11, spec Done-when 1)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c11`

**C12** - The latest `CI` run on `ci/spec-04-proof`, whose head commit adds a type error to a `.tsx` file under `frontend/`, has conclusion `failure`, and in its `web` job the step `npm run typecheck` has conclusion `failure` (AC 12, spec Done-when 2)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c12`

**C13** - `.github/workflows/ci.yml` contains no `secrets.` reference, and the Postgres user, password and database in it are `headroom`, `localdev`, `headroom`, the same as `docker-compose.yml` (AC 13)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c13`

### S3 - The repository enforces it · remote settings · ~1k

**C14** - `gh api repos/Felipeact/Headroom/branches/<b>/protection` for `development` and for `main` lists required status check contexts exactly `api` and `web`, and `enforce_admins.enabled` is `false` (AC 14, door 1)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c14`

**C15** - While its latest run is red, the pull request from `ci/spec-04-proof` into `development` reports `mergeStateStatus` `BLOCKED` (AC 15)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c15`

**C16** - `gh api repos/Felipeact/Headroom/vulnerability-alerts` answers HTTP `204` (AC 16)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c16`

**C17** - The CI run for the push of the feature's last commit to `development` has conclusion `success` with jobs `web` and `api` both `success` (AC 7, AC 11 on the working branch)
Proof: `bash .specs/features/04-setup-tests-and-ci/proofs.sh c17`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| Landing doors (2) | door 1 check names C7, C14 · door 2 test layout C4, C5 | - |
| new npm scripts (3) | `typecheck` C1 · `test` C3 · `test:e2e` C5 | - |
| `web` job commands (5) | `npm ci` C8 · `npm run lint` C8 · `npm run typecheck` C8, C12 · `npm test` C8 · `npm run build` C8 | - |
| `api` job commands (4) | `ruff format --check` C9 · `ruff check` C9 · `mypy app` C9 · `pytest` C9, C10 | - |
| workflow triggers (3) | PR into `development` C7, C11 · PR into `main` C7 · push to `development` C7, C17 | - |
| protected branches (2) | `development` C14, C15 · `main` C14 | - |
| run outcomes (2) | green C11, C17 · red C12, C15 | - |
| startup config: where the API tests get `DATABASE_URL` in CI (1 assembly) | CI job env C10 | - |

- C11, C12, C15, C17 read GitHub's records of real runs; C7-C10 and C13 read the workflow file
- Protection on `main` is proven by its settings (C14) only; no pull request into `main` is opened, because those are for releases
- No other check claims more than the single case its proof exercises

## Swept

- validation: C2, C12 - a type error fails locally and in CI
- failure modes: C12 - a failing step fails the job and the run, and names the step
- idempotency: n/a - the jobs change nothing outside the runner; a rerun is safe
- authorization: C13, C14 - no secrets in the workflow; protection is settings-only, changed by the owner
- concurrency: n/a - two independent jobs, no shared state; strict mode is off (door 1)
- data lifecycle: n/a - nothing persists; the throwaway branch and pull request are deleted after verification
- dependency failure: n/a - a GitHub Actions outage leaves checks pending and merges blocked, which is the safe direction
- state transitions: C11, C12, C15 - green to red on the same pull request, and red is blocked
- observability: C12 - each command is its own step, so the failed step names the check

## Handoff

- S1-S3 = ~10k (about 8 small frontend files, generated Vitest and Playwright setup, one workflow, `proofs.sh`), under the 150k budget - one builder
