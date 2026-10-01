# Spec 19: Multiple currencies, entities, and regions

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 4 (scale)
- **Status:** Not started
- **Modules:** `accounts`, `bank_sync`, `forecasting`, `billing`
- **Depends on:** 05, [09](09-billing-subscriptions-and-plans.md)

## Goal

Serve businesses that have several legal entities or accounts in different currencies, and expand into new regions.

## Requirements

1. **Multiple entities.** A group can contain several legal entities, each with its own accounts. Forecasts are shown for each entity and for the whole group combined.
2. **Multiple currencies:**
   - Store every amount in its original currency, as whole cents with a currency code.
   - For the combined forecast, convert everything to one reporting currency using daily exchange rates from a named provider.
   - Show users which exchange rates were used.
3. **Internal transfers.** Detect transfers between the group's own accounts or entities, and leave them out of the combined totals. Otherwise, the same money would count as both money in and money out.
4. **New regions.** Each new region needs:
   - a bank-data provider that covers it (Plaid, or a local open-banking provider)
   - customer data stored inside the region, where the law requires it
   - local date and number formats
   - tax handling for billing
   - a legal review
5. **Regional pricing.** Stripe holds prices in each region's currency.

## Acceptance criteria

- [ ] A group with a USD entity and a EUR entity shows correct forecasts for each entity and for the group combined.
- [ ] Transfers between the two entities don't appear as money in or money out in the combined view.
- [ ] A review of the infrastructure confirms that data for a region with data-residency rules stays in that region.
