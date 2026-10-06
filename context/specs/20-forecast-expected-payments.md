# Spec 20: Expected payments

- **Milestone:** 4, forecast
- **Status:** In progress
- **Depends on:** 13, 14

## Goal

Let owners add payments they know are coming, which the bank data can't predict.

## Build

- **API:** create, list, edit, and delete expected payments. Each has:
  - an amount
  - a direction (in or out)
  - a date
  - an account, defaulting to the primary account
  - a description
  - an optional repeat schedule
- **Matching:** when a real transaction is within an amount tolerance and a date window of an expected payment, mark the payment as matched, so the money is counted once.
- **Events:** publish `forecast_inputs.changed` on any change.
- **Web:** the expected payments page, matching `expected-payments.dc.html`, with the add-and-edit dialog. On phones, the dialog is a full-screen sheet.

## Done when

- [ ] Adding, editing, and deleting all work from the web app through to the database.
- [ ] A matched payment is counted only once.
- [ ] The page and the dialog match the mockup.
