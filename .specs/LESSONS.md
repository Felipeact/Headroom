# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Plan/Checks)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - GitHub computes a pull request's mergeStateStatus lazily and can answer UNKNOWN right after a push; a proof reading it must retry until it settles.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `ci` · harmful: 0
- features: 04-setup-tests-and-ci
- evidence: .specs/features/04-setup-tests-and-ci/proofs.sh:169 (ci)
- last seen: 2026-10-02T02:53:30Z

### L-002 - When a criterion names several file kinds (.ts and .tsx), the proof must exercise each kind, not just one.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `frontend` · harmful: 0
- features: 04-setup-tests-and-ci
- evidence: AC 2 (frontend)
- last seen: 2026-10-02T02:53:31Z

### L-003 - Prove a table exists by querying the schema, not by a command that exits 0 when the table is absent
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `migrations` · harmful: 0
- features: 05-setup-railway-staging
- evidence: C3 - proofs.sh:81 (migrations)
- last seen: 2026-10-02T03:37:24Z

### L-004 - Get user confirmation before a check asserts a command or name different from the literal the binding spec gives
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `deploy` · harmful: 0
- features: 05-setup-railway-staging
- evidence: C20 - proofs.sh:251-252; plan.md:128 (deploy)
- last seen: 2026-10-02T03:37:24Z

### L-005 - When a screen renders the same control in two places (desktop nav and a phone menu Dialog), assert the per-control metric in both placements, and read sizes only after the Dialog's open animation settles.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `frontend/e2e` · harmful: 0
- features: 07-web-app-shell
- evidence: checks.md C5 / e2e/shell.spec.ts (frontend/e2e)
- last seen: 2026-10-02T16:06:57Z

### L-006 - A 'no secret in source' check must name the file set its proof scans (git-tracked or would-track), because the ignored .env.local is where the secret is meant to live.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `frontend/tests` · harmful: 0
- features: 07-web-app-shell
- evidence: checks.md C41 (frontend/tests)
- last seen: 2026-10-02T16:06:57Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
