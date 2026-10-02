# 06 - Design system in the web app

## Problem

The web app still wears the create-next-app and shadcn starter theme: grey `oklch` colours, a
`.dark` palette DESIGN.md never defines, Geist fonts, and one `button.tsx` at 32px tall with 8px
corners. DESIGN.md asks for 44px buttons, 10px corners, and a cream-and-navy palette in Fraunces
and IBM Plex Sans. Every screen spec after this one (07 shell, 11-13 onboarding, 17, 20, 26, 27)
is told to "use only the tokens and the components in `components/ui/`". Today those tokens
don't exist, and only one component does. The first screen built now would either hard-code hex
values, which AGENTS.md forbids, or invent its own look-alikes. Then every later screen copies
whichever it chose.

When this ships, every DESIGN.md colour is a Tailwind utility (`bg-surface`, `text-ink-2`). The 13
components the spec lists are installed and themed. The development page `/dev/components`
renders the Components mockup from those components, so a reviewer can compare the two side by
side. The source gives no evidence beyond the roadmap's build order.

## Flow

This reuses the shadcn CLI and `components.json` from spec 01 to generate every component. It only
re-themes generated files and never hand-writes a component the CLI provides.

1. `npx shadcn@4.21.1 add button card input label select switch radio-group toggle-group dialog badge skeleton sonner` -> `frontend/components/ui/` (exists). Writes the generated files and their dependencies. The existing `button.tsx` is kept, not overwritten.
2. `frontend/app/globals.css` (exists): DESIGN.md tokens in `:root` (door 1), mapped into `@theme inline` and aliased by the shadcn semantic variables. The starter `oklch` values and the `.dark` block are removed.
3. `frontend/app/layout.tsx` (exists): `next/font/google` Fraunces and IBM Plex Sans replace Geist and feed `--font-sans` / `--font-heading`.
4. `frontend/components/ui/*` (exists after hop 1): re-themed through the tokens. Button and badge variants are renamed to DESIGN.md's names (doors 2, 3).
5. `frontend/app/dev/components/page.tsx` (new, gated by door 5): renders the mockup's sections from hop 4's components. Returns 404 in a production build. Three client components sit beside it: the swatch reads each caption's hex from its CSS variable, so `globals.css` stays the only place a hex value is written; then the segmented control and the dialog-and-toast demo.
6. out: `npm run dev` serves `/dev/components`. The Playwright run (`@axe-core/playwright`, door 4) and a Vitest guard over source files prove the result.

## Impact

| Front | What changes |
| --- | --- |
| domain | new terms: the 22 DESIGN.md token names become Tailwind colour names (`bg-bg`, `bg-surface`, `text-ink`, `text-ink-2`, `border-border-input`, `bg-warning-bg`, ...). Every later screen spells colours with these. |
| domain | existing term: shadcn `--accent` meant a neutral hover fill and now means the brand blue `#1D4E89` (door 1). The generated components that read `bg-accent` / `text-accent-foreground` for a hover or highlighted item (select items, toggle hover) are re-pointed to `--surface-muted` in hop 4. No hand-written code reads it yet. |
| domain | existing term: Button `variant="default"` and `variant="outline"` change meaning (door 2). Nothing outside `components/ui/` imports Button yet. |
| theme | the `.dark` palette is deleted. `@custom-variant dark (&:is(.dark *))` stays, so the `dark:` classes inside generated components never fire. Without that line, Tailwind v4 would apply them under the OS dark setting. |
| starter page | `app/page.tsx` stays until spec 07, but its three hex classes (`hover:bg-[#383838]`, `dark:hover:bg-[#ccc]`, `dark:hover:bg-[#1a1a1a]`) are swapped for tokens so the no-hex guard covers all of `app/` |
| dependencies | new runtime dependency `sonner` from `shadcn add`. `shadcn add` also installed `next-themes` for the generated `sonner.tsx`'s theme switching; the themed `sonner.tsx` pins `theme="light"`, so `next-themes` was uninstalled. One new dev dependency: `@axe-core/playwright` (door 4) |
| CI | none - CI runs lint, typecheck, Vitest and build (AD-004). The new Vitest guard runs there. Playwright stays local, as in spec 04 |
| stored data | nothing to migrate |

## Relations

None - no stored-data shape change

## Surface

Only routes this adds or whose signature changes.

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `GET /dev/components` | none | HTML page rendering the Components mockup | `200` when `NODE_ENV` is `development`, `404` in a production build |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. Token names | `:root { --bg: #F5F3EE; --surface: #FFFFFF; ... --danger-strong: #5E1111 }`, the 22 DESIGN.md names verbatim. `@theme inline { --color-bg: var(--bg); --color-surface: var(--surface); ... }`. shadcn variables alias them: `--background: var(--bg)`, `--foreground: var(--ink)`, `--card: var(--surface)`, `--primary: var(--accent)`, `--primary-foreground: var(--surface)`, `--muted: var(--surface-muted)`, `--muted-foreground: var(--ink-3)`, `--input: var(--border-input)`, `--ring: var(--accent)`, `--destructive: var(--danger-text)`. `--accent` is DESIGN's blue. | A prefix (`--hr-accent`): contradicts the literal names DESIGN.md says to define. Keeping shadcn's neutral `--accent` beside the brand one: one name would mean two colours, and `bg-accent` would silently pick the wrong one. |
| 2. Button variant names | `variant: "primary" \| "secondary" \| "outline" \| "link" \| "destructive" \| "ghost"`, default `"primary"`. `size: "default" \| "icon"`, both at least 44px. `ghost` is kept only for the dialog's icon-only close button. | shadcn's names (`default`, `outline`, ...): shadcn's `outline` is DESIGN's *secondary* look, so `outline` would mean different buttons in the docs and in the code. shadcn's `xs`/`sm`/`lg` sizes: all under 44px, which DESIGN.md forbids. |
| 3. Badge variant names | `variant: "neutral" \| "muted" \| "positive" \| "warning" \| "danger"` (Primary, Recurring/Expected, Synced, Needs attention, Overdraws) | Content names (`synced`, `recurring`): every new label would need a new variant |
| 4. Dev dependency | `npm install -D @axe-core/playwright` (exact version recorded by npm in `package-lock.json`). Tests use `new AxeBuilder({ page }).analyze()`. | Injecting `axe-core` by hand with `page.addScriptTag`: re-implements the official Deque integration, and every later screen's axe check copies it |
| 5. Dev-only page gate | `if (process.env.NODE_ENV === "production") notFound()` at the top of `app/dev/components/page.tsx`. Later `/dev/*` pages copy it. | `NEXT_PUBLIC_SHOW_DEV_PAGES` flag: a new Railway variable for a page no client needs. A `proxy`/middleware matcher: more machinery for one route. User confirmed: hidden on staging too. |
| 6. Colours the mockup uses outside the token table | Near-duplicates fold into existing tokens: `#D9CFC8` -> `--border-input`, `#8A4B00` -> `--warning-text`, `#3D2E1C` -> `--warning-strong`, `#3F2A2A` -> `--danger-strong`. Two new tokens for the colours DESIGN.md already names for the chart: `--line-soft: #ECE8E0` (skeleton blocks, gridlines) and `--line-strong: #C9C2B5` (switch off-track, zero line). They are added to DESIGN.md's table in a separate commit. Shadow `0 1px 2px rgba(22, 32, 43, 0.14)` becomes `--shadow-selected`. | Six new tokens, one per mockup hex: four of them differ from an existing token by a shade nobody can see, and that grows the palette DESIGN.md says not to grow. Hard-coding them in the page: breaks the "no hex in components" criterion. User confirmed: fold 4, add 2. |

- Nothing else in this change is hard to reverse

## Criteria

### S1: The theme is DESIGN.md (P1)

Any element styled with a token utility renders DESIGN.md's value, in DESIGN.md's fonts.

**Acceptance Criteria**

1. The web app SHALL define all 22 DESIGN.md colour tokens in `app/globals.css` `:root`, each with its DESIGN.md hex value (`--bg` `#F5F3EE` through `--danger-strong` `#5E1111`), plus `--line-soft` `#ECE8E0` and `--line-strong` `#C9C2B5` (door 6)
2. The web app SHALL expose each of those 24 tokens as a Tailwind colour, so `bg-<token>`, `text-<token>` and `border-<token>` compile to `var(--<token>)`
3. The web app SHALL keep `app/globals.css` free of any `oklch(` value and any `.dark {` block
4. WHILE the operating system prefers a dark colour scheme, the `/dev/components` body SHALL keep background `rgb(245, 243, 238)` and text colour `rgb(22, 32, 43)`
5. The `/dev/components` body text SHALL use the IBM Plex Sans family loaded by `next/font/google`, with `Segoe UI`, `system-ui` and `sans-serif` after it in the computed `font-family`
6. The `/dev/components` `h1` SHALL use the Fraunces family loaded by `next/font/google`, with `Georgia` and `serif` after it in the computed `font-family`
7. The web app SHALL import no Geist font in `app/layout.tsx`
8. The `body` SHALL have computed `font-variant-numeric` `tabular-nums`

**Independent test:** run `npm run dev`, open `/dev/components` with the OS in dark mode, and inspect the body's colours and fonts.

### S2: The components look and behave as DESIGN.md says (P1)

The 13 listed components exist as generated, re-themed to the tokens.

**Acceptance Criteria**

9. The web app SHALL contain, in `components/ui/`, the files the shadcn CLI generates for `button card input label select switch radio-group toggle-group dialog badge skeleton sonner`
10. The Button SHALL offer the variants `primary`, `secondary`, `outline`, `link` and `destructive`. On `/dev/components`, each SHALL render at least 44px tall, with 10px corners and 15px text, and the colours from the Components mockup (primary: `--accent` fill with white text; secondary: white with a `--border-input` border; outline: white with an `--ink` border; link: `--accent` text; destructive: `--danger-text` text with a `--danger-border` border)
11. WHEN a primary Button is disabled THEN it SHALL render with background `--surface-active` and text `--ink-3`, not with reduced opacity
12. The Input and the Select trigger SHALL render 48px tall, with 16px text, 10px corners, and a 1px `--border-input` border
13. IF an Input has `aria-invalid="true"` THEN it SHALL render a 2px `--danger-text` border, and its error text SHALL be the element its `aria-describedby` names
14. The web app SHALL give each Switch, radio option and toggle-group item on `/dev/components` a clickable area of at least 44 by 44px
15. WHEN a toggle-group item is pressed THEN it SHALL render with a `--surface` background and the `--shadow-selected` shadow, and the other items SHALL be transparent
16. The Badge SHALL offer the variants `neutral`, `muted`, `positive`, `warning` and `danger`, each with the background and text colours of the matching mockup badge, and 6px corners
17. The Card SHALL render with a `--surface` background, a 1px `--border` border and 14px corners
18. WHILE the viewport is at least 640px wide, an open Dialog SHALL be 480px wide and horizontally centred
19. WHILE the viewport is 375px wide, an open Dialog SHALL fill the viewport's width and height
20. WHEN a toast is shown THEN it SHALL stay for 4000ms, with a `--surface` background, even WHILE the operating system prefers a dark colour scheme
21. WHEN any focusable element on `/dev/components` receives keyboard focus THEN it SHALL show a 2px solid `--accent` outline offset by 2px
22. WHILE the operating system asks for reduced motion, the Dialog and toast SHALL open with no animation (computed `animation-duration` and `transition-duration` of `0s` or less than `0.01ms`)
23. The web app SHALL keep every file under `frontend/components/` and `frontend/app/` other than `app/globals.css` free of any hex colour literal or an `rgb(`, `rgba(`, `hsl(` or `oklch(` colour function

**Independent test:** on `/dev/components`, tab through every control, open the dialog and fire the toast, then run `npm test` for the no-hex guard.

### S3: `/dev/components` matches the mockup (P1)

A reviewer can put the page next to `components.dc.html` and find the same sections, in the same order, with the same copy.

**Acceptance Criteria**

24. WHEN `/dev/components` loads in development THEN it SHALL respond `200` with the `h1` "Components and states", followed by the `h2` sections Colors, Type, Buttons, Form controls, Badges, Alert cards and States, in that order
25. The Colors section SHALL show 14 swatches, each with the mockup's name and `--token · #HEX` caption, in the mockup's order
26. The Type section SHALL show the mockup's 7 rows (Display, Figure, Title, Section, Body, Caption, Eyebrow), each sample at the size and weight its label names
27. The Buttons section SHALL show the mockup's 6 buttons with their mockup labels (Primary, Secondary, Outline, Text link, Destructive, Disabled)
28. The Form controls section SHALL show the Business name input with its hint, the Amount input with `$` inside and its error "Enter an amount greater than $0.", the Province or territory select, two "Counts as cash" switches (on and off), the two radio options, and the Money out / Money in segmented control
29. The Badges section SHALL show the mockup's 6 badges with their labels (Primary, Recurring, Expected, Synced, Needs attention, Overdraws Operating)
30. The Alert cards section SHALL show the cash-gap card in the warning style and the account-shortfall card in the danger style, with the mockup's eyebrow, title and body text
31. The States section SHALL show the Loading card built from Skeleton, the Empty card ("No bank connected yet", "Connect your bank"), the Error card ("We couldn't load your forecast", "Try again"), and the Partial banner ("Reconnect"), each with its icon from `lucide-react` marked `aria-hidden`
32. The `/dev/components` page SHALL show, after the States section, a section titled "Dialog and toast" with one button that opens a themed Dialog (title, one field, Cancel and a primary action, right-aligned) and one button that shows a toast

**Independent test:** open `/dev/components` and `design/mockups/components.dc.html` side by side at 1440px.

### S4: The page is reachable only in development, and accessible (P1)

The page passes the checks every later screen will copy.

**Acceptance Criteria**

33. IF `/dev/components` is requested from a production build (`npm run build && npm start`) THEN the app SHALL respond `404`
34. WHEN `/dev/components` is scanned by `@axe-core/playwright` at 1440px wide and at 375px wide THEN the scan SHALL report 0 violations
35. WHILE the viewport is 375px wide, `/dev/components` SHALL have no horizontal scroll (`document.documentElement.scrollWidth` equal to 375), and its swatch, form and card grids SHALL stack into one column
36. WHILE the viewport is at least 1024px wide, the page content SHALL be at most 1344px wide, with 48px side padding. WHILE it is 375px wide, the side padding SHALL be 16px
37. WHEN a keyboard user presses Tab from the top of `/dev/components` THEN focus SHALL reach every button, input, select, switch, radio and toggle-group item in the mockup's reading order, and Escape SHALL close the open Dialog and return focus to the button that opened it

**Independent test:** `npx playwright test e2e/dev-components.spec.ts`, then `npm run build && npm start` and `curl -I localhost:3000/dev/components`.

## Out of scope

| Excluded | Why |
| --- | --- |
| Money input parsing ("5,000" -> cents) | DESIGN.md's Money input needs `lib/format.ts` (spec 07). Here the Amount field is a styled Input with a `$` adornment, and no parsing. |
| Summary card, Alert card, Step indicator, and Forecast chart as reusable components | Not in spec 06's `add` list. The alert cards on this page are Cards with token classes. Each component arrives with the screen that needs it (21, 23, 24, 26, 11). |
| Interface text from `messages/en.json` | `en.json` arrives in spec 07. This development-only page hard-codes the mockup's copy. |
| App shell, navigation and replacing the starter home page | Spec 07 |
| A dark theme | DESIGN.md defines none |
| Running Playwright in CI | CI's job list is fixed by AD-004 and spec 04, so it stays local |

## Assumptions

Defaults that are not already a numbered criterion. Drop a row once it is.

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| The mockup and DESIGN.md disagree on button weight | Follow the mockup: 600 for primary, outline and disabled; 500 for secondary, link and destructive | The spec's Done-when is "matches the mockup", and DESIGN.md's "15px semibold" reads as the primary case | n |
| Dialog and toast don't appear in the mockup | Add one "Dialog and toast" section after States (AC 32) | Otherwise two of the 13 themed components can't be seen, focus-tested or axe-scanned | n |
| `shadcn add` wants to overwrite the existing `button.tsx` | Keep the existing file (answer no, or skip `--overwrite`), then re-theme it | It's the same generated file from spec 01. Overwriting adds nothing. | n |
| Font fallbacks | Use `next/font/google`'s `fallback` option (`["Georgia", "serif"]`, `["Segoe UI", "system-ui", "sans-serif"]`), checked against `node_modules/next/dist/docs` before use | DESIGN.md names the fallbacks, and AGENTS.md says to read the installed Next.js docs first | n |
| Fraunces weights | Load 500 and 600 (the mockup's Google Fonts link). IBM Plex Sans: 400, 500 and 600. | Matches the mockup's `<link>` exactly | n |
| Profile for this feature | `light` (no `tlc-spec-lean` profile in AGENTS.md) | Default. The `ui` profile would have the Verifier open the mockup and compare each screen's copy and layout, which suits a "matches the mockup" spec. | n |

**Open questions:** none - all resolved or logged above. The user chose door 6 as written (fold 4, add `--line-soft` and `--line-strong` to DESIGN.md in a separate commit) and door 5 as written (404 in any production build, staging included).

## Observable

Worksheet, not the review. `n/a` needs its reason. One row may group the same decision
across several routes.

| Surface | Decision | Landing |
| --- | --- | --- |
| screen `/dev/components` | empty state | n/a - static page with no data, so it has nothing to be empty of. It *shows* the empty-state pattern (AC 31). |
| screen `/dev/components` | loading state | n/a - server-rendered with no data fetch. It *shows* the loading pattern (AC 31). |
| screen `/dev/components` | error state | n/a - no data fetch can fail. It *shows* the error pattern (AC 31). |
| screen `/dev/components` | unauthorised state | AC 33 - absent (404) outside development; no login exists until spec 10 |
| screen `/dev/components` | density and ordering | AC 24-32 - mockup order |
| screen `/dev/components` | destructive action confirms | n/a - the Destructive button is a sample with no action |
| screen `/dev/components` | 375px layout, keyboard, touch targets | AC 14, 35, 36, 37 |
| route `GET /dev/components` | versioning, rate limits | n/a - a development-only HTML page, not an API |

## Sources

- `context/specs/06-web-design-system.md` - the build list and the three Done-when items
- `design/mockups/components.dc.html` - binding layout, copy and colours for `/dev/components`
- `context/DESIGN.md` - binding tokens, type, component rules and accessibility
