# 06 - Design system in the web app checks

Profile: light
Plan: `.specs/features/06-web-design-system/plan.md`

37 checks in 4 slices · 6 one-way doors · 0 open, of which 0 block

Commands run from `frontend/`. `npx vitest run <file> -t "<name>"` runs a Vitest proof, and `npx playwright test <file> -g "<name>"` runs a Playwright proof. Playwright starts `npm run dev` on port 3000 (`playwright.config.ts`), so nothing else may be serving that port.

## Checks

### S1 - The theme is DESIGN.md · 3 files · 18 KB · ~5k

**C1** - `globals.css` `:root` defines all 24 tokens with their hex values: DESIGN.md's 22 plus `--line-soft` `#ECE8E0` and `--line-strong` `#C9C2B5` (AC 1)
Proof: `npx vitest run tests/design-system.test.ts -t "root defines token"`

**C2** - `@theme inline` maps each of the 24 tokens to `--color-<token>: var(--<token>)` (AC 2)
Proof: `npx vitest run tests/design-system.test.ts -t "theme exposes token"`

**C3** - `globals.css` contains no `oklch(` and no `.dark {` block (AC 3)
Proof: `npx vitest run tests/design-system.test.ts -t "no starter palette"`

**C4** - With `colorScheme: "dark"`, the `/dev/components` body has background `rgb(245, 243, 238)` and colour `rgb(22, 32, 43)` (AC 4)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "dark os keeps light theme"`

**C5** - The body's computed `font-family` names IBM Plex Sans first, then `"Segoe UI"`, `system-ui` and `sans-serif`, in that order (AC 5)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "body font is plex"`

**C6** - The `h1`'s computed `font-family` names Fraunces first, then `Georgia` and `serif`, in that order (AC 6)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "heading font is fraunces"`

**C7** - `app/layout.tsx` contains no `Geist` (AC 7)
Proof: `npx vitest run tests/design-system.test.ts -t "no geist"`

**C8** - The body's computed `font-variant-numeric` is `tabular-nums` (AC 8)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "tabular numbers"`

### S2 - The components look and behave as DESIGN.md says · 14 files · 60 KB · ~15k

**C9** - `components/ui/` contains `button`, `card`, `input`, `label`, `select`, `switch`, `radio-group`, `toggle-group`, `dialog`, `badge`, `skeleton` and `sonner` `.tsx` (AC 9)
Proof: `npx vitest run tests/design-system.test.ts -t "component file exists"`

**C10** - Each Button variant renders at least 44px tall, with a 10px radius, 15px text and its mockup colours: primary background `rgb(29, 78, 137)` and text `rgb(255, 255, 255)`; secondary background white and border `rgb(214, 208, 196)`; outline background white and border `rgb(22, 32, 43)`; link text `rgb(29, 78, 137)`; destructive text `rgb(142, 27, 27)` and border `rgb(239, 199, 194)` (AC 10)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "button variant"`

**C11** - The disabled primary Button has background `rgb(233, 229, 220)`, text `rgb(90, 99, 112)` and `opacity` `1` (AC 11)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "disabled button"`

**C12** - The Business name Input and the Province select trigger are each 48px tall, with 16px text, a 10px radius and a 1px `rgb(214, 208, 196)` border (AC 12)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "field metrics"`

**C13** - The Amount Input has `aria-invalid="true"`, a 2px `rgb(142, 27, 27)` border, and an `aria-describedby` element whose text is "Enter an amount greater than $0." (AC 13)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "invalid field"`

**C14** - The 2 switches, 2 radio options and 2 toggle-group items each have a clickable box of at least 44 by 44px (AC 14)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "touch target"`

**C15** - The pressed "Money out" item has background `rgb(255, 255, 255)` and a non-`none` box-shadow. "Money in" has a transparent background (`rgba(0, 0, 0, 0)`). Clicking "Money in" swaps the two (AC 15)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "segmented control"`

**C16** - Each Badge variant has a 6px radius and its mockup colours: neutral background white and text `rgb(69, 79, 92)`; muted background `rgb(241, 238, 231)` and text `rgb(69, 79, 92)`; positive background `rgb(234, 244, 238)` and text `rgb(30, 107, 69)`; warning background `rgb(255, 244, 226)` and text `rgb(122, 67, 0)`; danger background `rgb(142, 27, 27)` and text white (AC 16)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "badge variant"`

**C17** - The Form controls Card has background `rgb(255, 255, 255)`, a 1px `rgb(226, 221, 211)` border and a 14px radius (AC 17)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "card style"`

**C18** - At 1440px wide, the open Dialog is 480px wide, and its left and right gaps to the viewport differ by at most 1px (AC 18)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "dialog desktop"`

**C19** - At 375 by 812px, the open Dialog's box is 375 by 812px (AC 19)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "dialog phone"`

**C20** - The toast is visible 3500ms after it is shown and gone by 5000ms. With `colorScheme: "dark"`, its background is `rgb(255, 255, 255)` (AC 20)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "toast"`

**C21** - Every element Tab reaches on `/dev/components` shows `outline-style` `solid`, `outline-width` `2px`, `outline-color` `rgb(29, 78, 137)` and `outline-offset` `2px` (AC 21)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "focus ring"`

**C22** - With `reducedMotion: "reduce"`, the open Dialog content's computed `animation-duration` is at most `0.01ms` (AC 22)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "reduced motion"`

**C23** - No file under `components/` or `app/` other than `app/globals.css` matches a hex colour (`#` plus 3, 4, 6 or 8 hex digits, not followed by another word character) or `rgb(`, `rgba(`, `hsl(` or `oklch(`. A planted sample of each of those 5 patterns is detected (AC 23)
Proof: `npx vitest run tests/design-system.test.ts -t "no colour literals"`
Proof: `npx vitest run tests/design-system.test.ts -t "guard detects"`

### S3 - `/dev/components` matches the mockup · 2 files · 40 KB · ~10k

**C24** - `GET /dev/components` in development answers `200`. The `h1` is "Components and states", and the `h2` texts are, in order: Colors, Type, Buttons, Form controls, Badges, Alert cards, States, Dialog and toast (AC 24, 32)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "sections in order"`

**C25** - The Colors section has 14 swatches whose names and captions equal the mockup's 14, in order (Background `--bg · #F5F3EE` ... Danger text `--danger-text · #8E1B1B`) (AC 25)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "colour swatches"`

**C26** - The Type section has 7 rows. Each sample's computed size and weight are Display 40/600, Figure 36/600, Title 19/600, Section 18/600, Body 15/400, Caption 13/400 and Eyebrow 12/600 uppercase (AC 26)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "type scale"`

**C27** - The Buttons section's 6 controls read, in order: "Primary: Add expected payment", "Secondary: Dismiss", "Outline: See all fixes", "Text link: Manage", "Destructive: Disconnect" and "Disabled: Continue" (AC 27)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "button labels"`

**C28** - The Form controls section has: the "Business name" textbox valued "Harbor Street Plumbing" with the hint "Hint text sits under the field."; the "Amount" textbox with a visible `$` and its error; the "Province or territory" combobox showing "Ontario"; two "Counts as cash" switches (checked and unchecked); the radios "Primary account" (checked) and "Make primary"; and the "Direction" group with "Money out" and "Money in" (AC 28)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "form controls"`

**C29** - The Badges section's 6 badges read, in order: Primary, Recurring, Expected, Synced, Needs attention, Overdraws Operating (AC 29)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "badge labels"`

**C30** - The Alert cards section has the warning card (background `rgb(255, 244, 226)`, eyebrow "Cash gap · warning", title "Cash falls below your $5,000 minimum the week of Nov 9") and the danger card (background `rgb(252, 237, 235)`, eyebrow "Account shortfall · danger (later)", title "Operating checking will be overdrawn on Friday, Oct 2") (AC 30)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "alert cards"`

**C31** - The States section has a Loading card with at least 4 `[data-slot="skeleton"]` blocks; an Empty card ("No bank connected yet", button "Connect your bank"); an Error card ("We couldn't load your forecast", button "Try again"); and a Partial banner (button "Reconnect"). Each card has one `svg[aria-hidden="true"]` (AC 31)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "state cards"`

**C32** - In the "Dialog and toast" section, "Open dialog" opens a `dialog` role element containing a heading, one textbox, and the buttons "Cancel" then the primary action, in that order. "Show toast" shows a status message (AC 32)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "dialog and toast section"`

### S4 - The page is reachable only in development, and accessible · 3 files · 12 KB · ~3k

**C33** - With `NODE_ENV=production`, rendering the page calls `notFound()`. A production build served by `next start` answers `404` for `/dev/components` and `200` for `/` (AC 33)
Proof: `npx vitest run tests/dev-gate.test.ts -t "production calls notFound"`
Proof: `npm run build && node scripts/check-prod-gate.mjs`

**C34** - `@axe-core/playwright` reports 0 violations on `/dev/components`, at 1440 by 900 and at 375 by 812 (AC 34)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "axe"`

**C35** - At 375px wide, `document.documentElement.scrollWidth` is 375, and the 2nd swatch, 2nd form control and 2nd state card each start below the 1st (AC 35)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "phone layout"`

**C36** - At 1920px wide, the content box is at most 1344px wide with 48px left and right padding. At 375px, the padding is 16px (AC 36)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "page width"`

**C37** - Pressing Tab from the top reaches, in order: the 6 Buttons-section controls, Business name, Amount, Province, switch on, switch off, the checked radio, Money out, then the Empty, Error and Partial buttons and "Open dialog". Escape closes the open Dialog and returns focus to "Open dialog" (AC 37)
Proof: `npx playwright test e2e/dev-components.spec.ts -g "keyboard order"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| colour tokens in `:root` (24) | C1, table-driven over all 24 | - |
| colour tokens in `@theme` (24) | C2, table-driven over all 24 | - |
| shadcn component files (12) | C9, table-driven over all 12 | - |
| Button variants (5) | `primary` C10 · `secondary` C10 · `outline` C10 · `link` C10 · `destructive` C10 | - |
| Badge variants (5) | `neutral` C16 · `muted` C16 · `positive` C16 · `warning` C16 · `danger` C16 | - |
| touch-target control kinds (3) | switch C14 · radio C14 · toggle-group item C14 | - |
| colour-literal patterns (5) | hex C23 · `rgb(` C23 · `rgba(` C23 · `hsl(` C23 · `oklch(` C23 | - |
| mockup sections + added section (8) | Colors C25 · Type C26 · Buttons C27 · Form controls C28 · Badges C29 · Alert cards C30 · States C31 · Dialog and toast C32 | - |
| `GET /dev/components` statuses (2) | 200 C24 · 404 C33 | - |
| colour schemes (2) | light C24 · dark C4 | - |
| viewports for axe (2) | 1440 C34 · 375 C34 | - |
| Landing doors (6) | 1 token names C2 · 2 Button variants C10 · 3 Badge variants C16 · 4 axe dependency C34 · 5 dev gate C33 · 6 extra tokens C1 | - |
| startup config: fonts and global CSS (1 assembly) | root `app/layout.tsx` C5 | - |

- Claims naming a status code or route: C24, C33. Both proofs cross the HTTP boundary (Playwright `page.goto` response, and `fetch` against `next start`).
- No other check claims more than the cases its proof exercises.

## Swept

- validation: C13 - the error presentation of an invalid field. The page has no input logic to validate.
- failure modes: n/a - a static, server-rendered page with no data fetch or write
- idempotency: n/a - nothing is written
- authorization: C33 - the page is absent from every production build. No login exists until spec 10.
- concurrency: n/a - no shared state, and no request does work
- data lifecycle: n/a - no stored data
- dependency failure: C5, C6 - if a Google font fails to load, the named fallbacks are in the computed stack
- state transitions: C11 disabled, C15 pressed or unpressed, C37 dialog open then closed with focus returned
- observability: n/a - a development-only page with no runtime behaviour worth logging

## Handoff

- Read once: plan + checks (~30 KB), DESIGN.md (13 KB), the Components mockup (22 KB) = 65 KB. Write: S1 18 KB, S2 60 KB of mostly generated components, S3 40 KB (page + spec file), S4 12 KB = 130 KB. Total ≈ 195 KB / 4 ≈ 49k, plus tool output from npm, shadcn and Playwright (~40k) ≈ 90k, under the 150k budget, so one builder
- Mechanism: one builder (no ask, under budget)

- **Boundary:** C1-C37 closed at the `feat(frontend): theme the web app with the design system (spec 06)` commit. Vitest 74/74, Playwright `e2e/` 40/40 (123/123 with `--repeat-each=3`), and `npm run build && node scripts/check-prod-gate.mjs` printing `GET / -> 200; GET /dev/components -> 404`
- **Settled mid-build:** C25 corrected from 13 to the mockup's 14 swatches (commit `ae33dc5`). Three Playwright proofs now wait for running CSS transitions and open animations to finish before reading styles (`settle()`); the values asserted are unchanged. The axe scan excludes `nextjs-portal`, the Next.js dev tools overlay, which isn't part of the page
- **Abandoned:** reading the swatch caption straight from the CSS variable, because the CSS compiler shortens six-digit hex to three digits where it can; the caption expands it back
