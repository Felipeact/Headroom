# 09 - Typed API client verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 63eab27..7cd50c4
**Round**: 3 - scoped
**Verifier**: independent sub-agent (author != verifier)

This round is scoped to the fix commit `7cd50c4` (diff `ec9699a..7cd50c4`) plus every verdict from round 2 that was not PASS (C16, C17, C18).

The fix touches only `.specs/features/09-api-typed-client/proofs.sh`. The three `tr -d` arguments (`:90`, `:92`, `:101`) are now the escape `'\r'` on a single line.

A byte scan of the file finds **0 raw CR bytes** and 3 occurrences of `tr -d '\r'`. `git ls-files --eol` reports `i/lf w/lf`.

All proofs re-ran in full at `7cd50c4`, per the brief.

## Steps not run under `light` - carried from ec9699a

- Binding sources (step 1): not run - `ui` only. The fix touched no screen.
- Coverage recompute: not run - `standard`/`ui` only.
- Fault injection: not run - `standard`/`ui` only.
- Test policy: `checks.md` has no `Test policy` section.

## Proof runs - verified at 7cd50c4

- `services/core`: `uv run pytest tests/test_export_openapi.py -v` (no `DATABASE_URL`) - 3 passed, each listed as PASSED: `test_writes_contract_from_any_cwd`, `test_output_is_deterministic`, `test_contract_has_healthz_paths`.
- `frontend`: `npx vitest run tests/api-client.test.ts tests/api-check-page.test.tsx tests/dev-gate.test.ts --reporter=verbose` - 9 passed, each listed by name, including:
  - `sends to API_URL`
  - `API_URL unset: import works, the call rejects without fetching`
  - `connection refused shows API unreachable without a status`
  - `non-2xx shows API unreachable and the HTTP status`
  - `C14 api check: production calls notFound and makes no request`
- `frontend`: `npx playwright test e2e/api-check.spec.ts --reporter=list` - 3 passed: `live status`, `live status over http`, `a11y and 375`. Ports 3000 and 8100 were free beforehand.
- `bash proofs.sh c4 c5 c9 c10 c11 c19` - `PASS` for each check, exit 0.
  - c9 printed `Error: You're importing a module that depends on "server-only". ...`.
  - Afterwards `git status --porcelain` showed only this untracked report.
- `C16_SHA=ac83ef0… C17_SHA=7cdae40… C18_SHA=fc0a97b… bash proofs.sh c16 c17 c18` - `PASS c16`, `PASS c17`, `PASS c18`, exit 0.
  - The runs it read are unchanged since round 1:
    - 37061443177: `api` failure at "Check the OpenAPI contract is current", `web` success.
    - 37061470745: `web` failure at "Check generated API types are current", `api` success.
    - 37061421248: push on `development`, both jobs success.
- `npm run typecheck` (frontend) - exit 0.

### Earlier gaps - status at 7cd50c4

- **Round 2 gap (C16-C18 `tr -d` regression): closed.**
  - The escape `'\r'` strips the CR that Windows Python emits.
  - All three proofs pass as committed.
- **Round 1 gap 1 (C5): closed in round 2, still green.**
  - `proofs.sh c5` passes at 7cd50c4.
  - The fresh-clone confirmation is carried from ec9699a. This diff does not touch `.gitattributes` or the generators.
- **Round 1 gaps 2-4: closed in round 2, carried from ec9699a.**
  - This diff touches neither `e2e/api-check.spec.ts` nor `proofs.sh` c9.
  - The proofs for those checks re-ran green here.

## Checks

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | export from a temp cwd without `DATABASE_URL` exits 0 and writes `<root>/contracts/openapi.json` equal to `app.openapi()` | verified at 7cd50c4: `pytest ... -v`, `test_writes_contract_from_any_cwd` PASSED | `services/core/tests/test_export_openapi.py:29` - `assert result.returncode == 0`; `:30` - `assert list(tmp_path.iterdir()) == []`; `:31` - `json.loads(CONTRACT.read_text(...)) == app.openapi()` | PASS |
| C2 | two runs are byte-identical, end with exactly one `\n`, contain no `\r` | verified at 7cd50c4: `test_output_is_deterministic` PASSED | `test_export_openapi.py:40` - `assert first == second`; `:41-42` - `first.endswith(b"\n")`, `not first.endswith(b"\n\n")`; `:43` - `assert b"\r" not in first` | PASS |
| C3 | the committed contract has `/healthz/live` and `/healthz/ready` | verified at 7cd50c4: `test_contract_has_healthz_paths` PASSED | `test_export_openapi.py:49-50` - `"/healthz/live" in paths`, `"/healthz/ready" in paths` | PASS |
| C4 | `npm run api:types` exits 0; `schema.d.ts` has `export interface paths` with `"/healthz/live"` | verified at 7cd50c4: `proofs.sh c4` -> `PASS c4` | `proofs.sh:18-20` - `npm run api:types` checked with `fail` on error, then `grep -q '^export interface paths'` and `grep -q '"/healthz/live"'`; present at `frontend/lib/api/schema.d.ts:6-7` | PASS |
| C5 | after both commands at HEAD, `git status --porcelain -- <both files>` prints nothing | verified at 7cd50c4: `proofs.sh c5` -> `PASS c5` (fresh-clone check under `core.autocrlf=true` carried from ec9699a) | `proofs.sh:28-29` - `[ -z "$dirty" ]`; `.gitattributes:3-4` - `contracts/openapi.json text eol=lf`, `frontend/lib/api/schema.d.ts text eol=lf` | PASS |
| C6 | through the client, the live API gives `status: ok` and `HTTP 200` on `/dev/api-check` | verified at 7cd50c4: playwright `live status over http` passed | `frontend/e2e/api-check.spec.ts:18` - `getByText('status: ok', { exact: true })` visible; `:19` - `getByText('HTTP 200', { exact: true })` visible (real HTTP to uvicorn on 8100) | PASS |
| C7 | with `API_URL=http://api.test:9999` and a fake fetch, exactly one GET to `http://api.test:9999/healthz/live` | verified at 7cd50c4: vitest `sends to API_URL` passed | `frontend/tests/api-client.test.ts:30` - `toHaveBeenCalledTimes(1)`; `:32` - `expect(request.url).toBe('http://api.test:9999/healthz/live')`; `:33` - `expect(request.method).toBe('GET')` | PASS |
| C8 | `API_URL` unset: import does not throw, the call rejects with `API_URL is not set`, and fetch is never called | verified at 7cd50c4: vitest `API_URL unset: import works, the call rejects without fetching` passed | `api-client.test.ts:42` - `await import('@/lib/api/client')`; `:44` - `rejects.toThrow(new Error('API_URL is not set'))`; `:45` - `expect(fakeFetch).not.toHaveBeenCalled()` | PASS |
| C9 | a `"use client"` scratch import makes `npm run build` fail; the build passes again without it | verified at 7cd50c4: `proofs.sh c9` -> `PASS c9`, printing the `server-only` error line; tree clean afterwards | `proofs.sh:51` - the build must exit non-zero; `:52` - `grep -q 'server-only' <<<"$out"`; `:55` - the rebuild without the scratch must succeed | PASS |
| C10 | `@ts-expect-error` on `/healthz/nope` and on `data.missing`; typecheck exits 0 | verified at 7cd50c4: `npm run typecheck` exit 0; `proofs.sh c10` -> `PASS c10` | `frontend/lib/api/client.type-test.ts:5-6` and `:10-11` - `// @ts-expect-error` over `api.GET("/healthz/nope")` and over `void data.missing`; `proofs.sh:61-62` greps both | PASS |
| C11 | after building with the sentinel `API_URL`, `.next/static` contains neither `API_URL` nor `api-sentinel.invalid` | verified at 7cd50c4: `proofs.sh c11` -> `PASS c11` | `proofs.sh:68-69` - build with `API_URL=http://api-sentinel.invalid:8000`, then a recursive `grep -rlE` over `$FE/.next/static` for the alternation of `API_URL` and `api-sentinel\.invalid` must find nothing, else `fail c11` | PASS |
| C12 | in dev, `/dev/api-check` answers 200 with an h1 `API check` and the text `status: ok` | verified at 7cd50c4: playwright `live status` passed | `e2e/api-check.spec.ts:10` - `expect(response?.status()).toBe(200)`; `:11` - `getByRole('heading', { level: 1, name: 'API check' })`; `:12` - `getByText('status: ok', { exact: true })` | PASS |
| C13 | rejected call: `API unreachable` and no status number; 503 response: `API unreachable` and `HTTP 503`; neither throws | verified at 7cd50c4: vitest `connection refused ...` and `non-2xx ...` passed (unit level, client mocked) | `frontend/tests/api-check-page.test.tsx:22-23` - `getByText('API unreachable')`, `queryByText(/\d{3}/)` is null; `:34-35` - `getByText('API unreachable')`, `getByText('HTTP 503')` | PASS |
| C14 | with `NODE_ENV=production`, digest `NEXT_HTTP_ERROR_FALLBACK;404` and `GET` called 0 times | verified at 7cd50c4: vitest `C14 api check: ...` passed | `frontend/tests/dev-gate.test.ts:50` - `digest).toBe('NEXT_HTTP_ERROR_FALLBACK;404')`; `:51` - `expect(api.GET).toHaveBeenCalledTimes(0)` | PASS |
| C15 | 0 axe violations; scrollWidth at most 375; Tab is not trapped (focus reaches body or returns to the first element) | verified at 7cd50c4: playwright `a11y and 375` passed | `e2e/api-check.spec.ts:28` - `expect(results.violations).toEqual([])`; `:31` - `toBeLessThanOrEqual(375)`; `:42` - `expect(reachesBody OR returnsToFirst).toBe(true)` (logical or; written out because the gate splits table cells on the pipe character) | PASS |
| C16 | on the scratch PR, an endpoint change without regenerating makes `api` fail at the drift step | verified at 7cd50c4: `proofs.sh c16` -> `PASS c16` (run 37061443177) | `proofs.sh:109` - `[ "$(job_conclusion "$jobs" api)" = "failure" ]`; `:110` - `failed_step api = "Check the OpenAPI contract is current"`; scratch commit `ac83ef0` changes only `services/core/app/main.py` (round 1) | PASS |
| C17 | after regenerating only `openapi.json`, `web` fails at the types drift step and `api` succeeds | verified at 7cd50c4: `proofs.sh c17` -> `PASS c17` (run 37061470745) | `proofs.sh:118` - `web = failure`; `:119` - `failed_step web = "Check generated API types are current"`; `:121` - `api = success`; scratch commit `7cdae40` changes only `contracts/openapi.json` (round 1) | PASS |
| C18 | the pushed feature commit's CI has jobs named exactly `web` and `api`, both `success` | verified at 7cd50c4: `proofs.sh c18` -> `PASS c18` (run 37061421248, push on `development` at `fc0a97b`) | `proofs.sh:128` - `[ "$(job_names "$jobs")" = "api,web" ]`; `:129-130` - `web = success`, `api = success`. Later commits change no code CI runs (only `.gitattributes`, specs, the proof script and one e2e assertion; CI does not run e2e) | PASS |
| C19 | `.env.example` has `API_URL=http://localhost:8000`; no tracked `frontend/` file contains `NEXT_PUBLIC_API_URL` | verified at 7cd50c4: `proofs.sh c19` -> `PASS c19` | `proofs.sh:76` - `grep -qx 'API_URL=http://localhost:8000'` (present at `frontend/.env.example:13`); `:77` - `git ls-files -z frontend` piped to `xargs -0 grep -l 'NEXT_PUBLIC_API_URL'` must find nothing | PASS |

## Level and sampling - carried from ec9699a

- C6 and C12 cross HTTP into the real API.
- C16-C18 are proved at the GitHub Actions level.
- C13 is a unit proof of the page's branch, as `checks.md` states.
- C7 and C8 are unit proofs of the client.
- This diff changes no proof's level.

## Swept re-read - carried from ec9699a

| Row | Cited constraint | Present in code |
| --- | --- | --- |
| validation | C10 | yes - `client.type-test.ts:5,10` |
| failure modes | C8, C13 | yes - `client.ts:19`, `page.tsx:7-14` |
| idempotency | C2: regeneration never produces a spurious diff | yes - `export_openapi.py:18-20`; `.gitattributes:3-4` |
| authorization | C14, C9, C11 | yes - `page.tsx:20` `notFound()`; `client.ts:1` `import "server-only"` |
| dependency failure | C13 | yes |
| observability | C16, C17: the drift step prints the diff | yes - `ci.yml:33,75` `git diff --exit-code` |
| concurrency, data lifecycle, state transitions | n/a | approved policy |

## Findings

None blocking. One residual note on the check wording, carried from ec9699a: C15's "returns to the first element" would also accept a focus trap between two elements. The assertion matches the check exactly.

## Gate

`python3 .claude/skills/tlc-spec-lean/scripts/validate_verification.py 09-api-typed-client` - exit 0, 0 errors, 0 warnings. The first run rejected three rows only because the gate splits table cells on an escaped pipe; I reworded the C11, C15 and C19 evidence cells without changing any result.

Proofs at 7cd50c4:

- 3 pytest, 9 vitest and 3 playwright tests passed.
- `proofs.sh`: 9 of 9 checks passed (c4, c5, c9, c10, c11, c16, c17, c18, c19).
- `npm run typecheck`: exit 0.
