# Spec 12: Connect a bank

- **Milestone:** 3, bank data
- **Status:** In progress
- **Depends on:** 11

## Goal

Let an owner connect a bank through Plaid, without Headroom ever seeing their bank password.

## Build

- **API**, following Plaid's quickstart and using the sandbox:
  - `POST /v1/businesses/{business_id}/bank/link-token` creates a link token for Canada (`CA`), asking for 24 months of history.
  - `POST /v1/businesses/{business_id}/bank/connections` exchanges the `public_token` for an access token.
  - Access tokens are encrypted with Fernet (from the `cryptography` package) before storage, using a key from an environment variable.
  - For each bank, and for each of its accounts, store the name, type, last four digits, currency, and balance.
  - Connecting a bank writes an audit log entry.
  - Only owners can connect banks.
- **Web:** onboarding step 3, matching `onboarding-3-connect-bank.dc.html`, using `react-plaid-link`.

**Docs:** [Plaid quickstart](https://plaid.com/docs/quickstart/)

## Done when

- [ ] A sandbox bank connects in under 2 minutes.
- [ ] No API response or log contains an access token, and the database stores it only in encrypted form (tested).
