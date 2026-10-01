# Spec 12: Scenarios and corrections

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 2 (paid pilot)
- **Status:** Not started
- **Module:** `forecasting`
- **Depends on:** 05, [09](09-billing-subscriptions-and-plans.md)

## Goal

Let owners shape the forecast in two ways: correct what the product detected, and ask "what if" questions without changing their real forecast.

## Corrections (all plans)

1. An owner or bookkeeper can edit a detected recurring pattern's amount, schedule, or next date. They can also mark a pattern as not recurring, or as ended.
2. Corrections always override automatic detection on later runs. A dismissed pattern isn't detected again from the same transactions. It can come back only after 3 new matching payments.
3. Each correction is logged with who made it and when. The log also shows how accurate detection is.

## Scenarios (Growth plan)

4. A scenario starts as a copy of the current forecast. The owner can then make changes such as:
   - delaying an item by some number of days
   - changing an amount
   - adding a one-off payment
   - adding a recurring payment, such as a new hire's salary
5. The scenario appears as a second line on the same chart as the real forecast. It shows its own lowest balance and how the cash gaps change.
6. Scenarios are private drafts, and they never trigger alerts or emails. Each business can save up to 10.
7. Scenarios are calculated on request and return within 2 seconds.
8. Businesses on the Starter plan see an upgrade prompt instead of scenarios. The plan check uses `has_feature` from [spec 09](09-billing-subscriptions-and-plans.md).

## API

- `PATCH /v1/recurring-patterns/{id}`
- `POST /v1/businesses/{id}/scenarios`
- `GET /v1/scenarios/{id}`
- `DELETE /v1/scenarios/{id}`

## Acceptance criteria

- [ ] A pattern marked "ended" disappears from the next forecast and isn't detected again from the same transactions.
- [ ] The result of an "invoice paid 30 days late" scenario matches a worked example calculated by hand.
- [ ] Scenarios never create alerts or emails.
- [ ] On the Starter plan, the scenario endpoints return 403 with the error type `plan-upgrade-required`.
- [ ] A scenario for a business with 2 years of history is calculated in under 2 seconds.
