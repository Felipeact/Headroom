# Spec 26: The dashboard

- **Milestone:** 5, alerts and dashboard
- **Status:** Done
- **Depends on:** 13, 21, 24

## Goal

Show everything that matters on one screen.

## Build

- **API:** `GET /v1/businesses/{business_id}/dashboard` combines balances, accounts, the forecast, open alerts, and the next 14 days.
- **Web:** the dashboard, matching `dashboard-desktop.dc.html` and `dashboard-phone.dc.html`. It includes:
  - summary cards and alert cards
  - the 13-week chart (Recharts), with the minimum-balance line, the low–high band, and a text summary for screen readers
  - the accounts panel, and the list of the next 14 days
  - the status line, with a banner when the forecast is incomplete or a bank needs attention
  - the loading, empty, error, and partial states from `DESIGN.md`
- **Not in v1:** the single-account alert, each account's lowest balance, and the account picker on the chart.

## Done when

- [x] The dashboard matches its mockups on desktop and phone, apart from the parts not in v1.
- [x] It renders in under 2 seconds on a mid-range phone, using the sample data.
- [x] An axe check finds no violations.
