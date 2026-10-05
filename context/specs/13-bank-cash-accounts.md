# Spec 13: Choose cash accounts

- **Milestone:** 3, bank data
- **Status:** Done
- **Depends on:** 12

## Goal

Let the owner decide which accounts count as cash, and which one is the primary account.

## Build

- **Rules for what counts as cash:**
  - Checking accounts count by default.
  - Savings accounts are excluded until the owner includes them.
  - Credit cards and lines of credit never count.
  - Accounts in a currency other than CAD can't be included yet.
- **Primary account:** each business has one. It defaults to the checking account with the largest balance.
- **API:** `PATCH /v1/businesses/{business_id}/bank/accounts/{account_id}` includes an account, excludes it, or makes it primary.
- **Web:** the "choose accounts" step, matching `onboarding-3-choose-accounts.dc.html`, with a "Connect another bank" button.

## Done when

- [x] The API refuses to count a credit card or a US-dollar account as cash.
- [x] Two sandbox banks can be connected to one business.
- [x] The screen matches its mockup on a phone.
