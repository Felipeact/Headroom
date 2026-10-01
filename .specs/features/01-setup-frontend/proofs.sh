#!/usr/bin/env bash
# Proofs for spec 01 checks. Usage: bash .specs/features/01-setup-frontend/proofs.sh c1 [c2 ...]
# There is no test runner until spec 04, so each check is a named shell function.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
FE="$ROOT/frontend"
HERE="$ROOT/.specs/features/01-setup-frontend"

fail() { echo "FAIL $CHECK: $*" >&2; exit 1; }
gen_commit() {
  local sha
  sha="$(git -C "$ROOT" log --format=%H -1 --grep='initialize shadcn/ui')"
  [ -n "$sha" ] || fail "no generator commit with subject 'initialize shadcn/ui'"
  echo "$sha"
}

c1() { (cd "$FE" && npm run build) || fail "npm run build exited non-zero"; }

c2() { node "$HERE/dev-check.mjs" || fail "dev server check failed"; }

c3() { (cd "$FE" && npm run lint) || fail "npm run lint exited non-zero"; }

c4() {
  [ -f "$FE/app/layout.tsx" ] || fail "frontend/app/layout.tsx missing"
  [ -f "$FE/package-lock.json" ] || fail "frontend/package-lock.json missing"
  [ ! -e "$FE/src" ] || fail "frontend/src exists"
  node -e 'const t=require(process.argv[1]); if(t.compilerOptions.strict!==true) process.exit(1)' "$FE/tsconfig.json" \
    || fail "tsconfig strict is not true"
}

c5() {
  node -e 'const p=require(process.argv[1]); if(p.dependencies.next!=="16.3.8"){console.error(p.dependencies.next);process.exit(1)}' "$FE/package.json" \
    || fail "next is not pinned to 16.3.8"
}

c6() {
  node -e '
    const c=require(process.argv[1]); const p=require(process.argv[2]);
    const bad=[];
    if(c.rsc!==true) bad.push("rsc");
    if(c.tsx!==true) bad.push("tsx");
    if(c.tailwind.cssVariables!==true) bad.push("cssVariables");
    if(c.style!=="radix-nova") bad.push("style="+c.style);
    if(!p.dependencies["radix-ui"]) bad.push("radix-ui dependency");
    if(bad.length){console.error(bad.join(", "));process.exit(1)}' "$FE/components.json" "$FE/package.json" \
    || fail "components.json or radix base wrong"
}

c7() {
  grep -Eq '^export (function cn\(|\{ cn \} from )' "$FE/lib/utils.ts" || fail "lib/utils.ts does not export cn"
  node -e 'const p=require(process.argv[1]); if(!p.dependencies.cn) process.exit(1)' "$FE/package.json" \
    || fail "package.json does not depend on cn"
}

c8() {
  local first
  first="$(head -n 1 "$FE/AGENTS.md" | tr -d '\r')"
  [ "$first" = 'Also follow the root `AGENTS.md` and `context/DESIGN.md`.' ] || fail "first line is: $first"
}

c9() {
  local sha block_gen block_head
  sha="$(gen_commit)"
  block_gen="$(git -C "$ROOT" show "$sha:frontend/AGENTS.md" | sed -n '/BEGIN:nextjs-agent-rules/,/END:nextjs-agent-rules/p')"
  block_head="$(git -C "$ROOT" show "HEAD:frontend/AGENTS.md" | sed -n '/BEGIN:nextjs-agent-rules/,/END:nextjs-agent-rules/p')"
  [ -n "$block_gen" ] || fail "no nextjs-agent-rules block in generator commit"
  [ "$block_gen" = "$block_head" ] || fail "nextjs-agent-rules block changed since $sha"
}

c10() {
  local sha changed
  sha="$(gen_commit)"
  changed="$(git -C "$ROOT" diff --name-only "$sha" HEAD -- frontend)"
  [ "$changed" = "frontend/AGENTS.md" ] || fail "files changed under frontend since $sha: ${changed:-none}"
}

c11() {
  local tracked
  tracked="$(git -C "$ROOT" ls-files 'frontend/.env*')"
  [ -z "$tracked" ] || fail "tracked env files: $tracked"
  git -C "$ROOT" check-ignore -q frontend/.env.local || fail "frontend/.env.local is not ignored"
}

c12() {
  git -C "$ROOT" check-ignore -q services/core/.env.local || fail "services/core/.env.local is not ignored"
  if git -C "$ROOT" check-ignore -q services/core/.env.example; then fail "services/core/.env.example is ignored"; fi
}

[ "$#" -gt 0 ] || { echo "usage: $0 c1 [c2 ...]" >&2; exit 2; }
for CHECK in "$@"; do
  "$CHECK"
  echo "PASS $CHECK"
done
