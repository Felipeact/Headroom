# Spec 07: App shell, translations, and formatting

- **Milestone:** 2, foundations
- **Status:** Done
- **Depends on:** 06

## Goal

Build the frame every page lives in: the header, navigation, translations, formatting, and error tracking.

## Build

- The header and navigation from the dashboard mockup: Headroom, the business name, and links to Dashboard, Expected payments, Alerts, and Settings. The linked pages are empty placeholders for now.
- next-intl with English messages. All interface text comes from `messages/en.json`.
- `lib/format.ts`:
  - money from integer cents, in CAD with the `en-CA` locale: whole dollars, a true minus sign, and a plus sign for money in
  - dates with the month spelled out
- Sentry in the web app, set up by following Sentry's Next.js guide.

**Docs:** [next-intl](https://next-intl.dev), [Sentry for Next.js](https://docs.sentry.io/platforms/javascript/guides/nextjs/)

## Done when

- [x] Unit tests cover money formatting (for example, 320000 → "$3,200" and −320000 → "−$3,200") and date formatting.
- [x] The shell works at 375 pixels wide and with the keyboard alone.
- [x] A deliberate test error shows up in Sentry.
