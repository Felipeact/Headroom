# Spec 25: Suggested fixes

- **Milestone:** 5, alerts and dashboard
- **Status:** Done
- **Depends on:** 24

## Goal

Attach specific, practical fixes to every cash gap alert.

## Build

Rules choose the fixes. Each fix shows what the lowest balance would be if it were applied.

- **A large payment goes out in the gap week:** ask to move it or split it.
- **Money is expected just after the gap:** ask the client to pay early.
- **A line of credit has enough available credit to cover the shortfall:** draw on it.
- **Otherwise:** short-term financing for the length of the gap.

## Done when

- [x] On the sample data, the alert offers three fixes, with new lowest balances of $12,750, $17,650, and $5,150, matching the alert mockup.
- [x] The line-of-credit fix appears only when the available credit covers the shortfall.
