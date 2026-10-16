# 01 - Frontend scaffold verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 942d23c..HEAD
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

Verified at `b7b4c69`. In-scope commits (subject ends `(spec 01)`): `96c50eb`, `2e3eba2`, `6ae9f7d`,
`9f8574b`, `b7b4c69`. Interleaved spec 02 commits `a27c4eb`, `e848843` and the untracked
`.specs/features/02-setup-backend/verification.md` are out of scope and were not touched.

## Binding sources

Not run - profile `light` (step 1 runs under `ui` only). Binding source `context/specs/01-setup-frontend.md`
was read and its two Done-when items map to C1/C2 and C6/C10.

## Checks

One invocation: `bash .specs/features/01-setup-frontend/proofs.sh c1 c2 c3 c4 c5 c6 c7 c8 c9 c10 c11 c12` -
exit 0, each of `PASS c1` ... `PASS c12` printed individually; `git status --porcelain` unchanged afterwards
(build and dev rewrote no tracked file). All 12 functions exist at `proofs.sh:17,19,21,23,31,36,49,55,61,70,77,84`.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `npm run build` exits 0 | `proofs.sh c1` printed `PASS c1` (`✓ Compiled successfully`) | `.specs/features/01-setup-frontend/proofs.sh:17` - `(cd "$FE" && npm run build)` else `fail` | PASS |
| C2 | dev server `GET /` -> 200 with starter text | `proofs.sh c2` printed `GET http://localhost:3123/ -> 200, starter page`, `PASS c2` | `.specs/features/01-setup-frontend/dev-check.mjs:39` - `if (res.status !== 200) throw`; `dev-check.mjs:40` - `if (!body.includes("To get started, edit the")) throw` | PASS |
| C3 | `npm run lint` exits 0 | `proofs.sh c3` printed `PASS c3` | `.specs/features/01-setup-frontend/proofs.sh:21` - `(cd "$FE" && npm run lint)` else `fail` | PASS |
| C4 | layout.tsx, lockfile, strict true, no src/ | `proofs.sh c4` printed `PASS c4` | `proofs.sh:24-26` - `[ -f "$FE/app/layout.tsx" ]`, `[ -f "$FE/package-lock.json" ]`, `[ ! -e "$FE/src" ]`; `proofs.sh:27` - `t.compilerOptions.strict!==true` -> exit 1 | PASS |
| C5 | `dependencies.next` is exactly `16.3.8` | `proofs.sh c5` printed `PASS c5` | `.specs/features/01-setup-frontend/proofs.sh:32` - `p.dependencies.next!=="16.3.8"` -> exit 1 | PASS |
| C6 | components.json rsc/tsx/cssVariables/style radix-nova, radix-ui dep | `proofs.sh c6` printed `PASS c6` | `.specs/features/01-setup-frontend/proofs.sh:40-44` - `c.rsc!==true`, `c.tsx!==true`, `c.tailwind.cssVariables!==true`, `c.style!=="radix-nova"`, `!p.dependencies["radix-ui"]` | PASS |
| C7 | lib/utils.ts exports `cn`, package.json depends on `cn` | `proofs.sh c7` printed `PASS c7` | `.specs/features/01-setup-frontend/proofs.sh:50` - `grep -Eq` matching `^export function cn(` or `^export { cn } from `; `proofs.sh:51` - `!p.dependencies.cn` -> exit 1 | PASS |
| C8 | first line of frontend/AGENTS.md exact | `proofs.sh c8` printed `PASS c8` | `.specs/features/01-setup-frontend/proofs.sh:58` - `[ "$first" = 'Also follow the root \`AGENTS.md\` and \`context/DESIGN.md\`.' ]` | PASS |
| C9 | nextjs-agent-rules block unchanged since generator commit | `proofs.sh c9` printed `PASS c9` | `.specs/features/01-setup-frontend/proofs.sh:66-67` - `[ -n "$block_gen" ]`, `[ "$block_gen" = "$block_head" ]` | PASS |
| C10 | only frontend/AGENTS.md changed under frontend/ since generator commit | `proofs.sh c10` printed `PASS c10` | `.specs/features/01-setup-frontend/proofs.sh:74` - `[ "$changed" = "frontend/AGENTS.md" ]` | PASS |
| C11 | no tracked frontend/.env*, frontend/.env.local ignored | `proofs.sh c11` printed `PASS c11` | `.specs/features/01-setup-frontend/proofs.sh:80-81` - `[ -z "$tracked" ]`, `git check-ignore -q frontend/.env.local` | PASS |
| C12 | services/core/.env.local ignored, .env.example not | `proofs.sh c12` printed `PASS c12` | `.specs/features/01-setup-frontend/proofs.sh:85-86` - `check-ignore -q services/core/.env.local` else `fail`; `if check-ignore -q services/core/.env.example; then fail` | PASS |

## Level and sampling

- C2 crosses the HTTP boundary with a real request against `next dev` - correct level for the only status-code claim. Note (not a gap): the proof uses port 3123 (`dev-check.mjs:8`) where AC 2 names 3000; the check text names 3123 explicitly and the port is passed as a CLI flag to the same generated `dev` script, so the behaviour proven is the same.
- C9 compares against the generator commit, not against a fresh generator run; its strength rests on `6ae9f7d` being raw output, which was confirmed independently below.
- C7 regex accepts either export form; it is precise for the revised claim. Revision recorded in `checks.md:35` and in `b7b4c69` as user-approved (treated as given per the brief).
- No check claims more cases than its proof exercises.

## Generator commit independence check

`6ae9f7d feat(frontend): scaffold with create-next-app and initialize shadcn/ui (spec 01)` touches 22 files, all under `frontend/` (`git show --stat`). Read in full or at head: `AGENTS.md` (only the `nextjs-agent-rules` block, no Headroom line yet), `CLAUDE.md` (`@AGENTS.md`), `lib/utils.ts` (`export { cn } from "cn"`), `components.json` (stock shadcn schema, `radix-nova`, `rtl: false`), `package.json` (stock scripts `dev`/`build`/`start`/`lint`, next/react pins, shadcn deps), `app/layout.tsx` (stock Geist layout, "Create Next App" metadata), `app/page.tsx` (stock starter), `globals.css` (shadcn imports and theme vars), `components/ui/button.tsx` (stock shadcn button), `next.config.ts`, `eslint.config.mjs`, `postcss.config.mjs`, `tsconfig.json` (stock, strict true, `@/*` alias). Nothing reads as hand-written. Afterwards the only spec 01 change under `frontend/` is `9f8574b`, which adds exactly two lines (the required line plus a blank) to `frontend/AGENTS.md`. Minor plan inaccuracy (not a gap): plan Flow step 2 says `shadcn init` writes a preset font into `app/layout.tsx`, but the committed layout is the unmodified create-next-app one.

## Swept existing

No `Swept` row resolves to existing (all are `n/a` or check ids). The plan's `Observable` rows marked existing were re-read: `npm run dev`/`build` flags and defaults come from the generated `package.json` scripts (`"dev": "next dev"`, `"build": "next build"`, `"lint": "eslint"`), unchanged at HEAD per C10.

## Gate

`bash .specs/features/01-setup-frontend/proofs.sh c1 c2 c3 c4 c5 c6 c7 c8 c9 c10 c11 c12` - 12 passed, 0 failed (exit 0)
