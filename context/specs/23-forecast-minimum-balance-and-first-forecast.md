# Spec 23: Minimum balance and the first forecast

- **Milestone:** 4, forecast
- **Status:** Done
- **Depends on:** 21

## Goal

Finish onboarding: the owner sets a minimum balance, then waits for their first forecast.

## Build

- **API:**
  - `GET /v1/businesses/{business_id}/minimum-balance` and `PUT /v1/businesses/{business_id}/minimum-balance`. Only owners can change it.
  - The suggested starting value is about two weeks of typical spending.
  - `GET /v1/businesses/{business_id}/forecast/status` reports the first forecast's progress.
- **Web:**
  - Onboarding step 4, matching `onboarding-4-minimum-balance.dc.html`.
  - Onboarding step 5, matching `onboarding-5-building-forecast.dc.html`. It moves to the dashboard once the forecast is ready.

## Done when

- [x] A Playwright test goes from sign-up to the "building your forecast" screen, using the Plaid sandbox.
- [x] Both screens match their mockups.
