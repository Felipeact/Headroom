# 26 - The dashboard

## Problem

An owner who signs in to Headroom lands on a placeholder page. The forecast (spec 21), the minimum balance (spec 23), the cash gap alert and its fixes (specs 24, 25), the accounts (spec 13) and the next 14 days of payments all exist in the API, and none of them is on a screen. To answer "Am I OK?" (DESIGN.md principle 4: "in two seconds"), an owner today has no answer at all: the product's core promise never reaches the person it's for. Specs 27 (alert page), 30 (digest) and 32 (analytics on dashboard use) assume the dashboard exists.

The source gives the target through two mockups on the sample (seed 0, today Saturday 2026-09-26): cash on hand $42,300 over Operating + Reserve, a projected low of $3,150 the week of Nov 9 ($1,850 below a $5,000 minimum), $20,000 of available credit, a $2,450 Business Visa payment due Oct 8, one cash gap alert with Birch & Co's early payment as its top fix, the 13-week chart, and 4 payments in the next 14 days. It gives one performance bar: under 2 seconds on a mid-range phone.

When this ships, `/` is the dashboard: one API call returns everything it shows, and the page renders it at phone and desktop widths, with its loading, empty, error and partial states.

## Flow

This reuses the existing module reads (`bank_sync.service.list_connections` and `needs_attention`, `forecasting.service.latest_forecast`, `upcoming_items`, `minimum_balance_amount` and `is_incomplete`, `alerts.service.list_alerts`), the existing dismiss route, the expected-payment dialog and server action from spec 20, and `ReconnectBanner` from spec 17. No new table, event or subscription.

1. Browser requests `/` -> `frontend/app/(app)/page.tsx` (exists, a placeholder today), a server component, calls the API through `lib/api/` (exists) with the session token.
2. `GET /v1/businesses/{business_id}/dashboard` -> `app/dashboard.py` (door 1): a read router that owns no tables and calls only the three modules' `service.py`, in one session.
3. It returns `Dashboard` (door 2): balances, accounts, connections, the minimum, the forecast weeks, the open alerts with their fixes, the next 14 days, and the computed summaries.
4. The page renders the summary cards, alert cards, the 13-week chart (Recharts through the shadcn `chart` component, door 3), the accounts panel, the next 14 days and the status line. All text comes from `messages/en.json`, and all money goes through `lib/format.ts`.
5. Out: "Dismiss" calls the existing `POST .../alerts/{alert_id}/dismiss` through a server action. "Add expected payment" opens the existing spec 20 dialog, whose action saves through the existing route. Both revalidate `/`.

## Impact

| Front | What changes |
| --- | --- |
| app | a new kind of file: `app/dashboard.py`, an app-level read router outside `modules/` (door 1). It is mounted on the authenticated `/v1` router in `main.py`. AGENTS.md's module list is unchanged, and the router imports only `service.py` files |
| domain | new term: `cash on hand` (the glossary term) is now computed in one place for display: the sum of `balance_cents` of included checking and savings accounts, null counted as 0. Before this, only the forecast's `opening_balance_cents` held it |
| domain | new term: `projected low` (the glossary term): the week with the lowest `end_balance_cents` of the latest forecast, the earliest on a tie. Spec 24's alert keeps its own `lowest_balance_cents`; both agree on the sample |
| web | `/` stops rendering `PlaceholderPage`. `e2e/home.spec.ts` and `e2e/shell.spec.ts` reach `/` and may assert placeholder text; they change with this. Step 5 of onboarding (AD-092) already sends the owner to `/` |
| web | a new dependency: `recharts`, through `npx shadcn@latest add chart` (door 3) |
| contracts | `contracts/openapi.json` and `frontend/lib/api/schema.d.ts` are regenerated: one new route and its schemas |
| stored data | none. Nothing to migrate or backfill |

## Relations

`None - no stored-data shape change`

## Surface

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `GET /v1/businesses/{business_id}/dashboard` | path `business_id` | `Dashboard` | `200`, `401`, `404`, `422` |

`Dashboard` = `as_of` (business-local today) · `currency` · `cash_on_hand_cents` · `available_credit_cents` (sum of line-of-credit `available_cents`; null with no line of credit) · `minimum_balance_cents` (null = unset) · `projected_low` (`week_starts_on`, `balance_cents`; null with no forecast) · `next_card_payment` (`account_id`, `date`, `amount_cents`; null when the forecast has none) · `accounts` [`id`, `connection_id`, `institution_name`, `name`, `type`, `mask`, `currency`, `balance_cents`, `available_cents`, `included`, `primary`, `next_payment_on` (credit cards only, else null)] · `connections` [`id`, `institution_name`, `status`, `last_synced_at`] · `forecast` (`id`, `computed_at`, `opening_balance_cents`, `incomplete`, 13 `weeks` [`number`, `starts_on`, `ends_on`, `end_balance_cents`, `low_cents`, `high_cents`]; null with no snapshot) · `alerts` [open `Alert`, exactly as AD-099 and AD-101] · `upcoming` [`ForecastItem`, exactly as AD-080, the next 14 days]. Money only as integer cents with `currency`. No display text from the API.

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. App-level read router (user decision 2026-10-09) | `services/core/app/dashboard.py` with its own `router = APIRouter(tags=["dashboard"])`, mounted with `v1.include_router(dashboard_router)` in `main.py`. It owns no tables and no events, imports only `app.modules.<name>.service` (never `models`, `repository` or another `api.py`), and defines its own response models. GET is any member: `require_member(*Role)` (AD-031, as the alert GETs in AD-099) | The route in `modules/alerts/api.py`: no import cycle, but alerts would own a screen's read model and carry it if the module is ever split out. A sixth module: a module owns tables, and this has none. Composing 5 calls in the web server: the spec asks for one API route, and 5 round trips from Railway's web service to the API cost the 2-second bar |
| 2. `Dashboard` JSON | The shape in `Surface`. `alerts` reuses `Alert` and `upcoming` reuses `ForecastItem` field for field. `forecast` carries weeks only, never its items (the 14 days are `upcoming`). A missing forecast is `forecast: null` with `200`, never `404` | `404` "Forecast not ready." as on `GET .../forecast` (AD-080): the dashboard still has balances and accounts to show (DESIGN.md "Partial"). Prose from the API: text lives in `messages/en.json` (AGENTS.md) |
| 3. Chart dependency | `npx shadcn@latest add chart`, which adds `components/ui/chart.tsx` and installs `recharts`. The forecast chart is built on its `ChartContainer` with the tokens from DESIGN.md "Forecast chart" | `npm install recharts` with hand-made wrappers: AGENTS.md says use the shadcn CLI for components it provides, and its chart reads the theme's CSS variables. Another chart library: DESIGN.md names Recharts |
| 3a. Generated chart trimmed (added while building, 2026-10-10; door 3 stands) | `components/ui/chart.tsx` as `npx shadcn@latest add chart` wrote it, minus the 5 class rules that restyle Recharts' default `[stroke='#ccc']` / `[stroke='#fff']` strokes; the forecast chart sets every stroke from tokens | Exempting `chart.tsx` from spec 06's colour-literal test (C23): that weakens a check. Keeping the rules: they fail C23 and style nothing this chart draws |

- To record in `.specs/STATE.md` when the checks are approved: door 1 as AD-102, door 2 as AD-103, door 3 as AD-104.
- Nothing else here is hard to reverse. Copy, layout, tick spacing and the empty-state wording are criteria, and their tests change with them.

## Criteria

### S1: One call returns the dashboard's data (P1)

**Acceptance Criteria**

1. WHEN a member calls `GET /v1/businesses/{business_id}/dashboard` THEN the system SHALL answer `200` with `Dashboard` as in `Surface`.
2. The system SHALL compute `cash_on_hand_cents` as the sum of `balance_cents` of the business's included `checking` and `savings` accounts, counting a null balance as 0, and never counting a credit card or line of credit.
3. The system SHALL compute `available_credit_cents` as the sum of `available_cents` of the business's `line_of_credit` accounts in the business's currency (null counted as 0), or null when it has no line of credit.
4. The system SHALL compute `projected_low` from the latest forecast as the week with the lowest `end_balance_cents`, the earliest on a tie, and `next_card_payment` as its first `card_payment` item dated from today (earliest `date`, then `id`).
5. IF the business has no forecast snapshot THEN the system SHALL answer `200` with `forecast`, `projected_low` and `next_card_payment` null, and `upcoming` empty.
6. The system SHALL return in `alerts` only the business's `open` alerts, ordered as AD-099, each with its `items` and `fixes`.
7. The system SHALL return in `upcoming` exactly what `GET .../upcoming?days=14` returns at the same moment.
8. IF the caller is not a member of the business, or the business doesn't exist THEN the system SHALL answer `404` problem details "Business not found." and read nothing else.
9. WHEN the sample (`23a`, seed 0, today 2026-09-26) is loaded and the minimum is set to 500000 THEN the dashboard SHALL hold `cash_on_hand_cents` 4230000, `available_credit_cents` 2000000, `minimum_balance_cents` 500000, `projected_low` 2026-11-09 / 315000, `next_card_payment` -245000 on 2026-10-08 for Business Visa, 1 open alert with 3 fixes, and the 4 `upcoming` items of spec 21 C40 (Done when 1).

**Independent test:** pytest: load the sample with the clock at 2026-09-26, `PUT` the $5,000 minimum, `GET .../dashboard`, and compare with the mockup numbers; a second business's owner gets `404`.

### S2: The dashboard shows where cash stands (P1)

Values are the sample's (AC 9). Below `lg` (1024px) the phone mockup's copy applies, from `lg` up the desktop mockup's.

**Acceptance Criteria**

10. WHEN the owner opens `/` THEN the page SHALL show the heading "Cash flow" and the line "Saturday, September 26 · Forecast through December 27" (`as_of`, then the last week's `ends_on`); below `lg`, only "Forecast through December 27".
11. The page SHALL show the status line "Updated today at 6:02 AM · 2 banks synced" (below `lg`: "Updated 6:02 AM · 2 banks synced"): the oldest `last_synced_at` of the connections, in the business's time zone, as "today at", "yesterday at" or "Oct 7 at", and the number of connections with a `last_synced_at`.
12. The page SHALL show the summary cards in this order: "Cash on hand" $42,300 "Operating + Reserve · 2 accounts"; "Projected low" $3,150 "Week of Nov 9 · $1,850 below your minimum" (below `lg`: "Week of Nov 9, below your minimum"); "Available credit" $20,000 "Line of credit · not counted as cash"; and, from `lg` only, "Next card payment" $2,450 "Business Visa · due Thu, Oct 8".
13. IF the projected low is at or above the minimum, or the minimum is unset THEN the "Projected low" card SHALL say only "Week of Nov 9" under the amount.
14. IF `available_credit_cents` is null THEN the page SHALL not show the "Available credit" card; IF `next_card_payment` is null THEN it SHALL not show the "Next card payment" card.
15. WHEN an alert is open THEN the page SHALL show one alert card for it: the label "Cash gap", the title "Cash falls below your $5,000 minimum the week of Nov 9", and the body "Coastal Supply Co ($14,500) and Payroll ($11,200) leave in the same week, taking cash down to $3,150." (user decision 2026-10-09: up to 2 `cause` items, largest first, each as `counterparty` or else `description` up to its first comma (user decision 2026-10-10: expected payments have no counterparty, so "Coastal Supply Co, quarterly order" reads "Coastal Supply Co"; the same name is used in AC 16); 1 cause: "... leaves that week, ..."; 3 or more: "A ($x), B ($y) and N more payments leave in the same week, ...").
16. WHEN the alert has fixes THEN its card SHALL show its first fix as "Top fix:" and a sentence for its kind: `pay_early` "ask Birch & Co to pay their $9,600 invoice a week early."; `move_payment` "move the $14,500 payment to Coastal Supply Co a week later."; `draw_credit` "draw $2,000 from your Line of credit."; `financing` "arrange $2,000 of short-term financing for the length of the gap.". From `lg` up it adds "That keeps you above your minimum." when the fix's `new_lowest_balance_cents` is at or above the minimum.
17. The alert card SHALL link to `/alerts/{alert_id}` with "See all 3 fixes" ("See the fix" for 1, "See details" for none) and offer the button "Dismiss".
18. WHEN the owner activates "Dismiss" THEN the page SHALL call the dismiss route, remove the card, and show the toast "Alert dismissed"; IF the call fails THEN it SHALL keep the card and show "We couldn't dismiss this alert. Try again." next to it.
19. The page SHALL show the "13-week forecast" chart, "Projected balance at the end of each week": a point for today at `opening_balance_cents` and one per week at its `end_balance_cents` labelled by `starts_on`; the likely range from `low_cents` to `high_cents`; the minimum as a dashed line labelled "Your $5,000 minimum" (below `lg`: "Min $5,000"); the lowest point labelled "Low $3,150"; x labels "Today" then every 2nd week from week 1 ("Sep 28", "Oct 12", ... "Dec 21"), below `lg` "Today", "Oct 12", "Nov 9", "Dec 7"; and the legend "Projected balance", "Likely range", "Your $5,000 minimum" (below `lg`: "Your minimum").
20. IF the minimum is unset THEN the chart SHALL show no minimum line and no minimum legend entry.
21. The chart SHALL carry a text summary for screen readers: "Your cash is projected to go from $42,300 today to {last week's end balance} by the week of Dec 21. The lowest point is $3,150 in the week of Nov 9, $1,850 below your $5,000 minimum." (at or above: "..., above your $5,000 minimum."; unset: the second sentence ends after "Nov 9.").
22. The page SHALL show the "Accounts" panel with a "Manage" link to `/settings/banks`: under "Counted as cash", each included checking and savings account (name, "Primary" on the primary one, "{institution} ••{mask}", balance), then "Cash on hand $42,300"; under "Credit · not counted as cash", each credit card ("$2,450", "Payment due Oct 8"; below `lg` "Due Oct 8") and each line of credit ("$20,000", "Available"). Excluded checking and savings accounts are not shown, and a group with no accounts is not shown.
23. The page SHALL show "Next 14 days" with each `upcoming` item in order: date "Fri, Oct 2", description (`description`, else `counterparty`; a `card_payment` as "Business Visa payment"), account name, type ("Recurring, every 2 weeks" / "every week" / "twice a month" / "monthly" / "every 3 months" by `schedule`; "Expected"; "Card payment"), and signed amount "−$11,200" / "+$8,000". From `lg` up it is a table with the columns "Date", "Description", "Account", "Type", "Amount"; below `lg` a list with "Fri, Oct 2 · Operating checking" above the description.
24. IF `upcoming` is empty THEN the "Next 14 days" panel SHALL say "Nothing is due in the next 14 days.".
25. The page SHALL offer "Add expected payment", which opens spec 20's add dialog; WHEN a payment is saved THEN the dashboard SHALL show the recomputed data on its next render.

**Independent test:** Vitest renders the real page component with a typed sample `Dashboard` and asserts the copy and order; Playwright opens `/` at 375px and 1280px.

### S3: Every state has an answer (P1)

**Acceptance Criteria**

26. WHILE the dashboard data loads THE page SHALL show skeletons in the shape of the summary cards, the chart and the two panels, with `aria-busy="true"`.
27. IF the business has no bank connection THEN the page SHALL show only the empty state: the title "No bank connected yet", "Connect your bank to see your 13-week forecast.", and the link "Connect your bank" to `/onboarding/bank`.
28. IF the business has a connection and `forecast` is null THEN the page SHALL show the summary cards it can fill and the accounts panel, and in place of the chart, the alerts and the next 14 days: "Your forecast is on its way", "We're reading your bank data. This usually takes a minute or two.", and the link "See progress" to `/onboarding/forecast`.
29. IF the dashboard call fails THEN the page SHALL show "We couldn't load your dashboard.", "Check your connection and try again.", and the button "Try again", which reloads the data.
30. IF a connection with an included account needs attention (`login_required`) THEN the page SHALL show spec 17's `ReconnectBanner` for it, naming the bank and offering "Reconnect", above the summary cards, and still show the rest.
31. IF `forecast.incomplete` is true and no connection needs attention THEN the page SHALL show the warning banner "Some bank data is more than 2 days old, so this forecast may be off." with the link "Go to bank settings" to `/settings/banks`.

**Independent test:** Vitest for each state from a typed `Dashboard`; Playwright for the empty state with a fresh owner and the partial state with the sample loaded on the real clock.

### S4: Fast, accessible, usable by keyboard and on a phone (P1)

**Acceptance Criteria**

32. WHEN the sample is loaded for a fresh owner and `/` opens on the production build (`npm run build`, `npm run start`) in Chromium at 375×812 with a 4× CPU slowdown and Lighthouse's mobile network (150 ms round trip, 1.6 Mbps down, 750 kbps up) THEN the chart's text summary SHALL be in the page within 2000 ms of navigation start, on each of 3 consecutive loads (Done when 2).
33. WHEN axe runs on `/` in the populated, empty and partial states at 375px and 1280px THEN it SHALL report no violations (Done when 3).
34. WHEN the viewport is 375px wide THEN the page SHALL have no horizontal scroll, and every link and button SHALL be at least 44×44 px.
35. WHEN the owner uses only the keyboard THEN Tab SHALL reach, in order, "Add expected payment", each alert card's link and "Dismiss", "Manage", and every other link and button on the page, each with the visible 2px `--accent` focus outline.
36. WHERE the user has set "reduce motion" the chart SHALL render without animation.

**Independent test:** Playwright: the 3 timed loads, axe, 375px scroll width, touch target sizes, and a Tab walk.

## Out of scope

| Excluded | Why |
| --- | --- |
| The account-shortfall alert, each account's lowest balance ("Lowest: −$3,200 on Fri, Oct 2", "No shortfall expected"), the "Overdraws Operating" tag, and the chart's account picker | Spec 26 "Not in v1"; `specs/later` |
| The alert page behind "See all 3 fixes" | Spec 27. Until it lands, `/alerts/{id}` is a 404 |
| "See all upcoming" | No spec builds a list of all upcoming payments; the link would lead nowhere |
| The alert count in the navigation ("Alerts (2)") | The shell's navigation is spec 07's and is shared by every page; the count needs an alerts read on every render. The alert page (spec 27) is the natural place |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Who may open the dashboard | Any member (`require_member(*Role)`), as the alert GETs | v1 has only owners; bookkeepers (spec 31) need the dashboard first of all | y (approved, 2026-10-09) |
| Which sync the status line reports | The oldest `last_synced_at`, and the count of connections synced at least once | The oldest is the honest "data as of"; the sample's two banks share 6:02 AM | y (approved, 2026-10-09) |
| Wording where the mockups can't be copied from data (AC 16, AC 21, AC 28, AC 31, AC 18) | The sentences in those criteria | No mockup shows these states; they follow DESIGN.md's voice and the spec 23 status copy | y (approved, 2026-10-09) |
| "Add expected payment" on the dashboard | Opens spec 20's dialog in place (AC 25) | The mockup puts the button on the dashboard; a link to `/expected-payments` would lose the owner's place | y (approved, 2026-10-09) |
| "Reconnect" on the dashboard | Reuses spec 17's `ReconnectBanner`, which opens Plaid Link in place | DESIGN.md "Partial" asks for a banner that names the bank and offers "Reconnect"; spec 17 already built it | y (approved, 2026-10-09) |
| "Mid-range phone" (Done when 2) | Lighthouse's mobile emulation: 4× CPU slowdown, 150 ms / 1.6 Mbps / 750 kbps, 375×812, production build, "rendered" = the chart summary is in the page (AC 32) | Lighthouse's mobile profile is the common stand-in for a mid-range phone. The e2e suite's `npm run dev` server compiles on request and can't measure this | y (approved, 2026-10-09) |
| The sample on a real clock (AC 32, AC 31) | Load it with `python -m app.fixtures.load harbor_street --clerk-user-id <fresh user>`; its 2026-09-26 sync makes `incomplete` true, which also proves the partial banner | The running app has no clock override; the mockup numbers are proved at 2026-09-26 in pytest and Vitest instead | y (approved, 2026-10-09) |

**Open questions:** none blocking. Both gray areas were decided by the user on 2026-10-09 (door 1: app-level read router; AC 15: names with amounts).

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| API `GET .../dashboard` | response shape | AC 1, AC 9, door 2 |
| API `GET .../dashboard` | error shape and codes | AC 8 (problem details, AD-008); `401` existing (every `/v1` route); `422` existing for a malformed `business_id` |
| API `GET .../dashboard` | who may call it | AC 8, door 1 |
| API `GET .../dashboard` | versioning | existing - under `/v1` (AGENTS.md) |
| API `GET .../dashboard` | rate limit | n/a - no route has one in v1 |
| screen `/` | empty state | AC 27 (no bank), AC 28 (no forecast yet), AC 24 (nothing due), AC 14 (no credit, no card), AC 20 (no minimum) |
| screen `/` | loading state | AC 26 |
| screen `/` | error state | AC 29, AC 18 (dismiss fails) |
| screen `/` | unauthorised state | existing - `auth.protect()` and the shell's no-business redirect (specs 10, 11); a non-member never reaches another business's data (AC 8) |
| screen `/` | density and ordering | AC 10-12, AC 19, AC 22, AC 23; the phone and desktop layouts follow their mockups |
| screen `/` | what a destructive action confirms | AC 18 - "Dismiss" is not destructive: a dismissed alert reopens when it worsens (AD-096), so no confirmation |
| screen `/` | partial state | AC 30, AC 31 |
| document: the alert card and chart summary text | wording, tone, what the reader does next | AC 15-17 (each card ends with an action), AC 21 |
| collection: the alert cards | ordering, duplicates | AC 6 - AD-099's order; one card per open alert |
| collection: the next 14 days | ordering, the exception that doesn't fit | AC 7, AC 23 (card payments get "payment" appended) |

## Sources

- `context/specs/26-web-dashboard.md` - the build list, "Not in v1", and Done when.
- `design/mockups/dashboard-desktop.dc.html`, `design/mockups/dashboard-phone.dc.html` - binding layout and copy, on the sample.
- `context/DESIGN.md` - "Forecast chart", "States", "Writing", accessibility.
