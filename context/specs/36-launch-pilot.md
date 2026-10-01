# Spec 36: Pilot launch

- **Milestone:** 7, production
- **Status:** Not started
- **Depends on:** 34, 35

## Goal

Prove the whole flow works end to end, then let the first pilot client in.

## Build

- A Playwright end-to-end test on staging, using the Plaid sandbox. It:
  - signs up
  - creates a business
  - connects two banks
  - sets a minimum balance
  - waits for a forecast and an alert
  - receives the alert email in a test inbox
- Pilot billing:
  - Stripe Payment Links in Canadian dollars for the Starter and Growth plans, at 50% off for three months.
  - GST/HST charged where it applies. Confirm the details with an accountant.
- Merge `development` into `main`.

## Done when

- [ ] The end-to-end test passes on staging.
- [ ] Production serves the first pilot client.
