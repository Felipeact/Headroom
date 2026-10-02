# Project state

## Decisions

| ID | Decision | Rationale | Status | Date |
| --- | --- | --- | --- | --- |
| AD-001 | Settings: `Settings(BaseSettings)` in `app/settings.py`, `env_file=".env.local"`, no defaults for secrets; process env beats the file; code reads only through cached `get_settings()`, never at import | no secrets in code, and importing `app.main` must work without a database (spec 03 door 1) | active | 2026-10-01 |
| AD-002 | Readiness probe: `GET /healthz/ready`, no auth, outside `/v1`; `200 {"status": "ok"}` on `SELECT 1`, `503 {"status": "unavailable"}` on any SQLAlchemy error, no detail in the body | read by Railway, not clients; RFC 9457 does not apply to probes (spec 03 door 2) | active | 2026-10-01 |
| AD-003 | Every model inherits `app.db.Base`, whose `MetaData` uses the SQLAlchemy-docs naming convention (`ix`, `uq`, `ck`, `fk`, `pk`) | autogenerate can alter and drop constraints by name; adding it later means renaming every constraint (spec 03 door 3) | active | 2026-10-01 |
| AD-004 | CI check names: workflow `CI` in `.github/workflows/ci.yml` with job ids `web` and `api` (no `name:` override, no matrix); branch protection on `development` and `main` requires exactly those two contexts, strict off, admin bypass kept | a renamed job leaves protection waiting on a check that never runs, which blocks every merge; admin bypass keeps direct commits to `development` working (spec 04 door 1) | active | 2026-10-01 |

## Handoff

**Feature**: 04-setup-tests-and-ci
**Where**: C1-C17 green; independent Verifier pending over `7b9f969..HEAD`
**In progress**: none
**Next step**: Verifier report, then close throwaway pull request #1 and delete `ci/spec-04-proof`
**Blockers**: none (Docker Desktop must be running for the local database-backed tests)
**Uncommitted**: none from spec 04 (`.specs/features/05-setup-railway-staging/` is not part of this feature)
**Branch**: development
