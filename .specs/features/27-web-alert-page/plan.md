# 27 - The alert page

## Problem

An owner who sees a cash gap alert on the dashboard (spec 26) gets one sentence about its causes and one fix. The alert's other fixes, each fix's new lowest balance, and the payment that arrives after the gap (specs 24 and 25) exist in the API and are on no screen. The dashboard's "See all 3 fixes" button already links to `/alerts/{id}`, and that link lands on nothing. So the owner sees there is a problem but not every way out of it, which is the product's promise ("suggests fixes", AGENTS.md). Spec 29's alert email will link to the same page.

The source gives the target as one phone mockup (`alert.dc.html`) on the sample (seed 0, today 2026-09-26, minimum $5,000): a projected low of $3,150 the week of Nov 9, short by $1,850; causes Coastal Supply Co −$14,500 (Thu, Nov 12, expected payment) and Payroll −$11,200 (Fri, Nov 13, every 2 weeks); Birch & Co, invoice 1057 +$9,600 arriving after (Tue, Nov 17); three fixes with new lowest balances $12,750, $17,650 and $5,150; a "Dismiss alert" button. It gives no figures beyond those.

When this ships, `/alerts/{alert_id}` shows one alert in full at phone and desktop widths, and dismissing it returns the owner to a dashboard without it.

## Flow

This reuses the alert route and its JSON (`GET .../alerts/{alert_id}`, AD-099 and AD-101), the dismiss server action `dismissAlert` in `app/(app)/actions.ts` (spec 26), the dashboard's copy helpers (`itemName`, `causesBySize`, `weekLabel`), the `(app)` layout with its `loading.tsx` and `error.tsx`, and `lib/format.ts`. No API change.

1. Browser requests `/alerts/{alert_id}` -> the page route (door 1), a server component: `auth.protect()`, then `loadBusinesses()` (exists) for the first business.
2. It calls `GET /v1/businesses/{business_id}/alerts/{alert_id}` (exists) through a loader in `lib/api/` (exists), with the session token.
3. `404` or `422` from the API -> the route's not-found state (streamed: HTTP 200 with `noindex`). Any other failure -> `(app)/error.tsx` (exists).
4. It renders the alert: header, two summary cards, causes and arrives-after, fixes, dismiss. Text from `messages/en.json` (exists), money through `lib/format.ts` (exists).
5. Out: "Dismiss alert" calls `dismissAlert` (exists) -> `POST .../alerts/{alert_id}/dismiss` (exists) -> `revalidatePath("/")`. On success the client navigates to `/`, where the dashboard (exists) lists only open alerts.

## Impact

| Front | What changes |
| --- | --- |
| web | a new route `app/(app)/alerts/[alertId]/` (page, not-found). `/alerts` stays the placeholder it is today |
| web | the dashboard's "See all N fixes" link (spec 26) starts landing on a real page. Its href does not change |
| web | `messages/en.json` gains an `AlertPage` namespace. `Dashboard.alert` keys are reused where the text is the same (the title), not copied |
| contracts | none: no route or schema changes, nothing to regenerate |
| stored data | none |

## Relations

`None - no stored-data shape change`

## Surface

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `GET /alerts/{alert_id}` (web page) | path `alert_id` | HTML: the alert page | `200`, `200` with `<meta name="robots" content="noindex">` and the not-found screen (unknown, foreign or malformed id; amended 2026-10-10, user decision: the `(app)` loading boundary streams, so Next cannot send `404`), `307` to `/sign-in` when signed out |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. The alert page's URL | `/alerts/{alert_id}`, the alert's UUID as the only path segment, in `app/(app)/alerts/[alertId]/page.tsx`. Spec 26's dashboard already links here, and spec 29's emails will, so once an email is sent this URL cannot move | `/alerts?id=`: a query string reads as a filter of the list, and `/alerts` is the list. A business id in the path (`/b/{business_id}/alerts/{id}`): no other web route carries one; the page resolves the business like the dashboard does |

- Nothing else here is hard to reverse. Layout, copy and the not-found wording are criteria, and their tests change with them.

## Criteria

### S1: The alert in full (P1)

The owner opens `/alerts/{id}` and sees what causes the gap and every fix.

**Acceptance Criteria**

1. WHEN an owner opens `/alerts/{id}` for an alert of their business THEN the page SHALL show a "← Dashboard" link to `/`, the eyebrow "Cash gap", and an `h1` "Cash falls below your {minimum} minimum the week of {week}" from `minimum_cents` and `lowest_week_starts_on` ("…your $5,000 minimum the week of Nov 9" on the sample).
2. The page SHALL show a "Projected low" card with `lowest_balance_cents` and "Week of {lowest_week_starts_on}" in the warning style, and a "Short by" card with `shortfall_cents` and "Below your minimum" ($3,150, Week of Nov 9; $1,850 on the sample).
3. The page SHALL list, under "What's causing it", every `cause` item largest absolute amount first, each as name, "{weekday date} · {type}" and the signed amount (Coastal Supply Co, Thu, Nov 12 · Expected payment, −$14,500; Payroll, Fri, Nov 13 · Every 2 weeks, −$11,200 on the sample).
4. WHERE the alert has an `arrives_after` item the page SHALL show it under "Arrives after the gap", inside the causes section, with its full `description` (or `counterparty` when the description is null), "{weekday date} · {type}" and the amount with a plus sign in the positive colour (Birch & Co, invoice 1057, Tue, Nov 17 · Expected payment, +$9,600).
5. The page SHALL take each row's type from the item: `expected_payment` "Expected payment"; `card_payment` "Card payment"; `recurring_pattern` with a `schedule` the schedule's text ("Every 2 weeks"); `recurring_pattern` with no `schedule` "Recurring".
6. The page SHALL list, under "Ways to fix it", one card per fix in the API's order, each with a title, one paragraph and a "New lowest balance" row with `new_lowest_balance_cents`.
7. WHEN a fix is `pay_early` THEN its card SHALL read "Ask {name} to pay a week early" and "Their {amount} invoice is due {original_date}. Ask them to pay by {date}. A small early-payment discount can help." ("Ask Birch & Co to pay a week early" / "Their $9,600 invoice is due Nov 17. Ask them to pay by Nov 10. …").
8. WHEN a fix is `move_payment` THEN its card SHALL read "Move the {name} payment by a week" and "Ask {name} to move the {amount} payment to {date}." ("Ask Coastal Supply Co to move the $14,500 payment to Nov 19.").
9. WHEN a fix is `draw_credit` THEN its card SHALL read "Draw {amount} on your line of credit" and "You have {available_cents} available. Repay it when {arrives-after name} pays." ("Draw $2,000 …" / "You have $20,000 available. Repay it when Birch & Co pays."), or "… Repay it on {repay_on}." when the alert has no `arrives_after` item.
10. WHEN a fix is `financing` THEN its card SHALL read "Arrange {amount} of short-term financing" and "Borrow it on {date} and repay it on {repay_on}, after the gap."
11. The fix cards SHALL name a payment by its `counterparty`, else its `description` up to the first comma (the dashboard's `itemName`, "Birch & Co").
12. WHEN a fix's `new_lowest_balance_cents` is at least `minimum_cents` THEN its "New lowest balance" row SHALL use the positive style with a check icon; IF it is below THEN the row SHALL use the warning style with no check icon.
13. The page SHALL format every amount with `lib/format.ts` in whole dollars, and take every string from `messages/en.json`.
14. IF the alert has no fixes THEN the page SHALL omit the "Ways to fix it" section.

**Independent test:** sign in as the sample owner (seed 0, minimum $5,000), open the dashboard's "See all 3 fixes", and compare the page with `alert.dc.html` at 375 px.

### S2: Dismiss returns to the dashboard (P1)

The owner dismisses the alert and lands on a dashboard without it.

**Acceptance Criteria**

15. WHILE the alert is `open` the page SHALL show a secondary "Dismiss alert" button, at least 44 px tall and full width on phones, with the note "This alert closes on its own when the gap leaves your forecast." under it.
16. WHEN the owner activates "Dismiss alert" THEN the page SHALL call `dismissAlert` once, disable the button and show "Dismissing…" until it returns.
17. WHEN the dismissal succeeds THEN the browser SHALL be at `/`, the toast "Alert dismissed" SHALL show, and the dashboard SHALL show no alert card with that alert's id.
18. IF the dismissal fails THEN the page SHALL stay on `/alerts/{id}`, re-enable the button and show "We couldn't dismiss this alert. Try again." in a `role="alert"` element.

**Independent test:** on the sample, open the alert, press "Dismiss alert", and see the dashboard with no alert card; reload `/` and it is still gone.

### S3: The page's other states (P1)

Every way the page can load has a screen.

**Acceptance Criteria**

19. WHILE the alert is `dismissed` the page SHALL show the alert with "You dismissed this alert on {dismissed_at date}. It comes back if the gap gets worse." in place of the dismiss button.
20. WHILE the alert is `resolved` the page SHALL show the alert with "This gap is no longer in your forecast." in place of the dismiss button.
21. IF the API answers `404` or `422` for the alert (unknown, another business's, or a malformed id) THEN the page SHALL render with `<meta name="robots" content="noindex">` (HTTP 200, as Next streams under `(app)/loading.tsx`; amended 2026-10-10, user decision) and show "We couldn't find this alert" with a link to the dashboard, inside the app shell.
22. IF loading the business or the alert fails for any other reason THEN the page SHALL show the existing error state ("We couldn't load this page" with "Try again").
23. WHILE the page loads the page SHALL show the existing `(app)` loading skeleton.
24. WHEN a signed-out visitor opens `/alerts/{id}` THEN the app SHALL redirect them to `/sign-in`.
25. The page SHALL fit 375 px with no horizontal scroll, and from 768 px up SHALL keep its content in one column at most 640 px wide.
26. The page SHALL be usable with the keyboard alone (back link, dismiss, in that order) and SHALL pass an axe check with no violations.

**Independent test:** open `/alerts/00000000-0000-0000-0000-000000000000` (404 state), a dismissed alert, and the page with the API stopped (error state).

## Out of scope

| Excluded | Why |
| --- | --- |
| The alerts list at `/alerts` | No v1 spec builds it; the nav link keeps its placeholder |
| Acting on a fix (moving a payment, drawing credit) | The fixes are suggestions; no spec writes them back to the forecast |
| Undismissing an alert | No route exists (AD-099); a dismissed alert reopens on its own when the gap grows (AD-096) |
| Hiding "Dismiss alert" from non-owners | Only owners exist until spec 31; the API already refuses a non-owner (AD-099) and AC 18 covers the failure |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Names on the causes vs the arrives-after row | Causes use the short name (`itemName`), the arrives-after row the full description (AC 3, AC 4, AC 11) | It is what the mockup shows ("Coastal Supply Co" vs "Birch & Co, invoice 1057"), and the invoice number tells the owner which payment to chase | y |
| The `move_payment` title | "Move the {name} payment by a week" (AC 8) | The mockup's "the supplier payment" is wrong when the largest cause is payroll or rent; no field says "supplier" | y |
| The `financing` and dismissed/resolved texts | AC 10, AC 19, AC 20 | The mockup shows neither; written to DESIGN.md's voice ("say what to do next") | y |
| A fix that doesn't clear the minimum | Warning style, no check icon (AC 12) | The mockup's green check means "this works"; showing it on a fix that leaves cash below the minimum would mislead | y |
| Desktop layout | One column, at most 640 px, in the app shell (AC 25) | The only mockup is a phone; the spec asks only that desktop works | y |
| The app header on phones | Kept: the page renders inside the `(app)` layout like every other screen | The mockup crops to the page body; spec 07's shell is on every app screen | y |
| No confirm before dismiss | None, as on the dashboard (spec 26) | The mockup has none, and dismissing isn't destructive: the alert reopens if the gap grows | y |

**Open questions:** none - all resolved or logged above. The user approved the plan with every default on 2026-10-10.

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| screen alert page | loading state | AC 23 |
| screen alert page | empty state | AC 14 (no fixes); an alert always has at least one cause (AD-096) |
| screen alert page | error state | AC 21, AC 22 |
| screen alert page | unauthorised state | AC 21 (another business's alert is 404), AC 24 (signed out) |
| screen alert page | density and ordering | AC 3 (largest first), AC 6 (API order), AC 25 |
| screen alert page | destructive action confirms | existing - no confirm, as on the dashboard (Assumptions) |
| screen alert page | phone and keyboard | AC 15, AC 25, AC 26 |
| copy on the page | structure, tone, what the reader does next | AC 1-10, AC 15, AC 19-21; every state ends with an action or a link |

## Sources

- `context/specs/27-web-alert-page.md` - the spec and its two "Done when" items
- `design/mockups/alert.dc.html` - the phone layout and copy (compared by the visual pass, as in spec 26)
- `.specs/STATE.md` AD-099, AD-101 - the alert and fix JSON the page renders
