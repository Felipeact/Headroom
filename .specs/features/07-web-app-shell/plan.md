# 07 - App shell, translations, and formatting

## Problem

The web app's home page is still the create-next-app starter: the Next.js logo, "To get started,
edit the page.tsx file", and links to Vercel. Nothing frames a page. There is no header, no
navigation, and no place to put shared states. Every screen spec after this one (11-13 onboarding,
17 settings, 20 expected payments, 26 dashboard, 27 alert page) has to render money and dates, and
AGENTS.md requires them to use `lib/format.ts` and `messages/en.json`. Neither file exists yet. So
the first screen to need them would invent its own money formatting. `Intl` alone gets it wrong:
in `en-CA` it prints `-$3,200` with a hyphen, not DESIGN.md's true minus `−$3,200`, and it prints
`-$0` for −49 cents. Every later screen would copy whatever that first screen did. Web errors also
go nowhere: the API reports to Sentry (spec 08), but a crash in the browser leaves no trace. The
source gives no evidence beyond the roadmap's build order. Spec 10 needs this shell to land first.

When this ships, `/`, `/expected-payments`, `/alerts` and `/settings` each render inside the
dashboard mockup's header and navigation, as placeholder pages. Every string the shell shows comes
from `messages/en.json`. `formatMoney(-320000)` returns `−$3,200`. A deliberate test error in the
web app shows up in a dedicated Sentry project.

## Flow

This reuses the spec 06 components (`Button`, `Dialog`, `Skeleton`, `Card`) and tokens, and the
spec 06 `/dev/*` production gate (AD-014) for the Sentry test page. Next-intl and Sentry are set
up with their official setup steps, not by hand.

1. request for `/`, `/expected-payments`, `/alerts` or `/settings` -> `frontend/app/(app)/layout.tsx` (new route group, door 1). Renders the header and nav, then hands the page to `<main>`
2. `frontend/i18n/request.ts` (new, door 3) - `getRequestConfig` returns locale `en` and `messages/en.json` (new, door 3). `NextIntlClientProvider` in `app/layout.tsx` (exists) passes them on to client components
3. the shell components (new, no door - placement per conventions) - `useTranslations` / `getTranslations` for every string. Desktop shows the nav links; phone shows a menu button that opens the spec 06 `Dialog` (exists) with the same links. The business-name block is shown only when a name is passed in, and nothing passes one until spec 11
4. `frontend/app/(app)/loading.tsx` and `error.tsx` (new) - shared loading and error states for every page in the group. `error.tsx` reports the error to Sentry
5. `frontend/lib/format.ts` (new, door 2) - `formatMoney`, `formatSignedMoney`, `formatDate`. Pure functions with no callers yet besides tests
6. `@sentry/nextjs` through `instrumentation.ts`, `instrumentation-client.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`, `app/global-error.tsx` and `withSentryConfig` in `next.config.ts` (new, written by the wizard, then trimmed by door 4). It initialises only when `NEXT_PUBLIC_SENTRY_DSN` is set
7. `frontend/app/dev/sentry-check/page.tsx` (new, door 5) - throws a deliberate client error and a deliberate server error. Returns 404 in a production build
8. out: HTML pages, and error events sent to the `headroom-web` Sentry project

## Impact

| Front | What changes |
| --- | --- |
| domain | new routes: `/` is now the Dashboard, not the starter page. `/expected-payments`, `/alerts` and `/settings` exist as placeholders. Specs 20, 26, 27 and 17 fill them in, and the email links in specs 29-30 point at them (door 1) |
| domain | new terms: `formatMoney` / `formatSignedMoney` / `formatDate` (door 2). Every later screen and email that shows money or a date calls them |
| domain | new term: the message namespaces in `en.json` (`Shell`, `Nav`, `Pages`, `States`, `Metadata`). Later specs add keys under their own namespace |
| starter page | `app/page.tsx` and its Next/Vercel images are replaced. `app/page.test.tsx` and `e2e/home.spec.ts` are rewritten against the new Dashboard placeholder. `public/next.svg`, `public/vercel.svg` and the other starter SVGs go once nothing references them |
| root layout | `app/layout.tsx` gains `NextIntlClientProvider`, and its metadata changes from "Create Next App" to "Headroom" from `en.json`. `/dev/components` stays outside the shell, because the shell lives in the `(app)` group |
| config | `next.config.ts` is wrapped by `createNextIntlPlugin()` and `withSentryConfig`. The wizard's `.env.sentry-build-plugin` is already ignored by `.gitignore`'s `.env*` rule. `.env.example` gains the empty Sentry keys |
| dependencies | new runtime dependencies: `next-intl` (4.x, supports `next` ^16) and `@sentry/nextjs` (11.x, supports `next` ^16) |
| CI | `npm run build` must still pass with no `SENTRY_AUTH_TOKEN`, because CI has none. Source maps are uploaded only when the token is present |
| staging | `web` needs `NEXT_PUBLIC_SENTRY_DSN` (and optionally `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`) as Railway variables. That needs a push go-ahead, as spec 08 did |
| stored data | nothing to migrate |

## Relations

None - no stored-data shape change

## Surface

Only routes this adds or whose signature changes.

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `GET /` | none | HTML: shell plus the Dashboard placeholder | `200` |
| `GET /expected-payments` | none | HTML: shell plus the Expected payments placeholder | `200` |
| `GET /alerts` | none | HTML: shell plus the Alerts placeholder | `200` |
| `GET /settings` | none | HTML: shell plus the Settings placeholder | `200` |
| `GET /dev/sentry-check` | none | HTML: two buttons that raise deliberate errors | `200` in development, `404` in a production build |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. Route paths and the shell's route group | `app/(app)/layout.tsx` holds the shell. Pages: `app/(app)/page.tsx` -> `/`, `app/(app)/expected-payments/page.tsx`, `app/(app)/alerts/page.tsx`, `app/(app)/settings/page.tsx`. Later sign-in (10) and onboarding (11-13) pages sit outside `(app)` | `/dashboard` for the dashboard: an extra hop after login with nothing at `/`. The shell in the root `app/layout.tsx`: sign-in, onboarding and `/dev/*` would all inherit the nav they must not show |
| 2. Formatting API | `formatMoney(amountCents: number, currency: "CAD" = "CAD"): string` -> `"$3,200"`, `"−$3,200"`. `formatSignedMoney(amountCents: number, currency: "CAD" = "CAD"): string` -> `"+$8,000"`, `"−$640"`, `"$0"`. `formatDate(isoDate: string, style: "short" \| "weekday" = "short"): string` takes `"YYYY-MM-DD"` -> `"Nov 9"`, `"Fri, Oct 2"`. All three use `en-CA`, whole dollars rounded half away from zero, U+2212 for minus, and throw `RangeError` on a non-integer amount or a malformed date | Taking a `Date` for plain bank dates: `new Date("2026-10-02")` is UTC midnight, which shows as Oct 1 in Toronto. One `formatMoney(cents, { sign })` options bag: the sign rule is a meaning (balance versus money flow), and two names make it impossible to forget |
| 3. Messages layout | `frontend/messages/en.json`, nested by namespace (`{"Nav": {"dashboard": "Dashboard", ...}}`). `frontend/i18n/request.ts` uses `getRequestConfig` with a static `locale = "en"`, with no `[locale]` segment and no locale routing | next-intl's i18n routing (`/en/...`): changes every URL now, for French that only comes with Quebec. Adding it later is one middleware plus a segment move |
| 4. Sentry configuration | `@sentry/nextjs` from `npx @sentry/wizard@latest -i nextjs`, error monitoring only: no tracing (`tracesSampleRate` removed), no Session Replay, no Logs, no tunnel route. `dsn: process.env.NEXT_PUBLIC_SENTRY_DSN`, `environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT`, PII collection off (`sendDefaultPii: false`, or the installed SDK's equivalent, checked against its types before use). Source maps upload only when `SENTRY_AUTH_TOKEN` is set. Separate project `headroom-web` | Replay: it records the screen, and the screen shows bank balances. A tunnel route: one more public endpoint that forwards arbitrary bodies. The wizard's hard-coded DSN: staging and local need different values. User confirmed: separate web project |
| 5. Test-error page | Delete the wizard's `app/sentry-example-page` and `app/api/sentry-example-api`. Add `app/dev/sentry-check/page.tsx` with the AD-014 gate (`notFound()` in production): one button throws in a click handler (client), one calls a server action that throws (server) | Keeping the wizard's example page: a public crash route in production, which AD-010 already rejected for the API |

- Nothing else in this change is hard to reverse

## Criteria

### S1: Every page sits in the shell (P1)

The four destinations render inside the mockup's header and navigation, on a desktop and on a phone.

**Acceptance Criteria**

1. WHEN `/`, `/expected-payments`, `/alerts` or `/settings` loads THEN the app SHALL respond `200` with one `header` and one `main`, and the `main` SHALL contain an `h1` reading "Dashboard", "Expected payments", "Alerts" or "Settings" respectively
2. The header SHALL show the wordmark "Headroom" in Fraunces at 22px, weight 600, on viewports at least 1024px wide
3. The shell SHALL contain a `nav` labelled "Main" whose links, in order, are Dashboard (`/`), Expected payments (`/expected-payments`), Alerts (`/alerts`) and Settings (`/settings`)
4. WHILE a page is current, its nav link SHALL have `aria-current="page"`, a `--surface-active` background and weight 600, and every other nav link SHALL have no `aria-current`, a transparent background, `--ink-2` text and weight 500
5. The shell SHALL render each nav link at least 44px tall, with 10px corners and 15px text
6. WHILE the viewport is at least 1024px wide, the nav links SHALL be visible in the header and no menu button SHALL be rendered
7. WHILE the viewport is narrower than 1024px, the header SHALL show a 44 by 44px button named "Open menu" instead of the nav links
8. WHEN "Open menu" is activated THEN a Dialog titled "Menu" SHALL open with the same four links, in the same order, with the same `aria-current`
9. WHEN a link in the menu Dialog is activated THEN the app SHALL navigate to it and close the Dialog
10. WHERE a business name is passed to the shell, the header SHALL show the caption "Business" above the name on desktop, after a 1px divider, and the phone header SHALL show the name in place of the wordmark
11. WHERE no business name is passed, the header SHALL show no "Business" caption and no divider, and the phone header SHALL show the wordmark "Headroom". Until spec 11, no page passes one
12. WHILE the viewport is 375px wide, every shell page SHALL have no horizontal scroll (`document.documentElement.scrollWidth` equal to 375) and 16px side padding
13. WHILE the viewport is at least 1024px wide, the shell's content SHALL be at most 1344px wide, with 48px side padding
14. The header SHALL have a 1px `--border` bottom border, and the page SHALL keep the `--bg` background

**Independent test:** `npm run dev`, open `/alerts` at 1440px and at 375px, and use the menu.

### S2: The shell works with the keyboard alone and passes axe (P1)

**Acceptance Criteria**

15. WHEN a keyboard user presses Tab once from the top of any shell page THEN focus SHALL land on a "Skip to main content" link, which is visible while it has focus, and activating it SHALL move focus to `main`
16. WHEN a keyboard user keeps pressing Tab on a desktop viewport THEN focus SHALL reach the four nav links in order, each showing the spec 06 focus ring (2px solid `--accent`, offset 2px)
17. WHEN the menu Dialog is open THEN Tab SHALL cycle only through its links and close button, and Escape SHALL close it and return focus to "Open menu"
18. WHEN each of the four shell pages is scanned by `@axe-core/playwright` at 1440px and at 375px, and the open menu Dialog at 375px, THEN each scan SHALL report 0 violations

**Independent test:** `npx playwright test e2e/shell.spec.ts`.

### S3: All shell text comes from `messages/en.json` (P1)

**Acceptance Criteria**

19. The web app SHALL load messages through next-intl from `frontend/messages/en.json`, with locale `en`, and `<html>` SHALL keep `lang="en"`
20. The web app SHALL take every visible text node and every `aria-label` in the shell, the four placeholder pages, the loading state and the error state from a value in `messages/en.json`
21. The document `<title>` of the shell pages SHALL be "Headroom", taken from `en.json`
22. IF a component asks for a message key missing from `en.json` THEN `npm run build` SHALL fail, or a Vitest test over the shell SHALL fail, rather than ship the raw key

**Independent test:** change a nav label in `en.json` and watch it change in the header.

### S4: Shared loading and error states (P2)

Pages in the shell inherit one loading state and one error state, so the screens that come later start with both.

**Acceptance Criteria**

23. WHILE a shell page is loading, the `(app)` loading state SHALL render inside the shell with Skeleton blocks and `aria-busy="true"`
24. IF a shell page throws while rendering THEN the `(app)` error state SHALL render inside the shell, keeping the header and nav, with the title "We couldn't load this page", a danger icon marked `aria-hidden`, and a "Try again" button
25. WHEN "Try again" is activated THEN the error state SHALL call Next's `retry` (stable since Next 16.3) to re-fetch and re-render the page
26. IF a shell page throws while rendering THEN the error state SHALL report the error with `Sentry.captureException` once

**Independent test:** Vitest renders `loading.tsx` and `error.tsx` directly.

### S5: Money and dates read the way DESIGN.md says (P1)

**Acceptance Criteria**

27. The `formatMoney` function SHALL return `"$3,200"` for `320000`, and `"−$3,200"` for `-320000`, with U+2212 as the minus sign
28. The `formatMoney` function SHALL show whole dollars with comma grouping: `formatMoney(4230000)` returns `"$42,300"` and `formatMoney(0)` returns `"$0"`
29. The `formatMoney` function SHALL round half away from zero to the dollar: `320050` -> `"$3,201"`, `-320050` -> `"−$3,201"`, `320049` -> `"$3,200"`
30. IF the rounded amount is zero THEN `formatMoney` and `formatSignedMoney` SHALL return `"$0"`, never `"−$0"` or `"+$0"` (input `-49` and `49`)
31. The `formatSignedMoney` function SHALL return `"+$8,000"` for `800000` and `"−$640"` for `-64000`
32. IF `amountCents` is not a safe integer (`3200.5`, `NaN`, `Infinity`) THEN `formatMoney` and `formatSignedMoney` SHALL throw a `RangeError`
33. The `formatMoney`, `formatSignedMoney` and `formatDate` functions SHALL return no string containing a hyphen-minus (U+002D)
34. The `formatDate` function SHALL return `"Nov 9"` for `"2026-11-09"`, and `"Fri, Oct 2"` for `("2026-10-02", "weekday")`
35. The `formatDate` function SHALL return the same day for a plain date whatever the process time zone is: `formatDate("2026-10-02")` returns `"Oct 2"` with `TZ` set to `America/Vancouver` and to `Pacific/Auckland`
36. IF `isoDate` is not a real `YYYY-MM-DD` date (`"2026-02-30"`, `"10/02/2026"`, `""`) THEN `formatDate` SHALL throw a `RangeError`

**Independent test:** `npm test -- lib/format`.

### S6: Web errors reach Sentry (P1)

**Acceptance Criteria**

37. WHERE `NEXT_PUBLIC_SENTRY_DSN` is set, WHEN the "Throw a client error" button on `/dev/sentry-check` is clicked THEN an error event with the message `Headroom web Sentry check (client)` SHALL appear in the `headroom-web` Sentry project
38. WHERE `NEXT_PUBLIC_SENTRY_DSN` is set, WHEN the "Throw a server error" button on `/dev/sentry-check` is clicked THEN an error event with the message `Headroom web Sentry check (server)` SHALL appear in the `headroom-web` Sentry project
39. IF `/dev/sentry-check` is requested from a production build THEN the app SHALL respond `404`
40. The repository SHALL contain no `sentry-example-page` and no `sentry-example-api` route
41. The web app SHALL make every `Sentry.init` call take its DSN from `process.env.NEXT_PUBLIC_SENTRY_DSN`, set no `tracesSampleRate`, add no Replay integration, enable no logs, and turn PII collection off (Sentry 11 removed `sendDefaultPii`; its `dataCollection` option is turned off category by category). No DSN is written in source
42. WHERE `NEXT_PUBLIC_SENTRY_DSN` is not set, the app SHALL render every shell page without error and send nothing to Sentry
43. WHERE `SENTRY_AUTH_TOKEN` is not set, `npm run build` SHALL exit 0

**Independent test:** with the DSN in `frontend/.env.local`, click both buttons on `/dev/sentry-check` and query the Sentry API for the two messages.

## Out of scope

Product capabilities only. Process and harness rules live in AGENTS.md or as Observable `n/a`.

| Excluded | Why |
| --- | --- |
| The alert count in the nav ("Alerts (2)") | Needs alerts (spec 24). The link reads "Alerts" until then |
| The sync status line ("Updated today at 6:02 AM · 2 banks synced") | Needs bank sync (specs 14-15). Dashboard spec 26 adds it |
| The real business name and the user's name in the shell | Spec 11 passes the business name in, and spec 10 adds the user |
| Requiring login for shell pages | Spec 10 |
| Cents in transaction lists, long months ("December 27"), years in dates, time-of-day formatting | DESIGN.md asks for them, but spec 07 lists whole dollars and spelled-out months only. The screen that first needs each one adds it to `lib/format.ts` |
| French messages and locale switching | v1 is English only. French comes with Quebec |
| Sentry tracing, Session Replay, Logs, and user identification | Error tracking is what the spec asks for. Replay would record bank data on screen |
| Sentry Railway variables on staging | Needs the push go-ahead (see open questions). The Done-when item is proven locally |

## Assumptions

Defaults that are not already a numbered criterion. Drop a row once it is.

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Desktop / phone breakpoint for the nav | 1024px (Tailwind `lg`) | The desktop header holds the wordmark, the business, four links and later the sync status, which doesn't fit at 768px. The mockups are 1440px and 390px only | n |
| What the phone menu looks like | The spec 06 `Dialog`, which fills the screen at 375px, titled "Menu", with the four links stacked at 44px | No mockup of the open menu exists. The Dialog already traps focus and closes on Escape | n |
| Placeholder page body | The `h1` plus one sentence from `en.json` ("This page is coming soon.") | The spec says "empty placeholders". A heading keeps axe and the page title meaningful | n |
| Skip link | Added (AC 15), though the mockup doesn't show it | Four nav links come before the content on every page. It only shows when focused | n |
| Sentry environment name | `NEXT_PUBLIC_SENTRY_ENVIRONMENT`, `development` locally and `staging` on Railway | Same values as the API's `SENTRY_ENVIRONMENT` (AD-010). The browser needs the `NEXT_PUBLIC_` prefix | n |
| Web-side redaction | No `beforeSend`. PII collection off is enough for v1 | The web app holds no Plaid token. The Clerk cookie (spec 10) is excluded when PII collection is off. Revisit in spec 10 | n |
| Profile for this feature | `light` (no `tlc-spec-lean` profile in AGENTS.md) | Default. `ui` would have the Verifier compare the header with the mockup copy and layout, which suits a shell built from a mockup | n |

**Open questions:**

| # | Kind | Question | Until answered |
| --- | --- | --- | --- |
| 1 | blocks | Create the `headroom-web` Sentry project (Next.js platform), put its DSN in `frontend/.env.local` as `NEXT_PUBLIC_SENTRY_DSN`, and export `SENTRY_AUTH_TOKEN` / `SENTRY_ORG` / `SENTRY_PROJECT` for the API query | AC 37 and 38 cannot be proven |
| 2 | blocks go-live | Go-ahead to add the Sentry variables to the Railway `web` service and push | Staging web errors are not reported |

## Observable

Worksheet, not the review. `n/a` needs its reason. One row may group the same decision
across several routes.

| Surface | Decision | Landing |
| --- | --- | --- |
| screens `/`, `/expected-payments`, `/alerts`, `/settings` | empty state | n/a - placeholders with no data. The page is the empty placeholder the spec asks for (AC 1) |
| screens `/`, `/expected-payments`, `/alerts`, `/settings` | loading state | AC 23 |
| screens `/`, `/expected-payments`, `/alerts`, `/settings` | error state | AC 24, 25, 26 |
| screens `/`, `/expected-payments`, `/alerts`, `/settings` | unauthorised state | n/a - no login exists until spec 10, which makes every shell page require it |
| screens `/`, `/expected-payments`, `/alerts`, `/settings` | density and ordering | AC 3, 8 - mockup nav order |
| screens `/`, `/expected-payments`, `/alerts`, `/settings` | destructive action confirms | n/a - the shell has no destructive action |
| screens `/`, `/expected-payments`, `/alerts`, `/settings` | 375px layout, keyboard, touch targets | AC 5, 7, 12, 15, 16, 17, 18 |
| screen `/dev/sentry-check` | empty, loading, error, unauthorised states | n/a - a development-only page with no data. Throwing an error is its job. Absent in production (AC 39) |
| copy | structure, tone, what the reader does next | AC 20, 24 - DESIGN.md voice ("We couldn't load this page", "Try again") |
| all new routes | versioning, rate limits | n/a - HTML pages, not an API |

## Sources

- `context/specs/07-web-app-shell.md` - the build list and the three Done-when items
- `design/mockups/dashboard-desktop.dc.html`, `design/mockups/dashboard-phone.dc.html` - binding header and nav layout and copy
- `context/DESIGN.md` - binding money and date rules (true minus, plus for money in, spelled-out months) and tokens
