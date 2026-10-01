# 01 - Frontend scaffold checks

Profile: light
Plan: `.specs/features/01-setup-frontend/plan.md`

12 checks in 3 slices · 2 one-way doors · 0 open, of which 0 block

Proofs are named functions in `.specs/features/01-setup-frontend/proofs.sh`; there is no test
runner until spec 04. Each exits non-zero on failure and prints `PASS cN` on success.

## Checks

### S1 - The app runs and builds · generated files only · ~5k

**C1** - `npm run build` in `frontend/` exits 0 after both generators (AC 1)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c1`

**C2** - With `npm run dev` running, `GET http://localhost:3123/` returns `200` and a body containing `To get started, edit the` (AC 2)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c2`

**C3** - `npm run lint` in `frontend/` exits 0 (AC 3)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c3`

**C4** - `frontend/app/layout.tsx` and `frontend/package-lock.json` exist, `frontend/tsconfig.json` has `compilerOptions.strict` `true`, and `frontend/src` does not exist (AC 4)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c4`

**C5** - `frontend/package.json` `dependencies.next` is exactly `16.3.8` (AC 5, door 1)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c5`

### S2 - shadcn/ui is initialized · generated files only · ~2k

**C6** - `frontend/components.json` has `rsc` `true`, `tsx` `true`, `tailwind.cssVariables` `true`, `style` `radix-nova`, and `frontend/package.json` depends on `radix-ui` (AC 6, door 2)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c6`

**C7** - `frontend/lib/utils.ts` exports `cn` and `frontend/package.json` depends on `cn` (AC 7; revised with user approval 2026-10-01 - shadcn 4.21.1 generates `export { cn } from "cn"`, not `export function cn(`)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c7`

### S3 - Generated output stays unedited · 2 hand-edited files · ~1k

**C8** - The first line of `frontend/AGENTS.md` is exactly ``Also follow the root `AGENTS.md` and `context/DESIGN.md`.`` (AC 8)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c8`

**C9** - The `nextjs-agent-rules` block of `frontend/AGENTS.md` at `HEAD` equals the block in the commit whose subject contains `initialize shadcn/ui` (AC 9)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c9`

**C10** - `git diff --name-only <commit 'initialize shadcn/ui'> HEAD -- frontend` lists exactly `frontend/AGENTS.md` (AC 10)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c10`

**C11** - `git ls-files 'frontend/.env*'` is empty and `git check-ignore frontend/.env.local` matches (AC 11)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c11`

**C12** - `git check-ignore` matches `services/core/.env.local` and does not match `services/core/.env.example` (AC 12)
Proof: `bash .specs/features/01-setup-frontend/proofs.sh c12`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| Landing doors (2) | door 1 Next.js shape C5 · door 2 shadcn base C6 | - |
| generated npm scripts used (3) | `dev` C2 · `build` C1 · `lint` C3 | - |
| project shape (4) | `app/layout.tsx` C4 · `package-lock.json` C4 · `strict` C4 · no `src/` C4 | - |
| `components.json` fields claimed (4) | `rsc` C6 · `tsx` C6 · `cssVariables` C6 · `style` C6 | - |
| `frontend/AGENTS.md` parts (2) | added first line C8 · generated rules block C9 | - |
| env-file ignore (4) | `frontend/.env*` untracked C11 · `frontend/.env.local` ignored C11 · `services/core/.env.local` ignored C12 · `services/core/.env.example` kept C12 | - |
| Surface routes (0) | n/a - plan Surface is None | - |

- No check names a status code except C2, whose proof crosses the HTTP boundary with a real request
- No other check claims more than the single case its proof exercises

## Swept

- validation: n/a - no input is accepted; scaffold only
- failure modes: C1, C3 - build and lint exit codes
- idempotency: n/a - generators run once; re-running is not a supported path in this spec
- authorization: n/a - no route or data exists yet; Clerk arrives in spec 10
- concurrency: n/a - no runtime behaviour beyond the starter page
- data lifecycle: C11, C12 - env files never enter git
- dependency failure: C5, C6 - generator versions pinned so a registry change cannot alter the shape
- state transitions: n/a - no state
- observability: n/a - logging and Sentry arrive in spec 08

## Handoff

- S1-S3 = ~8k (generator output is not read, only probed by the proofs; 3 small hand-edited files), under the 150k budget - one builder
