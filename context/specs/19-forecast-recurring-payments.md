# Spec 19: Recurring payments

- **Milestone:** 4, forecast
- **Status:** Not started
- **Depends on:** 16, 18

## Goal

Find the payments that repeat, such as payroll, rent, and regular suppliers, and predict when they'll happen next.

## Build

- For each account:
  - Group transactions by counterparty and similar amount.
  - Detect these schedules: weekly, every two weeks, twice a month, monthly, and quarterly.
  - Require at least 3 occurrences.
  - Predict the next date, and the amount as the median of recent amounts.
- Skip card purchases, and internal transfers between two included accounts.
- Each pattern stores its counterparty, schedule, typical amount, next date, account, confidence, and the transactions it came from.
- `GET /v1/businesses/{business_id}/recurring-patterns`

## Done when

- [ ] On the sample data, payroll and rent are found, with the correct schedules and next dates.
- [ ] A payment seen only twice isn't treated as recurring.
- [ ] Transfers between the two sample accounts aren't detected as recurring.
