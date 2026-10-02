# Project state

## Decisions

| ID | Decision | Rationale | Status | Date |
| --- | --- | --- | --- | --- |
| AD-001 | Settings: `Settings(BaseSettings)` in `app/settings.py`, `env_file=".env.local"`, no defaults for secrets; process env beats the file; code reads only through cached `get_settings()`, never at import | no secrets in code, and importing `app.main` must work without a database (spec 03 door 1) | active | 2026-10-01 |
| AD-002 | Readiness probe: `GET /healthz/ready`, no auth, outside `/v1`; `200 {"status": "ok"}` on `SELECT 1`, `503 {"status": "unavailable"}` on any SQLAlchemy error, no detail in the body | read by Railway, not clients; RFC 9457 does not apply to probes (spec 03 door 2) | active | 2026-10-01 |
| AD-003 | Every model inherits `app.db.Base`, whose `MetaData` uses the SQLAlchemy-docs naming convention (`ix`, `uq`, `ck`, `fk`, `pk`) | autogenerate can alter and drop constraints by name; adding it later means renaming every constraint (spec 03 door 3) | active | 2026-10-01 |
| AD-004 | CI check names: workflow `CI` in `.github/workflows/ci.yml` with job ids `web` and `api` (no `name:` override, no matrix); branch protection on `development` and `main` requires exactly those two contexts, strict off, admin bypass kept | a renamed job leaves protection waiting on a check that never runs, which blocks every merge; admin bypass keeps direct commits to `development` working (spec 04 door 1) | active | 2026-10-01 |
| AD-005 | Railway topology: one project `headroom` in US East (`us-east4-eqdc4a`); environments are `staging` (tracks `development`) and, from spec 34, `production`; services named exactly `Postgres`, `api` (root `/services/core`), `web` (root `/frontend`); new services (spec 15 `jobs`) join the same project | reference variables and the IaC file bind to service names; one project lets spec 34 add `production` beside `staging` (spec 05 door 1) | active | 2026-10-01 |
| AD-006 | Railway `DATABASE_URL` on `api` is `postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}`, private host only; `Postgres` gets no public domain or TCP proxy | Railway's own `DATABASE_URL` uses `postgresql://`, which AD-001 rejects (spec 05 door 3) | active | 2026-10-01 |
| AD-007 | Railway service settings live only in `.railway/railway.ts` (Railway Infrastructure as Code, SDK `railway` pinned in `.railway/package.json`), applied with `railway config apply`; no `railway.json` / `railway.toml`; `railway config plan --detailed-exit-code` exits 0 when live matches the file. Under Git Bash on Windows run it as `env _=<railway.exe> <railway.exe> config ...` | Railway stops reading Config as Code on 2026-12-01 and rejects setting its path; IaC keeps settings in a reviewed diff (spec 05 door 4) | active | 2026-10-01 |

| AD-008 | Web colour tokens: the DESIGN.md names verbatim as CSS variables in `frontend/app/globals.css` `:root`, plus `--line-soft` `#ECE8E0` and `--line-strong` `#C9C2B5`; each exposed as Tailwind `--color-<name>`; shadcn semantic variables alias them, and shadcn `--accent` is the brand blue | screens spell colours with these names, so renaming one touches every screen (spec 06 doors 1, 6) | active | 2026-10-01 |
| AD-009 | Component variant names follow DESIGN.md: Button `primary \| secondary \| outline \| link \| destructive \| ghost` (default `primary`, sizes `default` and `icon`, both at least 44px); Badge `neutral \| muted \| positive \| warning \| danger` | shadcn's `outline` is DESIGN.md's secondary look, so its names would mean two buttons (spec 06 doors 2, 3) | active | 2026-10-01 |
| AD-010 | Development-only pages live under `app/dev/` and call `notFound()` when `process.env.NODE_ENV === "production"`, so they 404 on staging and production | no Railway variable for pages no client needs (spec 06 door 5) | active | 2026-10-01 |

## Handoff

**Feature**: 06-web-design-system
**Where**: done; independent Verifier PASS 37/37 at round 1 over `f1bbdd2..2a08ab3` (profile light), `validate_verification.py` exit 0. `/dev/components` renders the Components mockup locally and returns 404 in any production build
**In progress**: none
**Next step**: spec 07 (app shell; depends on 06), 08 or 09
**Blockers**: none. On this machine, npm 12 rejects the user-level `allow-scripts` in `~/.npmrc` for project installs; run `npm install` / `npx shadcn add` with `npm_config_userconfig=<empty file>`. Playwright reuses any server on port 3000, so stop other dev servers first
**Uncommitted**: none
**Branch**: spec-06-web-design-system (worktree `.claude/worktrees/spec-06-web-design-system`), not yet merged into `development`
