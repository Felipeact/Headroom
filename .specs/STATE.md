# Project state

## Decisions

| ID | Decision | Rationale | Status | Date |
| --- | --- | --- | --- | --- |

## Handoff

**Feature**: 03-setup-database
**Where**: plan written and validated (`validate_plan.py` exit 0); awaiting human review. No checks, no code.
**In progress**: none
**Next step**: get the plan approved, then write `.specs/features/03-setup-database/checks.md`. On approval, add doors 1-3 from the plan's `Landing` to `## Decisions`.
**Blockers**: no Postgres reachable on this machine (Docker not installed); proofs for AC 7, 11, 13, 14 need `docker compose up -d postgres`
**Uncommitted**: none
**Branch**: development
