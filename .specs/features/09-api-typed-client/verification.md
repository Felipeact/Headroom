# 09 - Typed API client verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 63eab27..133fc5e
**Round**: 4 - scoped
**Verifier**: independent sub-agent (author != verifier)

This round is scoped to the diff `7cd50c4..133fc5e`, which covers commits `09c9ec0`, `9fcaf8e` and `133fc5e`. Round 3 left no verdict below PASS. The code changes in that diff are:

- **`frontend/lib/api/client.ts`.** The Proxy now returns a function only for `GET`, `PUT`, `POST`, `DELETE`, `OPTIONS`, `HEAD`, `PATCH` and `TRACE`. Every other property is `undefined` (`:20`). The type is `Pick<Client<paths>, ...>` (`:5-6`).
- **`frontend/tests/api-client.test.ts`.** New test `exposes only the HTTP methods`.
- **`frontend/lib/api/client.type-test.ts`.** New third `@ts-expect-error`, on `api.use({})` (`:14-15`).
- **`services/core/tests/test_export_openapi.py`.** New autouse fixture `restore_contract` (`:16-21`).

The rest of the diff is documentation and state: `.specs/*`, `plan.md` (doors 6 and AD-019), the spec status and token usage. `proofs.sh`, `ci.yml`, `.gitattributes`, the page and the e2e spec are untouched. All proofs re-ran in full at `133fc5e`.

## Steps not run under `light` - carried from 7cd50c4

- Binding sources (step 1): not run. It applies to `ui` only, and the diff touched no screen.
- Coverage recompute: not run. It applies to `standard` and `ui` only.
- Fault injection: not run. It applies to `standard` and `ui` only.
- Test policy: `checks.md` has no `Test policy` section.

## Proof runs - verified at 133fc5e

- **pytest** (`services/core`): `uv run pytest tests/test_export_openapi.py -v`, run without `DATABASE_URL`. 3 passed, each listed as PASSED: `test_writes_contract_from_any_cwd`, `test_output_is_deterministic`, `test_contract_has_healthz_paths`. The md5 of `contracts/openapi.json` was `cb052d96…` before and after the run, so the fixture restored the bytes.
- **vitest** (`frontend`): `npx vitest run tests/api-client.test.ts tests/api-check-page.test.tsx tests/dev-gate.test.ts --reporter=verbose`. 10 passed, each listed, including:
  - `sends to API_URL`
  - `API_URL unset: import works, the call rejects without fetching`
  - `exposes only the HTTP methods`
  - `connection refused shows API unreachable without a status`
  - `non-2xx shows API unreachable and the HTTP status`
  - `C14 api check: production calls notFound and makes no request`
- **Playwright** (`frontend`): `npx playwright test e2e/api-check.spec.ts --reporter=list`. 3 passed: `live status`, `live status over http`, `a11y and 375`. Ports 3000 and 8100 were free beforehand.
- **`bash proofs.sh c4 c5 c9 c10 c11 c19`**: all PASS, exit 0. The c9 output included `Error: You're importing a module that depends on "server-only". ...`. `git status --porcelain` was empty afterwards.
- **`C16_SHA=ac83ef0… C17_SHA=7cdae40… C18_SHA=fc0a97b… bash proofs.sh c16 c17 c18`**: `PASS c16`, `PASS c17`, `PASS c18`, exit 0.
- **`npm run typecheck`**: exit 0. All three `@ts-expect-error` lines in `client.type-test.ts` are therefore live errors.

### Re-judged against the changed code - verified at 133fc5e

- **C7 still holds.** `api.GET` is in `METHODS`, so the Proxy still builds `createClient<paths>({ baseUrl })` per call and forwards it. The test's assertions at `api-client.test.ts:30,32,33` are unchanged and pass.
- **C8 still holds.** The `API_URL` guard (`client.ts:23`, `Promise.reject(new Error("API_URL is not set"))`) sits inside the function returned for allowed methods, so `GET` still rejects without fetching (`api-client.test.ts:44-45`). Import still does not throw (`:42`).
  - One new property of the client: reading `api.then` now returns `undefined`. Before this change it returned a function. `await import(...)` and `Promise.resolve(api)` no longer treat `api` as a thenable (`api-client.test.ts:56`).
- **C10 still holds.** The two claimed `@ts-expect-error` lines remain at `client.type-test.ts:5-6` and `:10-11`. The third, at `:14-15` on `api.use({})`, is extra coverage the claim does not require. Typecheck exits 0 and `proofs.sh c10` passes.
- **C1-C3 with the fixture.** The fixture reads the contract bytes before each test and writes them back after the `yield` (`test_export_openapi.py:19-21`). C1's assertions (`:40-42`) and C2's (`:51-54`) run before teardown, so they still observe the export's output.
  - C3 (`:60-61`) has no export of its own. It now reads exactly the bytes present at test start, which is the committed file on a clean tree, so it now asserts the claim ("the committed contract") more faithfully than before.
  - Round 1 gap 4 (tests leave the tracked contract rewritten) is closed at the source: the md5 was unchanged and the tree stayed clean.

## Checks

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | export from a temp cwd without `DATABASE_URL` exits 0 and writes `<root>/contracts/openapi.json` equal to `app.openapi()` | verified at 133fc5e: `pytest ... -v`, `test_writes_contract_from_any_cwd` PASSED | `services/core/tests/test_export_openapi.py:40` - `assert result.returncode == 0`; `:41` - `assert list(tmp_path.iterdir()) == []`; `:42` - `json.loads(CONTRACT.read_text(...)) == app.openapi()` (see precision note in Findings) | PASS |
| C2 | two runs are byte-identical, end with exactly one `\n`, contain no `\r` | verified at 133fc5e: `test_output_is_deterministic` PASSED | `test_export_openapi.py:51` - `assert first == second`; `:52-53` - `first.endswith(b"\n")`, `not first.endswith(b"\n\n")`; `:54` - `assert b"\r" not in first` | PASS |
| C3 | the committed contract has `/healthz/live` and `/healthz/ready` | verified at 133fc5e: `test_contract_has_healthz_paths` PASSED | `test_export_openapi.py:60-61` - `"/healthz/live" in paths`, `"/healthz/ready" in paths`; reads the restored committed bytes (fixture `:19-21`) | PASS |
| C4 | `npm run api:types` exits 0; `schema.d.ts` has `export interface paths` with `"/healthz/live"` | verified at 133fc5e: `proofs.sh c4` -> `PASS c4` | `proofs.sh:18-20` - `npm run api:types` checked with `fail` on error, plus `grep -q '^export interface paths'` and `grep -q '"/healthz/live"'`; present at `frontend/lib/api/schema.d.ts:6-7` | PASS |
| C5 | after both commands at HEAD, `git status --porcelain -- <both files>` prints nothing | verified at 133fc5e: `proofs.sh c5` -> `PASS c5` (fresh-clone check under `core.autocrlf=true` carried from ec9699a; `.gitattributes` untouched since) | `proofs.sh:28-29` - `[ -z "$dirty" ]`; `.gitattributes:3-4` - `text eol=lf` for both files | PASS |
| C6 | through the client, the live API gives `status: ok` and `HTTP 200` on `/dev/api-check` | verified at 133fc5e: playwright `live status over http` passed | `frontend/e2e/api-check.spec.ts:18` - `getByText('status: ok', { exact: true })` visible; `:19` - `getByText('HTTP 200', { exact: true })` visible (real HTTP to uvicorn on 8100, through the new method-only Proxy) | PASS |
| C7 | with `API_URL=http://api.test:9999` and a fake fetch, exactly one GET to `http://api.test:9999/healthz/live` | verified at 133fc5e: vitest `sends to API_URL` passed | `frontend/tests/api-client.test.ts:30` - `toHaveBeenCalledTimes(1)`; `:32` - `expect(request.url).toBe('http://api.test:9999/healthz/live')`; `:33` - `expect(request.method).toBe('GET')` | PASS |
| C8 | `API_URL` unset: import does not throw, the call rejects with `API_URL is not set`, and fetch is never called | verified at 133fc5e: vitest `API_URL unset: import works, the call rejects without fetching` passed | `api-client.test.ts:42` - `await import('@/lib/api/client')`; `:44` - `rejects.toThrow(new Error('API_URL is not set'))`; `:45` - `expect(fakeFetch).not.toHaveBeenCalled()`; guard at `client.ts:23` | PASS |
| C9 | a `"use client"` scratch import makes `npm run build` fail; the build passes again without it | verified at 133fc5e: `proofs.sh c9` -> `PASS c9`, printing the `server-only` error line; tree clean afterwards | `proofs.sh:51` - build must exit non-zero; `:52` - `grep -q 'server-only' <<<"$out"`; `:55` - the rebuild without the scratch must succeed | PASS |
| C10 | `@ts-expect-error` on `/healthz/nope` and on `data.missing`; typecheck exits 0 | verified at 133fc5e: `npm run typecheck` exit 0; `proofs.sh c10` -> `PASS c10` | `frontend/lib/api/client.type-test.ts:5-6` and `:10-11` - `// @ts-expect-error` over `api.GET("/healthz/nope")` and `void data.missing` (plus `:14-15` over `api.use({})`); `proofs.sh:61-62` greps both claimed lines | PASS |
| C11 | after building with the sentinel `API_URL`, `.next/static` contains neither `API_URL` nor `api-sentinel.invalid` | verified at 133fc5e: `proofs.sh c11` -> `PASS c11` | `proofs.sh:68-69` - build with `API_URL=http://api-sentinel.invalid:8000`, then a recursive `grep -rlE` over `$FE/.next/static` for the alternation of `API_URL` and `api-sentinel\.invalid` must find nothing, else `fail c11` | PASS |
| C12 | in dev, `/dev/api-check` answers 200 with an h1 `API check` and the text `status: ok` | verified at 133fc5e: playwright `live status` passed | `e2e/api-check.spec.ts:10` - `expect(response?.status()).toBe(200)`; `:11` - `getByRole('heading', { level: 1, name: 'API check' })`; `:12` - `getByText('status: ok', { exact: true })` | PASS |
| C13 | rejected call: `API unreachable` and no status number; 503 response: `API unreachable` and `HTTP 503`; neither throws | verified at 133fc5e: vitest `connection refused ...` and `non-2xx ...` passed (unit level, client mocked) | `frontend/tests/api-check-page.test.tsx:22-23` - `getByText('API unreachable')`, `queryByText(/\d{3}/)` is null; `:34-35` - `getByText('API unreachable')`, `getByText('HTTP 503')` | PASS |
| C14 | with `NODE_ENV=production`: digest `NEXT_HTTP_ERROR_FALLBACK;404` and `GET` called 0 times | verified at 133fc5e: vitest `C14 api check: ...` passed | `frontend/tests/dev-gate.test.ts:50` - `digest).toBe('NEXT_HTTP_ERROR_FALLBACK;404')`; `:51` - `expect(api.GET).toHaveBeenCalledTimes(0)` | PASS |
| C15 | 0 axe violations; scrollWidth at most 375; Tab is not trapped (focus reaches body or returns to the first element) | verified at 133fc5e: playwright `a11y and 375` passed | `e2e/api-check.spec.ts:28` - `expect(results.violations).toEqual([])`; `:31` - `toBeLessThanOrEqual(375)`; `:42` - `expect(reachesBody OR returnsToFirst).toBe(true)` (logical or; written out because the gate splits table cells on the pipe character) | PASS |
| C16 | scratch PR: endpoint changed without regenerating -> `api` fails at the drift step | verified at 133fc5e: `proofs.sh c16` -> `PASS c16` (run 37061443177) | `proofs.sh:109` - `[ "$(job_conclusion "$jobs" api)" = "failure" ]`; `:110` - `failed_step api = "Check the OpenAPI contract is current"`; scratch `ac83ef0` changes only `services/core/app/main.py` | PASS |
| C17 | after regenerating only `openapi.json`: `web` fails at the types drift step, `api` succeeds | verified at 133fc5e: `proofs.sh c17` -> `PASS c17` (run 37061470745) | `proofs.sh:118` - `web = failure`; `:119` - `failed_step web = "Check generated API types are current"`; `:121` - `api = success`; scratch `7cdae40` changes only `contracts/openapi.json` | PASS |
| C18 | the pushed feature commit's CI has jobs exactly `web` and `api`, both `success` | verified at 133fc5e: `proofs.sh c18` -> `PASS c18` (run 37061421248, push on `development` at `fc0a97b`) | `proofs.sh:128` - `[ "$(job_names "$jobs")" = "api,web" ]`; `:129-130` - `web = success`, `api = success`. Note: the claim names the CI run for `fc0a97b`; I did not check CI for `9fcaf8e`/`133fc5e` | PASS |
| C19 | `.env.example` has `API_URL=http://localhost:8000`; no tracked `frontend/` file contains `NEXT_PUBLIC_API_URL` | verified at 133fc5e: `proofs.sh c19` -> `PASS c19` | `proofs.sh:76` - `grep -qx 'API_URL=http://localhost:8000'` (present at `frontend/.env.example:13`); `:77` - `git ls-files -z frontend` piped to `xargs -0 grep -l 'NEXT_PUBLIC_API_URL'` must find nothing | PASS |

## Level and sampling - verified at 133fc5e for C7, C8 and C10; carried from 7cd50c4 for the rest

- **C7, C8:** unit proofs of the client, unchanged in level. The new method allowlist sits on the same code path the tests exercise.
- **C10:** proved at type-check level.
- **C6, C12:** cross HTTP through the changed client.
- **C16-C18:** proved at the GitHub Actions level.
- **C13:** a unit proof of the page's branch.

## Swept re-read - verified at 133fc5e for the rows the diff touches; carried from 7cd50c4 for the rest

| Row | Cited constraint | Present in code |
| --- | --- | --- |
| validation | C10 | yes - `client.type-test.ts:5,10`, plus `:14` for `use` |
| failure modes | C8, C13 | yes - `client.ts:23`, `page.tsx:7-14` |
| idempotency | C2 | yes - `export_openapi.py:18-20`, `.gitattributes:3-4`; the tests now leave the contract bytes unchanged (fixture `:19-21`) |
| authorization | C14, C9, C11 | yes - `page.tsx:20` `notFound()`; `client.ts:1` `import "server-only"` |
| dependency failure | C13 | yes |
| observability | C16, C17 | yes - `ci.yml:33,75` `git diff --exit-code` |
| concurrency, data lifecycle, state transitions | n/a | approved policy |

## Findings

None blocking.

1. **Precision note on C1 (pre-existing, found this round).** `test_export_openapi.py:42` reads the contract after the export. A committed contract that is already current satisfies it even if the export wrote somewhere else, so the test alone does not prove the "writes `<root>/contracts/openapi.json`" half of the claim. CI proves that half: in C16 the `api` drift step went red after the export rewrote the root file, and in C17 it went green. A sharper unit proof is cheap now that the fixture restores the bytes: delete or truncate `CONTRACT` before `run_export`, then assert it was recreated.
2. **Residual wording on C15** (carried from ec9699a). The phrase "returns to the first element" would also accept a focus trap between two elements. The assertion matches the check exactly.

## Gate

`python3 .claude/skills/tlc-spec-lean/scripts/validate_verification.py 09-api-typed-client` - exit 0, 0 errors, 0 warnings.

Proofs at 133fc5e:

- pytest 3, vitest 10 and Playwright 3, all passed.
- `proofs.sh` passed all 9 checks it covers: c4, c5, c9, c10, c11, c16, c17, c18, c19.
- `npm run typecheck` exited 0.
