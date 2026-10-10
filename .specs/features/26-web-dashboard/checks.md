# 26 - The dashboard checks

Profile: light
Plan: `.specs/features/26-web-dashboard/plan.md`

38 checks in 4 slices · 3 one-way doors · 0 open, of which 0 block

`uv run` proofs run from `services/core`, `npx` proofs from `frontend`. API tests reuse the sample fixture of `tests/test_alerts_sample.py` (seed 0, the request clock and the handlers' `clock()` at 2026-09-26 Toronto) and spec 20's `cash_business()`. Vitest renders the real `app/(app)/page.tsx` with the dashboard loader mocked to a typed `Dashboard` (`frontend/tests/fixtures/dashboard-sample.ts`) holding AC 9's sample values: Operating checking 800000 (primary, ••2381) and Reserve savings 3430000 (••9025) at Harbor Community Bank, Business Visa owing 245000 (Summit Federal ••5530), Line of credit 2000000 available (••7702), the alert and its 3 fixes as spec 25 C10, and the 4 upcoming items. Playwright proofs need the stack from `playwright.config.ts` (API on 8100, Clerk test users). "The sample e2e owner" is a fresh Clerk user for whom the test runs `uv run python -m app.fixtures.load harbor_street --clerk-user-id <id>`. Its forecast is computed on the real clock, so the test reads that owner's `GET .../dashboard` with their session token to get the forecast-derived values. Every Playwright spec runs headed with `--headed` or in `--ui` for watching.

## Checks

### S1 - One call returns the dashboard's data · 9 files · 150 KB · ~38k

**C1** - On the sample with the minimum at 500000, `GET .../dashboard` answers `200` with exactly the top-level keys `as_of`, `currency`, `cash_on_hand_cents`, `available_credit_cents`, `minimum_balance_cents`, `projected_low`, `next_card_payment`, `accounts`, `connections`, `forecast`, `alerts`, `upcoming`. The values are `as_of` "2026-09-26", `currency` "CAD", `cash_on_hand_cents` 4230000, `available_credit_cents` 2000000, `minimum_balance_cents` 500000, `projected_low` `{"week_starts_on": "2026-11-09", "balance_cents": 315000}`, and `next_card_payment` with `date` "2026-10-08", `amount_cents` -245000 and the Business Visa's `account_id` (AC 1, AC 9, door 2)
Proof: `uv run pytest tests/test_dashboard_api.py -k "sample_summary"`

**C2** - On the sample, each `accounts` entry has exactly the keys `id`, `connection_id`, `institution_name`, `name`, `type`, `mask`, `currency`, `balance_cents`, `available_cents`, `included`, `primary`, `next_payment_on`. Operating checking (Harbor Community Bank, "2381", 800000, included, primary), Reserve savings ("9025", 3430000, included) and Line of credit ("7702", available 2000000) have `next_payment_on` null, and Business Visa (Summit Federal, "5530") has `next_payment_on` "2026-10-08". `connections` holds 2 entries with exactly `id`, `institution_name`, `status`, `last_synced_at`, both `last_synced_at` "2026-09-26T10:02:00Z" (AC 1, AC 9, door 2)
Proof: `uv run pytest tests/test_dashboard_api.py -k "sample_accounts"`

**C3** - On the sample, `forecast` has exactly `id`, `computed_at`, `opening_balance_cents` (4230000), `incomplete`, `weeks`. `weeks` holds 13 entries, each with exactly `number`, `starts_on`, `ends_on`, `end_balance_cents`, `low_cents`, `high_cents`, equal field for field to the same weeks of `GET .../forecast`. The week starting 2026-11-09 ends at 315000, and no `items` key is present (AC 1, AC 4, door 2)
Proof: `uv run pytest tests/test_dashboard_api.py -k "sample_forecast"`

**C4** - On the sample, `alerts` equals `GET .../alerts` (state `open`) item for item: 1 alert with 3 `fixes` in the order `pay_early`, `move_payment`, `draw_credit`. `upcoming` equals `GET .../upcoming?days=14` at the same clock: Payroll -1120000 on 2026-10-02, "Acme Co, invoice 1042" +800000 on 2026-10-06, Software subscriptions -64000 on 2026-10-07, Business Visa -245000 on 2026-10-08 (AC 6, AC 7, AC 9)
Proof: `uv run pytest tests/test_dashboard_api.py -k "sample_alerts_upcoming"`

**C5** - `cash_on_hand_cents` sums included `checking` and `savings` only. On `cash_business()` with Operating 100000, Reserve 50000 and an included savings account with a null balance, it is 150000. Excluding Reserve makes it 100000. An excluded checking account of 70000, a credit card owing 30000, and a line of credit with a balance of 90000 never count (AC 2)
Proof: `uv run pytest tests/test_dashboard_api.py -k "cash_on_hand"`

**C6** - `available_credit_cents`: two CAD lines of credit with 300000 and a null `available_cents` give 300000. A USD line of credit with 500000 is not added. No line of credit gives null (AC 3)
Proof: `uv run pytest tests/test_dashboard_api.py -k "available_credit"`

**C7** - On a hand-built snapshot whose weeks 4 and 9 both end at the lowest 120000, `projected_low` is week 4's `starts_on` with 120000. With two `card_payment` items, one dated yesterday and two dated later the same day, `next_card_payment` is the earliest one dated today or later, the lower `id` on a tie (AC 4)
Proof: `uv run pytest tests/test_dashboard_api.py -k "projected_low_and_card"`

**C8** - A business with a synced connection but no forecast snapshot answers `200` with `forecast`, `projected_low` and `next_card_payment` null, `upcoming` `[]`, `alerts` `[]`, and `accounts` and `cash_on_hand_cents` still filled. With no minimum stored, `minimum_balance_cents` is null (AC 5)
Proof: `uv run pytest tests/test_dashboard_api.py -k "no_forecast"`

**C9** - `alerts` holds only `open` alerts. After the sample's alert is dismissed, `alerts` is `[]`; an alert set to `resolved` is also absent (AC 6)
Proof: `uv run pytest tests/test_dashboard_api.py -k "open_only"`

**C10** - A signed-in user with no membership and an owner of another business get `404` problem details "Business not found." on `GET .../dashboard`, and the response body holds none of the business's account names. No token gets `401`, and a `business_id` of "not-a-uuid" gets `422` (AC 8, door 1)
Proof: `uv run pytest tests/test_dashboard_api.py -k "access_denied"`

**C11** - `app/dashboard.py` imports from `app.modules` only `*.service` modules (an AST walk over its imports finds no `models`, `repository`, `api` or `gaps`), and the route is listed in `contracts/openapi.json` under the path `/v1/businesses/{business_id}/dashboard` with the tag `dashboard`. Re-exporting gives no diff (door 1, door 2)
Proof: `uv run pytest tests/test_dashboard_api.py -k "read_router_imports"`
Proof: `uv run python -m app.export_openapi && git diff --exit-code ../../contracts/openapi.json`

### S2 - The dashboard shows where cash stands · 16 files · 170 KB · ~43k

**C12** - `npx shadcn@latest add chart` added `components/ui/chart.tsx` and `recharts` to `package.json` `dependencies`. The page's chart renders inside `ChartContainer` (`[data-slot="chart"]`) (door 3)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "chart container"`

**C13** - Rendering the page with the sample at 1280 px (`lg` matched): h1 "Cash flow", "Saturday, September 26 · Forecast through December 27", status line "Updated today at 6:02 AM · 2 banks synced" with the request clock at 2026-09-26 12:00 Toronto, "yesterday at 6:02 AM" at 2026-09-27, and "Sep 26 at 6:02 AM" at 2026-09-28. Below `lg`: "Forecast through December 27" alone and "Updated 6:02 AM · 2 banks synced" (AC 10, AC 11)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "header and status line"`

**C14** - At `lg` the summary cards read, in DOM order: "Cash on hand" "$42,300" "Operating + Reserve · 2 accounts"; "Projected low" "$3,150" "Week of Nov 9 · $1,850 below your minimum"; "Available credit" "$20,000" "Line of credit · not counted as cash"; "Next card payment" "$2,450" "Business Visa · due Thu, Oct 8". Below `lg`: "Week of Nov 9, below your minimum", "Line of credit, not counted as cash", and no "Next card payment" card (AC 12)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "summary cards"`

**C15** - With the minimum at 300000 the "Projected low" card says only "Week of Nov 9", and the same with the minimum null. With `available_credit_cents` null there is no "Available credit" card, and with `next_card_payment` null no "Next card payment" card (AC 13, AC 14)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "summary card variants"`

**C16** - The alert card shows "Cash gap", "Cash falls below your $5,000 minimum the week of Nov 9", and "Coastal Supply Co ($14,500) and Payroll ($11,200) leave in the same week, taking cash down to $3,150.". With 1 cause: "Coastal Supply Co ($14,500) leaves that week, taking cash down to $3,150.". With 4 causes: "Coastal Supply Co ($14,500), Payroll ($11,200) and 2 more payments leave in the same week, taking cash down to $3,150.". With 3: "... and 1 more payment leave ...". A cause with a null `counterparty` uses its `description` (AC 15)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "alert card body"`

**C17** - Top fix per kind, at `lg`: `pay_early` "Top fix: ask Birch & Co to pay their $9,600 invoice a week early. That keeps you above your minimum." (new lowest 1275000 ≥ 500000); `move_payment` alone "Top fix: move the $14,500 payment to Coastal Supply Co a week later."; `draw_credit` alone "Top fix: draw $2,000 from your Line of credit."; `financing` alone "Top fix: arrange $2,000 of short-term financing for the length of the gap.". A top fix with new lowest 400000 < 500000 has no "That keeps you above your minimum.", and below `lg` the sentence never shows. With no fixes, no "Top fix:" text (AC 16)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "top fix"`

**C18** - The alert card's link reads "See all 3 fixes" with `href` `/alerts/<alert id>`, "See the fix" with 1 fix, and "See details" with none. A "Dismiss" button is present (AC 17)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "alert links"`

**C19** - The dismiss action `POST`s `.../alerts/<id>/dismiss` with the auth headers, revalidates `/`, and returns `{ error: null }` on `200`. On `500` or a thrown fetch it returns `{ error: "dismissFailed" }`. On that error the card stays and shows "We couldn't dismiss this alert. Try again." (AC 18)
Proof: `npx vitest run tests/dashboard-actions.test.ts -t "dismiss"`
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "dismiss fails"`

**C20** - The chart section shows "13-week forecast" and "Projected balance at the end of each week". Its data has 14 points: "Today" at 4230000, then one per week labelled by `starts_on` at `end_balance_cents`, with range `[low_cents, high_cents]`. At `lg` the x labels are exactly "Today", "Sep 28", "Oct 12", "Oct 26", "Nov 9", "Nov 23", "Dec 7", "Dec 21"; below `lg` exactly "Today", "Oct 12", "Nov 9", "Dec 7". The labels "Your $5,000 minimum" (below `lg` "Min $5,000") and "Low $3,150" are shown, and the legend reads "Projected balance", "Likely range", "Your $5,000 minimum" (below `lg` "Your minimum"). With the minimum null there is no minimum label and no third legend entry (AC 19, AC 20)
Proof: `npx vitest run tests/dashboard-chart.test.tsx -t "points labels legend"`

**C21** - The chart's screen-reader summary reads "Your cash is projected to go from $42,300 today to $X by the week of Dec 21. The lowest point is $3,150 in the week of Nov 9, $1,850 below your $5,000 minimum.", where $X is week 13's `end_balance_cents` formatted. With the minimum at 300000: "..., above your $3,000 minimum.". With the minimum null, the second sentence ends "in the week of Nov 9." (AC 21)
Proof: `npx vitest run tests/dashboard-chart.test.tsx -t "text summary"`

**C22** - The accounts panel has "Accounts" and a "Manage" link to `/settings/banks`. "Counted as cash" lists Operating checking with "Primary" and "Harbor Community Bank ••2381" "$8,000", then Reserve savings "Harbor Community Bank ••9025" "$34,300", then "Cash on hand" "$42,300". "Credit · not counted as cash" lists Business Visa "Summit Federal ••5530" "$2,450" "Payment due Oct 8" (below `lg` "Due Oct 8"), and Line of credit "$20,000" "Available". An excluded savings account is not listed. With no credit accounts the credit group heading is absent (AC 22)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "accounts panel"`

**C23** - "Next 14 days" at `lg` is a table with the column headers "Date", "Description", "Account", "Type", "Amount" and the rows "Fri, Oct 2 | Payroll | Operating checking | Recurring, every 2 weeks | −$11,200", "Tue, Oct 6 | Acme Co, invoice 1042 | Operating checking | Expected | +$8,000", "Wed, Oct 7 | Software subscriptions | Operating checking | Recurring, monthly | −$640", "Thu, Oct 8 | Business Visa payment | Operating checking | Card payment | −$2,450". Below `lg`, no table, and each item shows "Fri, Oct 2 · Operating checking" above its description (AC 23)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "next 14 days"`

**C24** - Type words by `schedule`: `weekly` "Recurring, every week", `biweekly` "Recurring, every 2 weeks", `semimonthly` "Recurring, twice a month", `monthly` "Recurring, monthly", `quarterly` "Recurring, every 3 months". An item with a null `description` shows its `counterparty`. With `upcoming` `[]` the panel says "Nothing is due in the next 14 days." (AC 23, AC 24)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "upcoming words"`

**C25** - E2E, the sample e2e owner at 1280 px, with the minimum `PUT` to the forecast's `projected_low.balance_cents` + 500000 through the API: `/` shows "Cash on hand" "$42,300" "Operating + Reserve · 2 accounts", "Available credit" "$20,000", the accounts panel's 4 accounts with "$8,000", "$34,300", "$2,450", "$20,000", the status line "Updated Sep 26 at 6:02 AM · 2 banks synced", a "Projected low" amount equal to the API's `projected_low` formatted, one alert card per API alert, 13 week points plus "Today" in the chart, and one "Next 14 days" row per API `upcoming` item (AC 10-12, AC 15, AC 19, AC 22, AC 23)
Proof: `npx playwright test e2e/dashboard.spec.ts -g "C25"`

**C26** - E2E, the same owner: pressing "Dismiss" on the alert card removes it and shows the toast "Alert dismissed", and `GET .../alerts` then lists it under `state=dismissed` (AC 18)
Proof: `npx playwright test e2e/dashboard.spec.ts -g "C26"`

**C27** - E2E, the same owner: "Add expected payment" opens the dialog titled as on `/expected-payments`. Saving "Dashboard test payment", 1234 dollars money in, dated 3 days after today, closes it, and the "Next 14 days" list then shows "Dashboard test payment" with "+$1,234" (AC 25)
Proof: `npx playwright test e2e/dashboard.spec.ts -g "C27"`

### S3 - Every state has an answer · 6 files · 60 KB · ~15k

**C28** - The dashboard's loading UI renders skeletons for 4 summary cards, the chart and 2 panels inside an element with `aria-busy="true"` and `aria-label` "Loading" (AC 26)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "loading skeleton"`

**C29** - With `connections` `[]` the page renders only "No bank connected yet", "Connect your bank to see your 13-week forecast." and a link "Connect your bank" to `/onboarding/bank`: no summary cards and no chart (AC 27)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "empty no bank"`

**C30** - With a connection and `forecast` null, the page renders "Cash on hand" "$42,300", the accounts panel, and "Your forecast is on its way", "We're reading your bank data. This usually takes a minute or two." with a link "See progress" to `/onboarding/forecast`. There is no "Projected low" card, no chart, no "Next 14 days" and no alert card (AC 28)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "forecast not ready"`

**C31** - When the loader returns null (the API answered 500 or threw), the page renders "We couldn't load your dashboard.", "Check your connection and try again." and a "Try again" button whose click calls `router.refresh()` (AC 29)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "load fails"`

**C32** - With Harbor Community Bank `login_required` and an included account, `ReconnectBanner` renders before the summary cards, naming "Harbor Community Bank" with a "Reconnect" button, and the cards, chart and panels still render. With `forecast.incomplete` true and no `login_required` connection, the banner "Some bank data is more than 2 days old, so this forecast may be off." with a link "Go to bank settings" to `/settings/banks` renders instead. With both, only the reconnect banner (AC 30, AC 31)
Proof: `npx vitest run tests/dashboard-page.test.tsx -t "partial banners"`

**C33** - E2E: a fresh owner with a business and no bank sees "No bank connected yet" and the "Connect your bank" link on `/`. The sample e2e owner (synced 2026-09-26, so incomplete on the real clock) sees "Some bank data is more than 2 days old, so this forecast may be off." above the cards (AC 27, AC 31)
Proof: `npx playwright test e2e/dashboard.spec.ts -g "C33"`

### S4 - Fast, accessible, usable by keyboard and on a phone · 4 files · 30 KB · ~8k

**C34** - The production build (`npm run build`, `npm run start` on port 3100, API on 8100) serves `/` to the sample e2e owner in Chromium at 375×812 with CDP `Emulation.setCPUThrottlingRate` 4 and `Network.emulateNetworkConditions` latency 150 ms, download 1.6 Mbps, upload 750 kbps. On each of 3 consecutive loads, the chart's text summary is attached within 2000 ms of navigation start, measured as `performance.now()` when it appears. The test prints the 3 times (AC 32, Done when 2)
Proof: `npx playwright test -c playwright.perf.config.ts -g "C34"`

**C35** - E2E: axe (`@axe-core/playwright`, tags wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa) reports 0 violations on `/` for the sample e2e owner at 375 px and at 1280 px, and for the no-bank owner at 375 px, each run after the chart and the animations settle (AC 33, Done when 3)
Proof: `npx playwright test e2e/dashboard.spec.ts -g "C35"`

**C36** - E2E at 375 px, the sample e2e owner: `document.documentElement.scrollWidth` ≤ 375, and every visible `a` and `button` inside `main` has a bounding box at least 44×44 px (AC 34)
Proof: `npx playwright test e2e/dashboard.spec.ts -g "C36"`

**C37** - E2E keyboard, the sample e2e owner at 1280 px: from the skip link, Tab reaches "Add expected payment", then the alert card's "See all … fixes" link, then "Dismiss", then "Manage", in that order. Each focused element shows a 2px outline in `--accent` (computed `outline-width` "2px" and `outline-color` equal to the token's value). Pressing Enter on "Add expected payment" opens the dialog (AC 35)
Proof: `npx playwright test e2e/dashboard.spec.ts -g "C37"`

**C38** - With `prefers-reduced-motion: reduce` matched, the chart's Recharts series render with `isAnimationActive` false; without it, true (AC 36)
Proof: `npx vitest run tests/dashboard-chart.test.tsx -t "reduced motion"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /v1/businesses/{business_id}/dashboard` statuses (4) | 200 C1 · 401 C10 · 404 C10 · 422 C10 | - |
| `Dashboard` top-level keys (12) | C1, table-driven over all 12 | - |
| doors (3) | 1 C10, C11 · 2 C1-C4, C11 · 3 C12 | - |
| account groups (4 types) | `checking` C5, C22 · `savings` C5, C22 · `credit_card` C5, C22 · `line_of_credit` C6, C22 | - |
| summary cards (4) | cash on hand C14 · projected low C14, C15 · available credit C14, C15 · next card payment C14, C15 | - |
| cause counts in the alert body (4) | 1 C16 · 2 C16 · 3 C16 · 4 or more C16 | - |
| fix kinds (4) | `pay_early` C17 · `move_payment` C17 · `draw_credit` C17 · `financing` C17 | - |
| fix-count link wording (3) | 0 C18 · 1 C18 · 3 C18 | - |
| `schedule` words (5) | C24, table-driven over all 5 | - |
| `upcoming` sources (3) | `recurring_pattern` C23 · `expected_payment` C23 · `card_payment` C23 | - |
| minimum states (3) | below the low C14, C21 · at or above C15, C21 · unset C15, C20, C21 | - |
| page states (6) | populated C13-C25 · loading C28 · no bank C29, C33 · forecast not ready C30 · load failed C31 · partial C32, C33 | - |
| breakpoints (2) | below `lg` C13, C14, C17, C20, C22, C23, C36 · `lg` and up C13, C14, C17, C20, C22, C23, C25 | - |
| sync-time wording (3) | today C13 · yesterday C13 · older C13 | - |

- Claims naming a status code, route or response shape: C1-C4, C8-C10 - each proof calls the route through `TestClient`.
- Startup config: the router is mounted once, on `v1` in `main.py`; `TestClient(app)` uses the same assembly, so C10 crosses it. No subscription is added.
- Vitest proves copy and branches on the sample's typed `Dashboard`; the Playwright proofs (C25-C27, C33-C37) prove the real stack wiring and the screen rules. Neither stands in for the other.

## Swept

- validation: C10 - a malformed `business_id` is `422`; the route takes no body or query
- failure modes: C31 (the dashboard call fails), C19 (dismiss fails)
- idempotency: n/a - the route is a read, and dismissing an already dismissed alert is AD-099's existing `200`
- authorization: C10 - `404` for non-members and other businesses, `401` without a token
- concurrency: n/a - one read in one session; a forecast written between two dashboard loads is simply the next render's data
- data lifecycle: n/a - nothing stored or migrated
- dependency failure: C32 - a bank needing attention or stale data degrades to a banner, not an error
- state transitions: C26 - `open` to `dismissed` from the dashboard, through the existing route
- observability: existing - a failed load is reported to Sentry by the `lib/api` loaders' convention (spec 20, spec 23)

## Handoff

- S1 = 150 KB ~38k, all in `services/core`; S2 enters `frontend` at ~81k (schema.d.ts alone is 82 KB); S3 at ~96k; S4 at ~104k, under the 150k budget - one builder
