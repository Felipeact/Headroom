# 27 - The alert page checks

Profile: light
Plan: `.specs/features/27-web-alert-page/plan.md`
Feature base: `310f6b5`

30 checks in 3 slices · 1 one-way door · 0 open, of which 0 block

`npx` proofs run from `frontend`, `uv run` proofs from `services/core`. Vitest renders the real `app/(app)/alerts/[alertId]/page.tsx` with `loadBusinesses` and the alert loader mocked, on spec 26's typed fixture `tests/fixtures/dashboard-sample.ts` (`ALERT`, `COASTAL`, `PAYROLL`, `FIXES`; the business in `America/Toronto`). Playwright proofs use spec 26's sample e2e owner (`loadSample`, then `raiseMinimum` so the sample has a cash gap on the real clock) and read the alert's values from that owner's `GET .../alerts/{id}`, because the forecast is computed on the real clock. Every Playwright spec runs headed with `--headed` or in `--ui` for watching.

## Checks

### S1 - The alert in full · 8 files · 70 KB · ~18k

**C1** - On `ALERT` the page shows a link named "Dashboard" with `href="/"`, the text "Cash gap", and exactly one `h1`, "Cash falls below your $5,000 minimum the week of Nov 9" (AC 1)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C1 header"`

**C2** - The "Projected low" card reads "$3,150" and "Week of Nov 9" and carries the `bg-warning-bg` class; the "Short by" card reads "$1,850" and "Below your minimum" and does not carry it (AC 2)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C2 summary cards"`

**C3** - With the items given in the order `PAYROLL`, `COASTAL`, the section "What's causing it" lists, in DOM order, "Coastal Supply Co" / "Thu, Nov 12 · Expected payment" / "−$14,500", then "Payroll" / "Fri, Nov 13 · Every 2 weeks" / "−$11,200" (AC 3)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C3 causes largest first"`

**C4** - On `ALERT`, after the causes and inside the same section, "Arrives after the gap" heads one row "Birch & Co, invoice 1057" / "Tue, Nov 17 · Expected payment" / "+$9,600", whose amount carries `text-positive`. With the `arrives_after` item removed, the text "Arrives after the gap" is absent. With its `description` null and `counterparty` "Birch & Co Ltd", the row reads "Birch & Co Ltd" (AC 4)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C4 arrives after"`

**C5** - A cause row's type reads, table-driven over 8 inputs: `expected_payment` "Expected payment"; `card_payment` "Card payment"; `recurring_pattern` with `weekly` "Every week", `biweekly` "Every 2 weeks", `semimonthly` "Twice a month", `monthly` "Every month", `quarterly` "Every 3 months"; `recurring_pattern` with `schedule` null "Recurring" (AC 5)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C5 row types"`

**C6** - On `ALERT` the section "Ways to fix it" holds exactly 3 fix cards, in the order pay early, move payment, draw credit, whose "New lowest balance" rows read "$12,750", "$17,650" and "$5,150" (AC 6)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C6 fix cards"`

**C7** - The `pay_early` card reads "Ask Birch & Co to pay a week early" and "Their $9,600 invoice is due Nov 17. Ask them to pay by Nov 10. A small early-payment discount can help." (AC 7, AC 11)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C7 pay early"`

**C8** - The `move_payment` card reads "Move the Coastal Supply Co payment by a week" and "Ask Coastal Supply Co to move the $14,500 payment to Nov 19." (AC 8, AC 11)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C8 move payment"`

**C9** - The `draw_credit` card reads "Draw $2,000 on your line of credit" and "You have $20,000 available. Repay it when Birch & Co pays." With the alert's `arrives_after` item removed, its paragraph reads "You have $20,000 available. Repay it on Nov 17." (AC 9)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C9 draw credit"`

**C10** - An alert whose fixes are `[FIXES.financing]` shows one card reading "Arrange $2,000 of short-term financing" and "Borrow it on Nov 9 and repay it on Nov 16, after the gap." (AC 10)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C10 financing"`

**C11** - With the `pay_early` fix's `counterparty` "Birch and Company Ltd", its title reads "Ask Birch and Company Ltd to pay a week early" (AC 11)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C11 counterparty first"`

**C12** - With `minimum_cents` 500000, a fix whose `new_lowest_balance_cents` is 515000 or 500000 has a "New lowest balance" row with `bg-positive-bg` and a check icon (`data-testid="fix-ok"`); one at 499999 has `bg-warning-bg` and no check icon (AC 12)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C12 new lowest style"`

**C13** - Rendered with every `messages/en.json` string replaced by `[[its key path]]`, every non-empty text node of the populated page contains `[[`, or is exactly a value from the alert: a payment name, an output of `formatDate`, or an output of `formatMoney` / `formatSignedMoney` (AC 13)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C13 text from messages"`

**C14** - An alert with `fixes: []` shows no "Ways to fix it" heading and no "New lowest balance" text, and still shows the causes (AC 14)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C14 no fixes"`

**C15** - The sample e2e owner opens the dashboard, follows the first alert card's "See all N fixes" link, and lands on `/alerts/{that alert's id}` with status `200` and the `h1` built from the API's `minimum_cents` and `lowest_week_starts_on`. At 375 px the page shows, in DOM order, the "Projected low" and "Short by" cards with the API's values, one row per API `cause` item, the arrives-after row when the API has one, one fix card per API fix with its `new_lowest_balance_cents`, and "Dismiss alert" (AC 1-6, door 1, Done when 1)
Proof: `npx playwright test e2e/alert-page.spec.ts -g "C15"`

### S2 - Dismiss returns to the dashboard · 3 files · 20 KB · ~5k

**C16** - WHILE the alert is `open` the page shows a button named "Dismiss alert" and the text "This alert closes on its own when the gap leaves your forecast." after it (AC 15)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C16 dismiss shown"`

**C17** - Activating "Dismiss alert" calls `dismissAlert("biz-1", ALERT.id)` exactly once; while that call is pending the button is disabled and named "Dismissing…" (AC 16)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C17 dismiss pending"`

**C18** - When `dismissAlert` resolves `{ error: null }`, `router.push("/")` is called once and the toast "Alert dismissed" is raised (AC 17)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C18 dismiss success"`

**C19** - When `dismissAlert` resolves `{ error: "dismissFailed" }`, `router.push` is not called, the button is enabled and named "Dismiss alert" again, and a `role="alert"` element reads "We couldn't dismiss this alert. Try again." (AC 18)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C19 dismiss fails"`

**C20** - The sample e2e owner on `/alerts/{id}` presses "Dismiss alert": the URL becomes `/`, "Alert dismissed" is visible, `#alert-{id}` is absent, and after a reload `#alert-{id}` is still absent while `GET .../alerts?state=dismissed` holds that id (AC 17, Done when 2)
Proof: `npx playwright test e2e/alert-page.spec.ts -g "C20"`

### S3 - The page's other states · 6 files · 40 KB · ~10k

**C21** - A `dismissed` alert with `dismissed_at` "2026-10-02T02:00:00Z" (Oct 1, 22:00 in Toronto) reads "You dismissed this alert on Oct 1. It comes back if the gap gets worse." and has no "Dismiss alert" button (AC 19)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C21 dismissed"`

**C22** - A `resolved` alert reads "This gap is no longer in your forecast." and has no "Dismiss alert" button (AC 20)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C22 resolved"`

**C23** - The alert loader maps the API's answer: `200` returns the alert; `404` and `422` return `"not_found"` without reporting to Sentry; `500` returns `null` and calls `Sentry.captureMessage` once; a thrown fetch returns `null` and calls `Sentry.captureException` once (AC 21, AC 22)
Proof: `npx vitest run tests/alert-loader.test.ts -t "C23"`

**C24** - The page calls `notFound()` when the loader returns `"not_found"`, and rejects (so `(app)/error.tsx` renders) when the loader returns `null` or `loadBusinesses` returns `null` or `[]` (AC 21, AC 22)
Proof: `npx vitest run tests/alert-page.test.tsx -t "C24 load outcomes"`

**C25** - A signed-in owner opening `/alerts/00000000-0000-0000-0000-000000000000` and `/alerts/not-a-uuid` gets a page with `<meta name="robots" content="noindex">` (HTTP 200: amended 2026-10-10 by user decision, Next streams under `(app)/loading.tsx` and cannot send `404`), the heading "We couldn't find this alert", a link "Go to the dashboard" with `href="/"`, and the app header's navigation. Another business's alert id is `404` "Alert not found." at the API (AC 21)
Proof: `npx playwright test e2e/alert-page.spec.ts -g "C25"`
Proof: `uv run pytest tests/test_alerts_api.py -k "test_alert_not_found"`

**C26** - The page renders inside `app/(app)/`, so `(app)/loading.tsx` is its loading state (the route has no `loading.tsx` of its own), and that state renders `aria-busy="true"` with the label "Loading" (AC 23)
Proof: `test -f "app/(app)/alerts/[alertId]/page.tsx" && test ! -e "app/(app)/alerts/[alertId]/loading.tsx"`
Proof: `npx vitest run "app/(app)/states.test.tsx" -t "C23 loading state"`

**C27** - A signed-out visitor opening `/alerts/00000000-0000-0000-0000-000000000000` ends on a URL whose path is `/sign-in` (AC 24)
Proof: `npx playwright test e2e/alert-page.spec.ts -g "C27"`

**C28** - On the sample alert at 375 px, `document.documentElement.scrollWidth` is at most 375, every visible link and button in `main` is at least 44 × 44 px, and "Dismiss alert" is as wide as the fix cards. At 1280 px the page's content column is at most 640 px wide (AC 15, AC 25)
Proof: `npx playwright test e2e/alert-page.spec.ts -g "C28"`

**C29** - On the sample alert, pressing Tab from the top reaches the "Dashboard" link before "Dismiss alert", each shows the 2px accent focus outline, and Enter on "Dismiss alert" lands on `/` (AC 26)
Proof: `npx playwright test e2e/alert-page.spec.ts -g "C29"`

**C30** - axe (tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) finds no violations on the sample alert at 375 and 1280 px, nor on the not-found state at 375 px (AC 26)
Proof: `npx playwright test e2e/alert-page.spec.ts -g "C30"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /alerts/{alert_id}` page statuses (3) | 200 C15 · 200 noindex not-found C25 · 307 C27 | - |
| doors (1) | 1 C15 | - |
| alert states (3) | `open` C16 · `dismissed` C21 · `resolved` C22 | - |
| alert item kinds (2) | `cause` C3 · `arrives_after` C4 | - |
| arrives-after presence (2) | present C4 · absent C4, C9 | - |
| row types (8) | C5, table-driven over all 8 | - |
| fix kinds (4) | `pay_early` C7 · `move_payment` C8 · `draw_credit` C9 · `financing` C10 | - |
| payment name source (2) | `counterparty` C11 · `description` before the comma C7, C8 | - |
| new lowest vs minimum (3 edges) | above C12 · equal C12 · below C12 | - |
| fix counts (3) | 0 C14 · 1 C10 · 3 C6 | - |
| alert loader outcomes (5) | 200 C23 · 404 C23 · 422 C23 · other status C23 · thrown C23 | - |
| page states (6) | populated C15 · loading C26 · not found C24, C25 · error C24 · signed out C27 · no fixes C14 | - |
| dismiss outcomes (2) | success C18, C20 · failure C19 | - |
| breakpoints (2) | 375 px C15, C28, C30 · 1280 px C28, C30 | - |

- Claims naming a status or route: C15, C20, C25, C27 - each proof drives the real stack in Playwright. The API's own `404` for a foreign alert is spec 24's test, run again here.
- Vitest proves copy and branches on the typed fixture; Playwright proves wiring, the real sample and the screen rules. Neither stands in for the other.
- Startup config: none - no route, router or subscription is added to the API.

## Swept

- validation: C25 - a malformed id is `422` at the API and the not-found screen on the page
- failure modes: C19 (dismiss fails), C23 and C24 (loading fails)
- idempotency: C17 - the button is disabled while a dismissal is pending; dismissing an already dismissed alert is AD-099's existing `200`
- authorization: C25 (another business's alert is the not-found screen, `404` at the API), C27 (signed out); dismiss is owner-only at the API (AD-099)
- concurrency: n/a - if the alert changes state in another tab, the dismiss route answers `200` (dismissed) or `409` (resolved), which land on C18 or C19
- data lifecycle: n/a - nothing stored or migrated
- dependency failure: C23, C24 - an API failure renders the error state, not a blank page
- state transitions: C20 - `open` to `dismissed` from this page, through the existing route; C21 and C22 render the other two states
- observability: C23 - a failed load is reported to Sentry, and a `404` is not

## Handoff

- S1 = 70 KB ~18k (the page, its components, `messages/en.json` at 30 KB, the fixture, the Vitest file); S2 adds ~5k at ~23k; S3 adds ~10k at ~33k, plus `schema.d.ts` read once (82 KB, ~21k) at ~54k, under the 150k budget - one builder
