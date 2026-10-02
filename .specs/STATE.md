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

## Handoff

**Feature**: 04-setup-tests-and-ci
**Where**: done; independent Verifier PASS 17/17 over `7b9f969..1e25913`, `validate_verification.py` exit 0; throwaway pull request #1 closed and `ci/spec-04-proof` deleted
**In progress**: none
**Next step**: spec 05 (another session has started it)
**Blockers**: none (Docker Desktop must be running for the local database-backed tests)
**Uncommitted**: none from spec 04
**Branch**: development
