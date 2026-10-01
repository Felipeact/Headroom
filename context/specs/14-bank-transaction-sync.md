# Spec 14: Transaction sync

- **Milestone:** 3, bank data
- **Status:** Not started
- **Depends on:** 12 (can run alongside 13)

## Goal

Bring in every connected account's transactions and balances, with no duplicates.

## Build

- Use Plaid's `/transactions/sync`, storing its cursor for each connection. Apply the transactions Plaid reports as added, modified, and removed.
- Normalize every transaction once, here:
  - amounts in cents, with the currency
  - money in as positive, money out as negative
  - the date stored as a date, with a pending flag
  - the counterparty and Plaid's category kept
- Save each transaction by its Plaid transaction ID. When a pending transaction posts, the posted version replaces it.
- After each sync, store every account's latest balance and, for lines of credit, the available credit.
- Add the in-process event bus. Publish `transactions.synced` after any sync that changed data.
- `POST /v1/webhooks/plaid` verifies the `Plaid-Verification` signature, then triggers a sync.

**Docs:** [Plaid Transactions](https://plaid.com/docs/transactions/)

## Done when

- [ ] Running the same sync twice changes nothing the second time.
- [ ] A pending transaction that posts appears once, and a transaction Plaid removes is removed.
- [ ] Money out is negative and money in is positive for all sandbox data.
- [ ] A webhook with an invalid signature is rejected.
