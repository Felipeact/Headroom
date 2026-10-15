# Spec 33: Security review

- **Milestone:** 7, production
- **Status:** In progress
- **Depends on:** 17, 20, 27, 29, 30, 31, 32

## Goal

Check that the product is safe to hold real businesses' bank data.

## Build

- Rate limits and security headers on the API, and rejection of cross-origin requests from browsers.
- A test or written check for every rule under "Security and data handling" in `AGENTS.md`, including:
  - token encryption
  - removing secrets from logs
  - webhook signatures
  - denying access across businesses, on every endpoint
- Two-factor authentication on every admin account, and production access limited to the people who need it.
- A written plan for what to do if customer data is exposed.

## Done when

- [ ] Every security rule has a passing test or a written check.
- [ ] The data-exposure plan has been rehearsed once.
