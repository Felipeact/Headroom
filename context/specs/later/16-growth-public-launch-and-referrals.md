# Spec 16: Public launch, free forecast check, and referrals

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 3 (launch and grow)
- **Status:** Not started
- **Area:** Growth (frontend, `accounts`, `billing`)
- **Depends on:** 07, [09](09-billing-subscriptions-and-plans.md), [11](11-integrations-quickbooks-and-xero.md), [14](14-firm-multi-client-workspace.md)

## Goal

Build the public website, plus the features the growth plan depends on: a free forecast check, a referral program for partners, and listings in accounting app marketplaces.

## Requirements

**Public website**

1. The public website includes:
   - a pricing page for the Starter, Growth, and Firm plans
   - a security page that explains how bank data is handled
   - sign-up
   - a blog for articles people find through search, such as "13-week cash flow forecast template"

**Free forecast check**

2. Anyone can connect a bank and see their 13-week forecast for free, without entering a card. Alerts, scenarios, and actions need a paid plan, and upgrading takes one click.
3. Free accounts that don't upgrade stop syncing after a set period, such as 30 days. Their data is then deleted according to the data-handling policy.

**Partner referrals**

4. Partners (bookkeepers and firms) get a referral link.
   - Each sign-up that comes through the link is credited to that partner.
   - Commission is tracked on the business's payments, for example a percentage of its first-year revenue.
   - Commissions are paid out manually at first.
5. Partners see a dashboard listing the businesses they referred and the commission they've earned.

**Marketplace listings**

6. The app is listed in the QuickBooks and Xero app marketplaces after passing each marketplace's review. The listings depend on [spec 11](11-integrations-quickbooks-and-xero.md).

## Acceptance criteria

- [ ] A visitor can get from the pricing page to a free forecast without entering a card.
- [ ] A referral stays credited to the partner from the link click, through sign-up, to the first payment (tested).
- [ ] Commission statements match the revenue Stripe records for referred businesses.
- [ ] Both marketplace listings are approved.
- [ ] A lawyer has reviewed the security page.
