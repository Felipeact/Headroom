# 04 - Tests and CI verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 7b9f969..1e25913
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

HEAD = `origin/development` = `1e2591356360bf8f0774c1fd5870e43c6206b182`. Feature commits reviewed: `efcfb78`, `52a7c0c`, `dd0c7fc`, `1e25913` (`git log --oneline 7b9f969..HEAD`; 14 files, `git diff --stat`).

## Binding sources

Step 1 does not run under profile `light`. `context/specs/04-setup-tests-and-ci.md` was still opened and read (Steps and Done-when) to judge whether the checks reach it. One known divergence: the spec's Steps say `typecheck` is `tsc --noEmit`, while C1 requires `next typegen && tsc --noEmit`. checks.md:19 records that this was changed with the user on 2026-10-01. `ruff format --check` in the `api` job goes beyond the spec, and plan Assumptions record that choice. Neither is counted as a contradiction.

## Checks

All proofs ran at HEAD `1e25913` from the repo root. The run `proofs.sh c1 c2 ... c16` covered C1 to C16 in one go. C15's first read failed (see the note under the table) and was rerun with `proofs.sh c15 c16`. `proofs.sh c17` ran after `gh run watch 36957308625 --exit-status` exited 0. Each check printed its own `PASS cN` line.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `typecheck` is exactly `next typegen && tsc --noEmit` and exits 0 with no `.next/` or `next-env.d.ts` | `proofs.sh c1` -> `PASS c1` | `.specs/features/04-setup-tests-and-ci/proofs.sh:32` - `[ "$script" = "next typegen && tsc --noEmit" ]`; `proofs.sh:33-34` - `rm -rf .next next-env.d.ts`, then `npm run typecheck` must exit 0 or `fail`; reads `frontend/package.json:10` | PASS |
| C2 | a temporary `app/zz-type-error.tsx` makes typecheck exit non-zero, the error names that file, and the file is removed | `proofs.sh c2` -> `PASS c2` (the log shows `app/zz-type-error.tsx(1,14): error TS2322`) | `proofs.sh:42` - `if out="$(in_web npm run typecheck 2>&1)"; then fail`; `proofs.sh:44` - `grep -q 'zz-type-error\.tsx'`; cleanup `proofs.sh:39` trap RETURN | PASS |
| C3 | with `CI` unset, `npm test` exits within 120 s, uses jsdom, and reports `app/page.test.tsx` passing, which renders `app/page.tsx` with Testing Library | `proofs.sh c3` -> `PASS c3` (the log shows `✓ app/page.test.tsx > Page renders its main heading`) | `proofs.sh:49` - `env -u CI timeout 120 npm test` must exit 0; `proofs.sh:51` - grep for a check mark on `app/page.test.tsx` in the verbose output; `proofs.sh:52` reads `frontend/vitest.config.mts:8` `environment: 'jsdom'`; `proofs.sh:53-54` read `frontend/app/page.test.tsx:2-3,6` (`@testing-library/react`, `import Page from './page'`, `render(<Page />)`); `frontend/package.json:11` `"test": "vitest run"` | PASS |
| C4 | failing canaries `e2e/zz-canary.test.ts` and `.spec.ts` leave `npm test` at exit 0, and both are removed | `proofs.sh c4` -> `PASS c4` | `proofs.sh:62` writes `expect(1).toBe(2)` to both files; `proofs.sh:64` - `env -u CI timeout 120 npm test` must exit 0 or `fail`; the exclusion is at `frontend/vitest.config.mts:10` `exclude: [...configDefaults.exclude, 'e2e/**']`; cleanup trap at `proofs.sh:59` | PASS |
| C5 | `testDir` is `./e2e`, the webServer is on `http://localhost:3000`, and `test:e2e` exits 0 with at least one passing test that loads `/` | `proofs.sh c5` -> `PASS c5` (`1 passed (6.0s)`; port 3000 was free beforehand, so Playwright started the server itself) | `proofs.sh:69` reads `frontend/playwright.config.ts:15`; `proofs.sh:70-71` read `playwright.config.ts:74,76`; `proofs.sh:72` reads `frontend/e2e/home.spec.ts:4` `page.goto('/')`; `proofs.sh:75` - `grep -qE '[1-9][0-9]* passed'` | PASS |
| C6 | `npm run lint` and `npm run build` both exit 0 | `proofs.sh c6` -> `PASS c6` | `proofs.sh:79` - `npm run lint` must exit 0 or `fail`; `proofs.sh:80` - `npm run build` must exit 0 or `fail` | PASS |
| C7 | the workflow is named `CI`; PR branches are exactly development and main; push is development only; the jobs are exactly `web` and `api` with no `name:` | `proofs.sh c7` -> `PASS c7` | `proofs.sh:84-88` (e.g. `[ "$(wf "sorted(w['jobs'])")" = '["api", "web"]' ]`, `:88` no-name list `= '[]'`); reads `.github/workflows/ci.yml:4,7-10,16,34` | PASS |
| C8 | `web` runs in `frontend` and its run steps, in order, are ci, lint, typecheck, test, build, each as its own step | `proofs.sh c8` -> `PASS c8` | `proofs.sh:92` working-directory `= '"frontend"'`; `proofs.sh:93` - `[ "$(run_steps web)" = '["npm ci", "npm run lint", "npm run typecheck", "npm test", "npm run build"]' ]`; reads `ci.yml:20,28-32` | PASS |
| C9 | `api` runs in `services/core`, uses `astral-sh/setup-uv`, and its run steps end with format --check, check, mypy and pytest, in that order | `proofs.sh c9` -> `PASS c9` | `proofs.sh:98` working-directory; `proofs.sh:99` `startswith('astral-sh/setup-uv@')` `= true`; `proofs.sh:101-102` last-4 run steps equality; reads `ci.yml:38,58,62-65` | PASS |
| C10 | a `postgres:17` service on 5432, a `DATABASE_URL` of `postgresql+psycopg://...@localhost:5432`, and a green PR run whose api log shows `passed` and no `skipped` | `proofs.sh c10` -> `PASS c10`. Independently, run `36957067839` api log: `16 passed, 1 warning`, with `DATABASE_URL: ***localhost:5432/headroom` | `proofs.sh:112` image `= '"postgres:17"'`; `:113` ports `= '["5432:5432"]'`; `:114` regex `^"postgresql\+psycopg://[^@]+@localhost:5432/`; `:119-120` passed / no skipped; reads `ci.yml:41,48,55` | PASS |
| C11 | a `pull_request` CI run on `ci/spec-04-proof` succeeded, with `web` and `api` both `success` | `proofs.sh c11` -> `PASS c11`. Independently, `gh run view 36957067839`: event `pull_request`, conclusion `success`, both jobs `success`, head `7f7dc07` | `proofs.sh:107` `--status success` filter; `proofs.sh:129` - `[ "$(job_conclusions "$run")" = "api=success web=success" ]` | PASS |
| C12 | the latest run on `ci/spec-04-proof`, whose head adds a `.tsx` type error, has conclusion `failure`, and its `web` step `npm run typecheck` failed | `proofs.sh c12` -> `PASS c12`. Independently: run `36957188351` failed; the only failed step is `web` / `Run npm run typecheck`; `api` passed. Head `0ef5f56` adds `frontend/app/zz-type-error.tsx` with `export const n: number = "not a number";`. `gh pr checks 1` shows `web fail`, `api pass` | `proofs.sh:136` conclusion `= failure`; `proofs.sh:138` `grep -qE '^frontend/.*\.tsx$'` over head-commit files; `proofs.sh:140-141` the typecheck step's conclusion `= failure` | PASS |
| C13 | no `secrets.` in the workflow, and the Postgres user, password and database are headroom, localdev, headroom, matching docker-compose | `proofs.sh c13` -> `PASS c13` | `proofs.sh:146` `grep -n 'secrets\.'` must find nothing; `proofs.sh:148` equality `'["headroom", "localdev", "headroom"]'` (reads `ci.yml:44-46`); `proofs.sh:150-151` read `docker-compose.yml:11-13` | PASS |
| C14 | protection on development and main requires exactly `api` and `web`, with `enforce_admins` false | `proofs.sh c14` -> `PASS c14`. Independently, both branches report contexts `["web","api"]` pinned to app 15368, `strict:false`, `enforce_admins:false`, and no rulesets | `proofs.sh:158` `= "api web"`; `proofs.sh:160` `= false` | PASS |
| C15 | while its latest run is red, PR #1 into development reports `BLOCKED` | First read printed `FAIL c15: pull request is 'OPEN development UNKNOWN'`; the rerun printed `PASS c15`. Independently, `gh pr view 1` reports `OPEN`, base `development`, `mergeable: MERGEABLE`, `mergeStateStatus: BLOCKED`. Protection requires no reviews, signatures, linear history or conversation resolution, so the failed required `web` check is the only thing blocking | `proofs.sh:169` - `[ "$state" = "OPEN development BLOCKED" ]` | PASS |
| C16 | `vulnerability-alerts` answers 204 | `proofs.sh c16` -> `PASS c16`. Independently: `HTTP/2.0 204 No Content` | `proofs.sh:175` - `grep -q ' 204'` | PASS |
| C17 | the push CI run for the last feature commit on development succeeded, with both jobs `success` | after `gh run watch 36957308625 --exit-status` exited 0: `proofs.sh c17` -> `PASS c17`. Independently, run `36957308625` is event `push`, head `1e25913` (= HEAD), conclusion `success`, both jobs `success`, api `16 passed` | `proofs.sh:180-181` resolve the run by `origin/development` SHA; `proofs.sh:184` conclusion `= success`; `proofs.sh:185` `= "api=success web=success"` | PASS |

Note on C15: GitHub computes `mergeStateStatus` lazily, so the first query after the `development` push answered `UNKNOWN`. A second query a moment later answered `BLOCKED`. The claim holds, but the proof is time-sensitive on its first read. This is recorded as a gap below and does not change any verdict.

## Level and sampling judgment

- C1 to C6 run the real npm scripts at the command boundary, which is the level the claims are stated at. C3's jsdom claim is settled by reading the config (`vitest.config.mts:8`), not by observing the environment at runtime. That is acceptable, because the claim names the configured environment.
- C2 proves AC 2 ("a `.ts` or `.tsx` file") on one `.tsx` file only. tsc's coverage of `.ts` files depends on `tsconfig.json` `include`, which no proof asserts. This is a precision gap in the checks, not in the code: checks.md:89 states one case per check.
- C10's "no skipped" grep is close to vacuous: `services/core/tests` has no skip markers (`grep -rn -i skip` found nothing). The claim is still reached, because `test_migrations.py:32-33,57` connect to `DATABASE_URL`, and the run is green with `16 passed`. If the database were unreachable, those tests would error rather than skip.
- C11 sampled head `7f7dc07`, an empty commit on top of `dd0c7fc`. Its code is identical to HEAD apart from the docs-only commit `1e25913`. C17 covers HEAD itself.
- C7 to C9 and C13 read the parsed YAML, and C11, C12 and C17 show that GitHub actually ran that YAML. That is the right pair of levels for workflow claims.
- C14 proves protection on `main` through its settings only. checks.md:88 discloses this, and it matches the plan (no release PR is opened).

## Coverage

Not recomputed: profile `light`, so the Coverage recompute does not run.

## Test policy rows

Not judged: profile `light`, and checks.md carries no Test policy section.

## Faults injected

None: profile `light`, so fault injection does not run.

## Swept existing

- validation (C2, C12): re-read and confirmed. The local tsc error and the CI step failure were both observed.
- failure modes and observability (C12): each command is its own step (`ci.yml:28-32,61-65`). The failed step reported by GitHub is `Run npm run typecheck`. Confirmed.
- authorization (C13, C14): no `secrets.` in `ci.yml`, and `permissions: contents: read` at `ci.yml:12-13`. Protection is read back from GitHub. Confirmed.
- state transitions (C11, C12, C15): the same PR went green (`36957067839`), then red (`36957188351`), and is `BLOCKED`. Confirmed.
- The `n/a` rows (idempotency, concurrency, data lifecycle, dependency failure) are approved policy, so there is nothing to check in the code. Concurrency's "strict mode is off" was still confirmed (`strict:false` on both branches).

## Gaps (non-blocking)

1. C15 is time-sensitive: the first `gh pr view` after a base-branch push answers `UNKNOWN` until GitHub computes merge state. A retry settles it. Location: `.specs/features/04-setup-tests-and-ci/proofs.sh:169`.
2. Precision gap (C2 / AC 2): only a `.tsx` error is exercised. No check pins `.ts` coverage through `tsconfig.json` `include`. Location: `proofs.sh:40`.
3. C10's `skipped` assertion is weak, because the suite has no skip markers. Database reachability is actually shown by the green migration tests (`services/core/tests/test_migrations.py:32`). Location: `proofs.sh:120`.

## Gate

`bash .specs/features/04-setup-tests-and-ci/proofs.sh c1 ... c17` (the batch, the c15/c16 rerun, then c17): 17 passed, 0 failed at HEAD `1e25913`. C15 failed once on a transient `UNKNOWN` and passed on the rerun, as noted above.

Working tree `git status --porcelain`: before `?? .specs/features/05-setup-railway-staging/`. After (once this report is written) the same, plus `?? .specs/features/04-setup-tests-and-ci/verification.md`, plus ` M context/specs/05-setup-railway-staging.md`. That last change is spec 05's status line going from `Not started` to `In progress`. It was not made by this Verifier: none of my commands touch that file. It looks like concurrent spec 05 work, and it is unrelated to this feature.
