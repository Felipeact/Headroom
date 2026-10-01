# Spec 09: Subscriptions and plans

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 1 (MVP)
- **Status:** Not started
- **Module:** `billing`
- **Depends on:** 01

## Goal

Let owners pay for the Starter or Growth plan by card, and give every module one place to check what a business's plan includes.

## Requirements

1. **Plans:** Starter costs $39/month and Growth costs $79/month. Set both up as products and prices in Stripe. The prices live in Stripe, not in the code.
2. **Payments:**
   - New subscriptions go through Stripe Checkout.
   - Owners change their card or plan, cancel, and see invoices in the Stripe customer portal.
3. **Pilot discount:** a Stripe coupon gives 50% off for three months.
4. **Plan checks:**
   - Other modules call `billing.service.has_feature(business_id, feature)` to check what a plan includes, for example whether scenario planning is available.
   - The list of which features belong to which plan lives in one place in the code.
   - Numeric limits, such as the number of bank connections, live in the same place. Other modules read them with `billing.service.limit(business_id, name)`.
5. **Webhooks:** Stripe webhooks keep each subscription's status up to date: active, past due, or canceled.
   - Verify each webhook's `Stripe-Signature` header before processing it.
   - Use Stripe's event ID so each event is processed only once.
6. **Late payment:** when a payment is late, the product keeps working for 7 days and shows a banner. After that, forecasts become read-only and new alerts pause until the owner pays.
7. **Access:** only owners can manage billing.
8. **Connection limits:**
   - Starter: 1 connection, which is either one bank (with all of its accounts) or one accounting app.
   - Growth: up to 5 bank connections and 1 accounting app.
   - Firm: the Growth limits apply to each client business.
   - If a downgrade leaves a business with more connections than its new plan allows, the owner chooses which ones to keep. The rest stop syncing but aren't deleted, and they're left out of the forecast.

## API and events

- `POST /v1/billing/checkout-session`
- `POST /v1/billing/portal-session`
- `GET /v1/billing/subscription`
- `POST /v1/webhooks/stripe`
- Publishes `subscription.changed`

## Acceptance criteria

- [ ] A test-mode card completes checkout, and the business becomes active within 10 seconds of the webhook arriving.
- [ ] Replaying the same Stripe webhook changes nothing.
- [ ] A webhook with an invalid signature is rejected, and nothing changes.
- [ ] `has_feature` returns `false` for Growth-only features on the Starter plan, and `true` immediately after an upgrade.
- [ ] The pilot coupon gives 50% off for exactly three billing periods.
- [ ] `limit` returns 1 bank connection for Starter and 5 for Growth. After a downgrade from Growth, the connections the owner didn't keep stop syncing.

## Open questions

- Should there be a free trial, or is the free forecast check in [spec 16](16-growth-public-launch-and-referrals.md) enough?
- How will sales tax be handled in each region? One option is Stripe Tax.
- Should there be annual plans?
- Is one connection enough for Starter? A business with two banks, or a bank plus accounting software, would have to choose Growth. Test this during the pilot.
