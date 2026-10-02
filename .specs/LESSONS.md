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

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
