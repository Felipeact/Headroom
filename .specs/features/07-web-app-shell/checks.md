# 07 - App shell, translations, and formatting checks

Profile: light
Plan: `.specs/features/07-web-app-shell/plan.md`

43 checks in 6 slices · 5 one-way doors · 2 open, of which 1 blocks (C37, C38 need the `headroom-web` DSN)

Commands run from `frontend/`. `npx vitest run <file> -t "<name>"` runs a Vitest proof, and `npx playwright test <file> -g "<name>"` runs a Playwright proof. Playwright starts `npm run dev` on port 3000 (`playwright.config.ts`), so nothing else may be serving that port. Colours are the computed values of the AD-012 tokens: `--surface-active` `rgb(233, 229, 220)`, `--ink-2` `rgb(69, 79, 92)`, `--border` `rgb(226, 221, 211)`, `--bg` `rgb(245, 243, 238)`, `--accent` `rgb(29, 78, 137)`.

## Checks

### S1 - Every page sits in the shell · 12 files · 30 KB · ~8k

**C1** - `/`, `/expected-payments`, `/alerts` and `/settings` each answer `200`, with exactly one `header`, one `main`, and a `main` `h1` reading "Dashboard", "Expected payments", "Alerts" and "Settings" respectively (AC 1)
Proof: `npx playwright test e2e/shell.spec.ts -g "shell pages"`

**C2** - At 1440px wide, the header shows "Headroom" with computed `font-family` starting with Fraunces, `font-size` `22px` and `font-weight` `600` (AC 2)
Proof: `npx playwright test e2e/shell.spec.ts -g "wordmark"`

**C3** - The `nav` named "Main" contains exactly 4 links, in order: Dashboard `/`, Expected payments `/expected-payments`, Alerts `/alerts`, Settings `/settings` (AC 3)
Proof: `npx playwright test e2e/shell.spec.ts -g "nav links"`

**C4** - On each of the 4 pages, the link for that page has `aria-current="page"`, background `rgb(233, 229, 220)` and weight `600`, and the other 3 have no `aria-current`, background `rgba(0, 0, 0, 0)`, colour `rgb(69, 79, 92)` and weight `500` (AC 4)
Proof: `npx playwright test e2e/shell.spec.ts -g "current link"`

**C5** - Each nav link is at least 44px tall, with `border-radius` `10px` and `font-size` `15px` (AC 5)
Proof: `npx playwright test e2e/shell.spec.ts -g "link metrics"`

**C6** - At 1440px and at 1024px wide, the 4 nav links are visible and no button named "Open menu" is rendered (AC 6)
Proof: `npx playwright test e2e/shell.spec.ts -g "desktop nav"`

**C7** - At 375px and at 1023px wide, a button named "Open menu" is visible with a 44 by 44px box, and no link of the "Main" nav is visible (AC 7)
Proof: `npx playwright test e2e/shell.spec.ts -g "phone menu button"`

**C8** - At 375px on `/alerts`, activating "Open menu" opens a `dialog` named "Menu" holding exactly the 4 links in the C3 order, with `aria-current="page"` on Alerts only (AC 8)
Proof: `npx playwright test e2e/shell.spec.ts -g "menu dialog"`

**C9** - Activating "Settings" in the open menu Dialog moves the URL to `/settings`, shows the `h1` "Settings", and leaves no `dialog` open (AC 9)
Proof: `npx playwright test e2e/shell.spec.ts -g "menu navigates"`

**C10** - Rendered with `businessName="Harbor Street Plumbing"`, the shell header contains the caption "Business", the name in the desktop block, a divider element, and the name in the phone block where the wordmark would be (AC 10)
Proof: `npx vitest run components/shell/app-header.test.tsx -t "with business name"`

**C11** - Rendered with no business name, the header contains no "Business" caption, no divider, and "Headroom" in both the desktop and phone blocks. Each of the 4 live pages shows no "Business" text (AC 11)
Proof: `npx vitest run components/shell/app-header.test.tsx -t "without business name"`
Proof: `npx playwright test e2e/shell.spec.ts -g "no business yet"`

**C12** - At 375px wide, on each of the 4 pages, `document.documentElement.scrollWidth` is 375 and the shell's left and right padding are `16px` (AC 12)
Proof: `npx playwright test e2e/shell.spec.ts -g "phone layout"`

**C13** - At 1920px wide, the shell's content box is at most 1344px wide with `48px` left and right padding (AC 13)
Proof: `npx playwright test e2e/shell.spec.ts -g "desktop width"`

**C14** - The `header` has `border-bottom` `1px solid rgb(226, 221, 211)`, and the `body` background is `rgb(245, 243, 238)` (AC 14)
Proof: `npx playwright test e2e/shell.spec.ts -g "header border"`

### S2 - The shell works with the keyboard alone and passes axe · 1 file · 8 KB · ~2k

**C15** - On each of the 4 pages, the first Tab focuses a link "Skip to main content" whose box is visible (width and height above 1px) while focused, and Enter on it moves focus to `main` (AC 15)
Proof: `npx playwright test e2e/shell.spec.ts -g "skip link"`

**C16** - At 1440px, Tab after the skip link reaches Dashboard, Expected payments, Alerts, Settings in that order, each with `outline` `2px solid rgb(29, 78, 137)` and `outline-offset` `2px` (AC 16)
Proof: `npx playwright test e2e/shell.spec.ts -g "keyboard nav"`

**C17** - With the menu Dialog open at 375px, 10 presses of Tab keep focus inside the `dialog`, and Escape closes it with focus back on "Open menu" (AC 17)
Proof: `npx playwright test e2e/shell.spec.ts -g "menu focus"`

**C18** - `@axe-core/playwright` reports 0 violations on each of the 4 pages at 1440 by 900 and at 375 by 812, and on the open menu Dialog at 375 by 812 (AC 18)
Proof: `npx playwright test e2e/shell.spec.ts -g "axe"`

### S3 - All shell text comes from `messages/en.json` · 4 files · 8 KB · ~2k

**C19** - `i18n/request.ts`'s config resolves to locale `en` and messages deep-equal to `messages/en.json`, and `<html>` has `lang="en"` on `/` (AC 19)
Proof: `npx vitest run tests/i18n.test.ts -t "request config"`
Proof: `npx playwright test e2e/shell.spec.ts -g "html lang"`

**C20** - Every non-blank text node and every `aria-label` inside `body` (Next.js dev overlay excluded) on the 4 pages at 1440 and 375, and in the open menu Dialog, equals a string value in `messages/en.json`. The same holds for the rendered loading and error states (AC 20)
Proof: `npx playwright test e2e/shell.spec.ts -g "text from messages"`
Proof: `npx vitest run app/\(app\)/states.test.tsx -t "text from messages"`

**C21** - The document title on each of the 4 pages is "Headroom" (AC 21)
Proof: `npx playwright test e2e/shell.spec.ts -g "title"`

**C22** - Message keys are type-checked: a `t("noSuchKey")` call under `// @ts-expect-error` in `tests/i18n-keys.test.ts` makes `npm run typecheck` exit 0, which it could not if the unknown key were accepted (tsc reports an unused `@ts-expect-error`) (AC 22)
Proof: `npm run typecheck`
Proof: `npx vitest run tests/i18n-keys.test.ts -t "unknown key is a type error"`

### S4 - Shared loading and error states · 3 files · 6 KB · ~2k

**C23** - `app/(app)/loading.tsx` renders an element with `aria-busy="true"` containing at least 1 `[data-slot="skeleton"]` block (AC 23)
Proof: `npx vitest run app/\(app\)/states.test.tsx -t "loading state"`

**C24** - `app/(app)/error.tsx` exists beside `app/(app)/layout.tsx` (so Next renders it inside the shell), and renders the title "We couldn't load this page", one `svg[aria-hidden="true"]` and a button "Try again" (AC 24)
Proof: `npx vitest run app/\(app\)/states.test.tsx -t "error state"`

**C25** - Clicking "Try again" calls the `reset` prop exactly once (AC 25)
Proof: `npx vitest run app/\(app\)/states.test.tsx -t "try again resets"`

**C26** - Rendering the error state with an `Error` calls `Sentry.captureException` exactly once, with that error (AC 26)
Proof: `npx vitest run app/\(app\)/states.test.tsx -t "reports to sentry"`

### S5 - Money and dates read the way DESIGN.md says · 2 files · 5 KB · ~1k

**C27** - `formatMoney(320000)` is `"$3,200"` and `formatMoney(-320000)` is `"−$3,200"`, whose first character is U+2212 (AC 27)
Proof: `npx vitest run lib/format.test.ts -t "money whole dollars"`

**C28** - `formatMoney(4230000)` is `"$42,300"` and `formatMoney(0)` is `"$0"` (AC 28)
Proof: `npx vitest run lib/format.test.ts -t "money grouping"`

**C29** - `formatMoney(320050)` is `"$3,201"`, `formatMoney(-320050)` is `"−$3,201"`, `formatMoney(320049)` is `"$3,200"` (AC 29)
Proof: `npx vitest run lib/format.test.ts -t "money rounding"`

**C30** - `formatMoney(-49)`, `formatMoney(49)`, `formatSignedMoney(-49)`, `formatSignedMoney(49)` and `formatSignedMoney(0)` are all `"$0"` (AC 30)
Proof: `npx vitest run lib/format.test.ts -t "zero has no sign"`

**C31** - `formatSignedMoney(800000)` is `"+$8,000"` and `formatSignedMoney(-64000)` is `"−$640"` (AC 31)
Proof: `npx vitest run lib/format.test.ts -t "signed money"`

**C32** - `formatMoney` and `formatSignedMoney` each throw `RangeError` for `3200.5`, `NaN`, `Infinity` and `2 ** 53` (AC 32)
Proof: `npx vitest run lib/format.test.ts -t "rejects non-integer cents"`

**C33** - Over the inputs `-320050, -320000, -64000, -49, 0, 49, 320000` for both money functions, and `"2026-01-01", "2026-10-02", "2026-12-31"` in both date styles, no output contains U+002D (AC 33)
Proof: `npx vitest run lib/format.test.ts -t "no hyphen minus"`

**C34** - `formatDate("2026-11-09")` is `"Nov 9"` and `formatDate("2026-10-02", "weekday")` is `"Fri, Oct 2"` (AC 34)
Proof: `npx vitest run lib/format.test.ts -t "date styles"`

**C35** - With `process.env.TZ` set to `America/Vancouver` and then `Pacific/Auckland`, `formatDate("2026-10-02")` is `"Oct 2"` both times (AC 35)
Proof: `npx vitest run lib/format.test.ts -t "date ignores time zone"`

**C36** - `formatDate` throws `RangeError` for `"2026-02-30"`, `"10/02/2026"`, `""` and `"2026-10-2"` (AC 36)
Proof: `npx vitest run lib/format.test.ts -t "rejects malformed dates"`

### S6 - Web errors reach Sentry · 10 files · 20 KB · ~5k

**C37** - With `NEXT_PUBLIC_SENTRY_DSN` set, clicking "Throw a client error" on `/dev/sentry-check?run=<nonce>` produces an event in the `headroom-web` project whose message contains `Headroom web Sentry check (client) <nonce>`, found through the Sentry API within 60s (AC 37)
Proof: `bash ../.specs/features/07-web-app-shell/proofs.sh c37`

**C38** - With `NEXT_PUBLIC_SENTRY_DSN` set, clicking "Throw a server error" on `/dev/sentry-check?run=<nonce>` produces an event in `headroom-web` whose message contains `Headroom web Sentry check (server) <nonce>`, found through the Sentry API within 60s (AC 38)
Proof: `bash ../.specs/features/07-web-app-shell/proofs.sh c38`

**C39** - With `NODE_ENV=production`, the `/dev/sentry-check` page calls `notFound()`, and in development it renders. A production build served by `next start` answers `404` for `/dev/sentry-check` and `200` for `/`, `/expected-payments`, `/alerts` and `/settings` (AC 39)
Proof: `npx vitest run tests/dev-gate.test.ts -t "sentry check"`
Proof: `npm run build && node scripts/check-prod-gate.mjs`

**C40** - No path under `frontend/app/` contains `sentry-example-page` or `sentry-example-api` (AC 40)
Proof: `npx vitest run tests/sentry-config.test.ts -t "no example routes"`

**C41** - Each of `instrumentation-client.ts`, `sentry.server.config.ts` and `sentry.edge.config.ts` passes `dsn: process.env.NEXT_PUBLIC_SENTRY_DSN` and `sendDefaultPii: false`, and contains none of `tracesSampleRate`, `replayIntegration`, `enableLogs: true`. No file under `frontend/` outside `node_modules` and `.next` contains a Sentry DSN literal (`https://<key>@...ingest...sentry.io/<id>`) (AC 41)
Proof: `npx vitest run tests/sentry-config.test.ts -t "init options"`
Proof: `npx vitest run tests/sentry-config.test.ts -t "no dsn in source"`

**C42** - With `NEXT_PUBLIC_SENTRY_DSN` empty, the 4 pages load with no `pageerror`, and no request goes to a host containing `sentry` (AC 42)
Proof: `NEXT_PUBLIC_SENTRY_DSN= npx playwright test e2e/shell.spec.ts -g "no sentry without dsn"`

**C43** - With `SENTRY_AUTH_TOKEN` unset, `npm run build` exits 0 (AC 43)
Proof: `env -u SENTRY_AUTH_TOKEN npm run build`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| shell pages (4) | `/` C1 · `/expected-payments` C1 · `/alerts` C1 · `/settings` C1 | - |
| `GET /`, `/expected-payments`, `/alerts`, `/settings` statuses (1 each) | 200 C1, C39 | - |
| `GET /dev/sentry-check` statuses (2) | 200 C39 · 404 C39 | - |
| nav link states (2) | current C4 · not current C4 | - |
| header widths (4 edges) | 1440 C6 · 1024 C6 · 1023 C7 · 375 C7 | - |
| business name present (2) | given C10 · absent C11 | - |
| keyboard paths (3) | skip link C15 · nav order C16 · menu dialog C17 | - |
| axe scans (9) | `/` 1440 C18 · `/` 375 C18 · `/expected-payments` 1440 C18 · `/expected-payments` 375 C18 · `/alerts` 1440 C18 · `/alerts` 375 C18 · `/settings` 1440 C18 · `/settings` 375 C18 · menu dialog 375 C18 | - |
| group states (2) | loading C23 · error C24 | - |
| money sign cases (4) | positive C27 · negative C27 · zero C30 · rounds to zero C30 | - |
| money rounding edges (3) | .50 up C29 · .50 down for negatives C29 · .49 C29 | - |
| bad cents inputs (4) | fraction C32 · `NaN` C32 · `Infinity` C32 · unsafe integer C32 | - |
| date styles (2) | `short` C34 · `weekday` C34 | - |
| bad date inputs (4) | impossible day C36 · numeric order C36 · empty C36 · unpadded C36 | - |
| Sentry runtimes (2) | client C37 · server C38 | - |
| startup config: Sentry init (3 assemblies) | `instrumentation-client.ts` C41 · `sentry.server.config.ts` C41 · `sentry.edge.config.ts` C41 | - |
| startup config: next-intl (2 assemblies) | `next.config.ts` plugin C19 (Playwright boots it) · `app/layout.tsx` provider C20 | - |
| Landing doors (5) | 1 routes C1 · 2 format API C27 · 3 messages layout C19 · 4 Sentry config C41 · 5 test page C39 | - |

- Claims naming a status code or route: C1, C39. Both cross the HTTP boundary (Playwright `page.goto` response, and `fetch` against `next start`).
- C10 is proven at the component level only: no page passes a business name until spec 11, so no route can show it.
- C24 proves the error state's placement by file location; Next's segment rules put `error.tsx` inside the sibling `layout.tsx`. No route throws on purpose.
- No other check claims more than the cases its proof exercises.

## Swept

- validation: C32, C36 - `lib/format.ts` rejects non-integer cents and malformed dates
- failure modes: C24, C25, C26 - a page that throws shows the error state, can retry, and is reported
- idempotency: n/a - nothing is written; every page is a read
- authorization: C39 - the Sentry test page is absent from every production build. No login exists until spec 10
- concurrency: n/a - no shared state, and no request does work
- data lifecycle: n/a - no stored data
- dependency failure: C42 - with no DSN, Sentry stays off and pages still render. C43 - a missing Sentry token does not break the build
- state transitions: C8, C9, C17 - menu closed, open, then closed by navigation or Escape
- observability: C26, C37, C38 - client, server and boundary errors reach Sentry

## Handoff

- Read once: plan + checks (~40 KB), the next-intl and Sentry setup docs and installed types (~40 KB), the dashboard mockup headers (~4 KB), the spec 06 Dialog and Skeleton (~8 KB) = ~90 KB. Write: S1 30 KB, S2 8 KB, S3 8 KB, S4 6 KB, S5 5 KB, S6 20 KB = ~77 KB. Total ≈ 167 KB / 4 ≈ 42k, plus tool output from npm, the Sentry setup, build and Playwright (~50k) ≈ 92k, under the 150k budget, so one builder
- Mechanism: one builder (no ask, under budget)
