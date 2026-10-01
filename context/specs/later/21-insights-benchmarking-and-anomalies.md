# Spec 21: Benchmarking and anomaly detection

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 4 (scale)
- **Status:** Not started
- **Module:** `forecasting`
- **Depends on:** 05, [15](15-forecasting-industry-templates.md)

## Goal

Show owners how their cash position compares with similar businesses, and flag unusual transactions or broken patterns early.

## Benchmarking

1. Start with three measures:
   - **Days of cash on hand:** how many days current cash would cover normal spending
   - **Customer payment time:** the average number of days customers take to pay
   - **Top-customer share:** the share of revenue that comes from the largest customer
2. Compare each business with a peer group of businesses in a similar industry, of a similar size, and in the same region. Show where the business ranks, for example "bottom 25% for days of cash on hand."
3. **Privacy rules:**
   - Only combined statistics are ever shown.
   - A benchmark appears only for peer groups of at least 20 businesses.
   - Businesses can opt out of contributing their data.
   - The privacy policy explains all of this.

## Anomaly detection

4. Flag unusual activity, such as:
   - a payment far larger or smaller than usual for that counterparty
   - a large payment to someone new
   - an expected recurring payment that didn't happen
   - a customer who stopped paying on their usual schedule
5. Anomalies appear in the dashboard and the weekly digest. They trigger urgent alerts only when they create a cash gap.
6. Users can mark each anomaly as expected or unexpected. Their answers improve future detection.

## Acceptance criteria

- [ ] No benchmark is shown for a peer group smaller than 20 businesses (tested).
- [ ] Businesses that opted out are left out of every benchmark (tested).
- [ ] On a test data set with known anomalies, detection finds at least 80% of them, with no more than 2 false alarms per business per month.
