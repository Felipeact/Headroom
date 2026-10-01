# Spec 11: QuickBooks and Xero sync

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 2 (paid pilot)
- **Status:** Not started
- **Module:** `bank_sync`
- **Depends on:** 03, 04

## Goal

Import open invoices and unpaid bills with their real due dates, so the forecast relies less on guesses.

## Requirements

1. **Connecting.** Owners connect QuickBooks Online or Xero through OAuth 2.0, with read-only permissions.
   - Tokens are encrypted the same way as Plaid tokens.
   - Access tokens are refreshed automatically.
   - If a refresh fails, the connection is flagged so the owner can reconnect.
2. **Importing.** Import open invoices (money coming in) and unpaid bills (money going out).
   - For each one, store the counterparty, the amount due in cents, the currency, the due date, and the status.
   - Keep them current using the provider's webhooks where available, plus a nightly sync.
3. **Customers who pay late.** Predict when each invoice will actually be paid. Start from the due date, then add how many days late that customer usually pays, once there's enough payment history to know.
4. **No double counting:**
   - When a paid invoice's money shows up in the bank, match the two so the payment counts only once.
   - When an invoice or bill covers the same payment as a manual expected payment or a predicted recurring payment, the invoice or bill wins.
5. **Forecast update.** Publish `forecast_inputs.changed` after every import that changes anything.
6. **Marketplace requirements.** Meet the requirements for listing in the QuickBooks and Xero app marketplaces. [Spec 16](16-growth-public-launch-and-referrals.md) needs these listings.

## Acceptance criteria

- [ ] A QuickBooks sandbox company and the Xero demo company both connect, and their invoices and bills appear in upcoming transactions.
- [ ] After an invoice is paid in the sandbox, it leaves expected money-in on the next sync, and the bank deposit isn't counted twice.
- [ ] An expired refresh token flags the connection, and reconnecting restores it.
- [ ] Tested on past data, forecasts that use accounting data are more accurate than forecasts for the same businesses that use bank data only.
