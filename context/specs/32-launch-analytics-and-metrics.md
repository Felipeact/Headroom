# Spec 32: Analytics and the weekly metrics report

- **Milestone:** 7, production
- **Status:** In progress
- **Depends on:** 26

## Goal

Measure whether the pilot is working.

## Build

- **PostHog events** in the web app:
  - sign-up completed
  - business created
  - bank connected
  - minimum balance set
  - dashboard viewed
  - alert opened
  - alert dismissed
  - expected payment added

  Never send amounts or transaction details.
- **A weekly report** with:
  - weekly active businesses
  - alerts opened
  - activation: the share of new users who connect a bank within 24 hours of signing up
  - the 4-week forecast error from spec 22

**Docs:** [PostHog](https://posthog.com/docs)

## Done when

- [ ] Each event appears in PostHog from staging.
- [ ] The report runs without manual steps.
