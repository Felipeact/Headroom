# 09 - Typed API client checks

Profile: light
Plan: `.specs/features/09-api-typed-client/plan.md`

19 checks in 4 slices · 4 one-way doors · 1 open, of which 0 block (C16-C18 need the push go-ahead; it blocks go-live, not the build)

Commands run from `services/core/` (`uv run pytest ...`) or `frontend/` (`npx vitest run <file> -t "<name>"`, `npx playwright test <file> -g "<name>"`, `npm run ...`). `bash .specs/features/09-api-typed-client/proofs.sh <cNN>` runs from anywhere in the repo. Playwright starts `npm run dev` on port 3000 and the API on port 8100 (8000 is often taken), and reuses a server already on either port locally, so stop other servers first.

## Checks

### S1 - Generated contract and types · 5 files · 15 KB · ~4k

**C1** - `python -m app.export_openapi`, run with `PYTHONPATH=services/core`, a temporary directory as cwd, and no `DATABASE_URL` in the environment, exits `0` and writes `<repo root>/contracts/openapi.json` (not a file in the cwd), whose parsed JSON equals `app.main.app.openapi()` (AC 1, door 1)
Proof: `uv run pytest tests/test_export_openapi.py -k "writes_contract_from_any_cwd"`

**C2** - Two consecutive runs produce byte-identical files that end with exactly one `\n` and contain no `\r` (AC 2, door 1)
Proof: `uv run pytest tests/test_export_openapi.py -k "output_is_deterministic"`

**C3** - The committed `contracts/openapi.json` has the keys `/healthz/live` and `/healthz/ready` under `paths` (AC 3)
Proof: `uv run pytest tests/test_export_openapi.py -k "contract_has_healthz_paths"`

**C4** - `npm run api:types` exits `0`, and `lib/api/schema.d.ts` then contains `export interface paths` with the key `"/healthz/live"` (AC 4, door 2)
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c4`

**C5** - After running both commands at `HEAD`, `git status --porcelain -- contracts/openapi.json frontend/lib/api/schema.d.ts` prints nothing (AC 5)
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c5`

### S2 - Server-only typed client · 6 files · 12 KB · ~3k

**C6** - Through `lib/api/client.ts`, `GET /healthz/live` against the running API yields `data.status` `"ok"` and `response.status` `200`, shown on `/dev/api-check` as `status: ok` and `HTTP 200` (AC 6)
Proof: `npx playwright test e2e/api-check.spec.ts -g "live status over http"`

**C7** - With `API_URL=http://api.test:9999` and a fake `fetch`, `api.GET("/healthz/live")` makes exactly one request, to `http://api.test:9999/healthz/live` with method `GET` (AC 7, door 3)
Proof: `npx vitest run tests/api-client.test.ts -t "sends to API_URL"`

**C8** - With `API_URL` unset, importing `@/lib/api/client` does not throw, and `api.GET("/healthz/live")` rejects with an `Error` whose message is exactly `API_URL is not set`, without calling `fetch` (AC 8, door 3)
Proof: `npx vitest run tests/api-client.test.ts -t "API_URL unset"`

**C9** - A scratch page that renders a `"use client"` component importing `@/lib/api/client` makes `npm run build` exit non-zero; the build passes again once the scratch files are removed (AC 9, door 3)
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c9`

**C10** - `lib/api/client.type-test.ts` holds a `// @ts-expect-error` on `api.GET("/healthz/nope")` and one on reading `data.missing` from the `/healthz/live` result, and `npm run typecheck` exits `0` (an unused `@ts-expect-error` would fail it) (AC 10)
Proof: `npm run typecheck`
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c10`

**C11** - After `API_URL=http://api-sentinel.invalid:8000 npm run build`, no file under `.next/static` contains `API_URL` or `api-sentinel.invalid` (AC 11, door 3)
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c11`

### S3 - Test page shows the live result · 4 files · 10 KB · ~3k

**C12** - In development with the API running, `/dev/api-check` answers `200` and shows an `h1` reading `API check` and the text `status: ok` (AC 12)
Proof: `npx playwright test e2e/api-check.spec.ts -g "live status"`

**C13** - When the client rejects (connection refused), the rendered page shows `API unreachable` and no status number; when the client returns an error response with status `503`, it shows `API unreachable` and `HTTP 503`; neither case throws (AC 13)
Proof: `npx vitest run tests/api-check-page.test.tsx -t "connection refused"`
Proof: `npx vitest run tests/api-check-page.test.tsx -t "non-2xx"`

**C14** - With `NODE_ENV=production`, the page throws the `notFound()` digest `NEXT_HTTP_ERROR_FALLBACK;404` and the client's `GET` is called `0` times (AC 14, AD-014)
Proof: `npx vitest run tests/dev-gate.test.ts -t "C14 api check"`

**C15** - On `/dev/api-check`: axe reports `0` violations; at 375px wide `document.documentElement.scrollWidth` is at most `375`; pressing Tab from the page start moves focus through the page and back to `body` or the first element without being trapped (AC 15)
Proof: `npx playwright test e2e/api-check.spec.ts -g "a11y and 375"`

### S4 - CI fails on a stale contract · 1 file · 2 KB · ~1k

**C16** - On a scratch pull request into `development` whose head commit changes an endpoint in `services/core` without regenerating `contracts/openapi.json`, the `api` check concludes `failure` at the openapi drift step (AC 16, door 4)
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c16`

**C17** - On the same pull request, after a commit that regenerates `contracts/openapi.json` but not `frontend/lib/api/schema.d.ts`, the `web` check concludes `failure` at the types drift step and the `api` check concludes `success` (AC 17, door 4)
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c17`

**C18** - The CI run for the pushed feature commit on `development` has jobs named exactly `web` and `api`, both concluding `success` (AC 18, AD-004)
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c18`

**C19** - `frontend/.env.example` contains the line `API_URL=http://localhost:8000`, and no tracked file under `frontend/` contains `NEXT_PUBLIC_API_URL` (Impact: configuration, door 3)
Proof: `bash .specs/features/09-api-typed-client/proofs.sh c19`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| generated files (2) | `contracts/openapi.json` C1 C2 C3 C5 · `frontend/lib/api/schema.d.ts` C4 C5 | - |
| CI drift checks (2 jobs) | `api` C16 · `web` C17 | - |
| `/dev/api-check` outcomes (4) | ok C12 · rejected call C13 · non-2xx response C13 · production C14 | - |
| client misuse (3) | `API_URL` unset C8 · imported by client component C9 · address in browser bundle C11 | - |
| type rejections (2) | unknown path C10 · unknown response field C10 | - |
| startup config: `API_URL` (3 assemblies) | `next dev` under Playwright C6 C12 · Vitest C7 · `next build` C11 | - |
| one-way doors (4) | door 1 C1 C2 · door 2 C4 · door 3 C7 C8 C9 C11 C19 · door 4 C16 C17 | - |

- Claims naming a status code or response shape: C6 (200 through the real API), C13 (503) - C6 crosses the HTTP boundary to the running API; C13 is a unit proof of the page's branch, stated as such
- No other check claims more than the single case its proof exercises

## Swept

- validation: C10 - unknown paths and response fields are rejected at type-check time; no runtime input is accepted
- failure modes: C8 (missing `API_URL`), C13 (API down or answering an error)
- idempotency: C2 - the export run twice yields the same bytes, so regeneration never produces a spurious diff
- authorization: C14 (page 404s outside development), C9 and C11 (client and address never reach the browser). No login until spec 10
- concurrency: n/a - two developer commands writing one file each; CI jobs regenerate into their own checkout
- data lifecycle: n/a - no stored data
- dependency failure: C13 - the page survives the API being down
- state transitions: n/a - no state machine
- observability: C16, C17 - the drift step prints the diff before failing; the dev page has no logging requirement

## Handoff

- S1-S4 touch about 16 files, ~39 KB including both generated files (~10k tokens), plus reading `app/main.py`, `ci.yml`, `playwright.config.ts` and `package.json` (~3k); ~13k total, under the 150k budget - one builder

- **Boundary:** C1-C19 closed at `fc0a97b` (pushed). C16 at scratch `ac83ef0`, C17 at scratch `7cdae40` (PR #2, closed unmerged, branch deleted), C18 at `fc0a97b`
- **Settled mid-build:** the user approved pushing `development` and the scratch pull request for C16-C18
- **Abandoned:** Playwright's API on port 8000 - a system process (`Manager`) holds it on this machine, so the tests use 8100
