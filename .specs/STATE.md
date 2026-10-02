# Project state

## Decisions

| ID | Decision | Rationale | Status | Date |
| --- | --- | --- | --- | --- |
| AD-001 | Settings: `Settings(BaseSettings)` in `app/settings.py`, `env_file=".env.local"`, no defaults for secrets; process env beats the file; code reads only through cached `get_settings()`, never at import | no secrets in code, and importing `app.main` must work without a database (spec 03 door 1) | active | 2026-10-01 |
| AD-002 | Readiness probe: `GET /healthz/ready`, no auth, outside `/v1`; `200 {"status": "ok"}` on `SELECT 1`, `503 {"status": "unavailable"}` on any SQLAlchemy error, no detail in the body | read by Railway, not clients; RFC 9457 does not apply to probes (spec 03 door 2) | active | 2026-10-01 |
| AD-003 | Every model inherits `app.db.Base`, whose `MetaData` uses the SQLAlchemy-docs naming convention (`ix`, `uq`, `ck`, `fk`, `pk`) | autogenerate can alter and drop constraints by name; adding it later means renaming every constraint (spec 03 door 3) | active | 2026-10-01 |

## Handoff

**Feature**: 03-setup-database
**Where**: built; C1-C15 green at HEAD; independent Verifier dispatched over `714b59b..HEAD`
**In progress**: verification report
**Next step**: once `validate_verification.py 03-setup-database` exits 0, start spec 04
**Blockers**: none (Docker Desktop must be running for the database-backed tests)
**Uncommitted**: none
**Branch**: development
