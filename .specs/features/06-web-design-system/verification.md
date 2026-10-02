# 06 - Design system in the web app verification

**Verdict**: PASS
**Profile**: light
**Diff range**: f1bbdd2..2a08ab3a181581e54be67eb13e30bed8cca89631
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

Verified at `2a08ab3`. Port 3000 and 3100 were confirmed free before the runs (curl: connection refused; `netstat` showed no listener), so Playwright's `webServer` started a fresh `npm run dev` from this worktree.

Profile `light`: step 1 (binding-source comparison), the `Coverage` recompute, `Test policy` verdicts and fault injection are not run. No `Test policy` section exists in `checks.md`.

Every proof file was added by this feature's diff (`git diff --name-only f1bbdd2..HEAD`): `frontend/e2e/dev-components.spec.ts`, `frontend/tests/design-system.test.ts`, `frontend/tests/dev-gate.test.ts`, `frontend/scripts/check-prod-gate.mjs`.

## Checks

Paths are relative to `frontend/`. Vitest run = `npx vitest run tests/design-system.test.ts tests/dev-gate.test.ts --reporter=verbose` (72/72, exit 0). Playwright run = `npx playwright test e2e/dev-components.spec.ts --reporter=list` (40/40, exit 0). Each named test appears individually as passed in those outputs.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `:root` defines 24 tokens with hex values | Vitest: 24 x "C1 ... root defines token --<name> as <hex>" + "root defines token count is 24", all passed | `tests/design-system.test.ts:64` - `expect(root).toMatch(new RegExp(\`--${name}:\\s*${hex};\`, 'i'))` over the 24-entry `TOKENS` table at `tests/design-system.test.ts:10-35` (includes `'line-soft': '#ECE8E0'`, `'line-strong': '#C9C2B5'`); `tests/design-system.test.ts:67` - `toHaveLength(24)` | PASS |
| C2 | `@theme inline` maps each token to `--color-<token>: var(--<token>)` | Vitest: 24 x "C2 ... theme exposes token --color-<name>", all passed | `tests/design-system.test.ts:74` - `expect(theme).toMatch(new RegExp(\`--color-${name}:\\s*var\\(--${name}\\);\`))` | PASS |
| C3 | no `oklch(` and no `.dark {` | Vitest "C3 no starter palette" passed | `tests/design-system.test.ts:79` - `not.toContain('oklch(')`; `tests/design-system.test.ts:80` - `not.toMatch(/\.dark\s*\{/)` | PASS |
| C4 | dark OS keeps body bg `rgb(245, 243, 238)` / colour `rgb(22, 32, 43)` | Playwright "dark os keeps light theme (C4)" passed | `e2e/dev-components.spec.ts:49` - `newContext({ colorScheme: 'dark' })`; `e2e/dev-components.spec.ts:53` - `toBe('rgb(245, 243, 238)')`; `e2e/dev-components.spec.ts:54` - `toBe('rgb(22, 32, 43)')` | PASS |
| C5 | body font: IBM Plex Sans, then Segoe UI, system-ui, sans-serif | Playwright "body font is plex (C5)" passed | `e2e/dev-components.spec.ts:61` - `expect(stack[0]).toMatch(/IBM Plex Sans/)`; `e2e/dev-components.spec.ts:62` - `expectInOrder(stack, [stack[0], 'Segoe UI', 'system-ui', 'sans-serif'])` (order asserted at `e2e/dev-components.spec.ts:44`) | PASS |
| C6 | h1 font: Fraunces, then Georgia, serif | Playwright "heading font is fraunces (C6)" passed | `e2e/dev-components.spec.ts:68` - `toMatch(/Fraunces/)`; `e2e/dev-components.spec.ts:69` - `expectInOrder(stack, [stack[0], 'Georgia', 'serif'])` | PASS |
| C7 | `app/layout.tsx` has no Geist | Vitest "C7 no geist" passed | `tests/design-system.test.ts:85` - `expect(layout).not.toMatch(/geist/i)` | PASS |
| C8 | body `font-variant-numeric` is `tabular-nums` | Playwright "tabular numbers (C8)" passed | `e2e/dev-components.spec.ts:74` - `toBe('tabular-nums')` | PASS |
| C9 | 12 component files exist | Vitest: 12 x "C9 component file exists: components/ui/<name>.tsx", all passed | `tests/design-system.test.ts:104` - `expect(existsSync(path.join(frontend, 'components/ui', \`${name}.tsx\`))).toBe(true)` over the 12-name list at `tests/design-system.test.ts:88-101` | PASS |
| C10 | 5 Button variants: >=44px, 10px radius, 15px, mockup colours | Playwright 5 x "button variant <v> (C10)", all passed | `e2e/dev-components.spec.ts:94` - `height).toBeGreaterThanOrEqual(44)`; `:95` - `toBe('10px')`; `:96` - `toBe('15px')`; `:98` - `expect(await css(control, property), property).toBe(value)` over the table at `e2e/dev-components.spec.ts:85-89` (primary `rgb(29, 78, 137)`/white; secondary white/`rgb(214, 208, 196)`; outline white/`rgb(22, 32, 43)`; link `rgb(29, 78, 137)`; destructive `rgb(142, 27, 27)`/`rgb(239, 199, 194)`) | PASS |
| C11 | disabled primary: bg `rgb(233, 229, 220)`, text `rgb(90, 99, 112)`, opacity 1 | Playwright "disabled button (C11)" passed | `e2e/dev-components.spec.ts:105` - `toBe('rgb(233, 229, 220)')`; `:106` - `toBe('rgb(90, 99, 112)')`; `:107` - `opacity')).toBe('1')` | PASS |
| C12 | Input and Select trigger 48px, 16px, 10px radius, 1px `rgb(214, 208, 196)` | Playwright "field metrics (C12)" passed | `e2e/dev-components.spec.ts:116` - `height).toBe(48)`; `:117` - `toBe('16px')`; `:118` - `toBe('10px')`; `:119` - `toBe('1px')`; `:120` - `toBe('rgb(214, 208, 196)')`, looped over both fields | PASS |
| C13 | Amount `aria-invalid`, 2px `rgb(142, 27, 27)`, described-by error text | Playwright "invalid field (C13)" passed | `e2e/dev-components.spec.ts:126` - `toHaveAttribute('aria-invalid', 'true')`; `:127` - `toBe('2px')`; `:128` - `toBe('rgb(142, 27, 27)')`; `:131` - `page.locator(\`[id="${describedBy}"]\`)).toHaveText('Enter an amount greater than $0.')` | PASS |
| C14 | 2 switches, 2 radios, 2 toggle items each >=44x44 | Playwright "touch target (C14)" passed | `e2e/dev-components.spec.ts:142` - `expect(targets).toHaveLength(6)`; `:145` - `width).toBeGreaterThanOrEqual(44)`; `:146` - `height).toBeGreaterThanOrEqual(44)` | PASS |
| C15 | pressed item white + shadow, other transparent; click swaps | Playwright "segmented control (C15)" passed | `e2e/dev-components.spec.ts:154-156` - out `toBe(WHITE)`, shadow `not.toBe('none')`, in `toBe('rgba(0, 0, 0, 0)')`; after `into.click()`, `:160-162` - in `toBe(WHITE)`, shadow `not.toBe('none')`, out `toBe('rgba(0, 0, 0, 0)')` | PASS |
| C16 | 5 Badge variants: 6px radius and mockup colours | Playwright 5 x "badge variant <v> (C16)", all passed | `e2e/dev-components.spec.ts:175` - `toHaveAttribute('data-variant', variant)`; `:176` - `background-color')).toBe(background)`; `:177` - `color')).toBe(color)`; `:178` - `toBe('6px')`, over the table at `e2e/dev-components.spec.ts:166-170` matching the check's 5 colour pairs | PASS |
| C17 | Form controls Card white, 1px `rgb(226, 221, 211)`, 14px radius | Playwright "card style (C17)" passed | `e2e/dev-components.spec.ts:184` - `toBe(WHITE)`; `:185` - `toBe('1px')`; `:186` - `toBe('rgb(226, 221, 211)')`; `:187` - `toBe('14px')` | PASS |
| C18 | at 1440, Dialog 480px wide, centred within 1px | Playwright "dialog desktop (C18)" passed | `e2e/dev-components.spec.ts:195` - `expect(Math.round(b.width)).toBe(480)`; `:196` - `expect(Math.abs(b.x - (1440 - (b.x + b.width)))).toBeLessThanOrEqual(1)` | PASS |
| C19 | at 375x812, Dialog box 375x812 | Playwright "dialog phone (C19)" passed | `e2e/dev-components.spec.ts:226` - `toEqual([0, 0, 375, 812])` | PASS |
| C20 | toast visible at 3500ms, gone by 5000ms; dark OS bg white | Playwright "toast lasts 4 seconds (C20)" and "toast stays light under a dark os (C20)" passed | `e2e/dev-components.spec.ts:236` - `toBeVisible()` after waiting to 3500ms; `:237` - `toHaveCount(0, { timeout: Math.max(5000 - (Date.now() - shownAt), 1) })`; `:241` - `colorScheme: 'dark'`; `:247` - `toBe(WHITE)` | PASS |
| C21 | every Tab-reached element shows 2px solid `rgb(29, 78, 137)` outline, offset 2px | Playwright "focus ring (C21)" passed | `e2e/dev-components.spec.ts:210` - `expect(ring.slice(0, 4), ...).toEqual(['solid', '2px', 'rgb(29, 78, 137)', '2px'])` on every Tab stop until "Show toast"; `:214` - `toBeFocused()`; `:215` - `reached).toBeGreaterThanOrEqual(17)` | PASS |
| C22 | reduced motion: Dialog content `animation-duration` <= 0.01ms | Playwright "reduced motion (C22)" passed | `e2e/dev-components.spec.ts:252` - `reducedMotion: 'reduce'`; `:259` - `expect(seconds).toBeLessThanOrEqual(0.00001)` (0.00001 s = 0.01 ms) | PASS |
| C23 | no colour literals outside globals.css; guard detects 5 planted patterns | Vitest "no colour literals in components/ or app/ outside globals.css", 5 x "guard detects <kind>", "guard ignores a plain anchor and an id", all passed | `tests/design-system.test.ts:114` - `files.length).toBeGreaterThan(0)`; `:120` - `expect(offenders).toEqual([])`; `:130` - `expect(findColourLiterals(sample)).toEqual([sample])` over hex, `rgb(`, `rgba(`, `hsl(`, `oklch(` at `tests/design-system.test.ts:124-128`; patterns at `tests/design-system.test.ts:44-45` | PASS |
| C24 | dev GET 200, h1 and 8 h2 in order | Playwright "sections in order (C24)" passed | `e2e/dev-components.spec.ts:266` - `expect(response?.status()).toBe(200)`; `:267` - `toHaveText('Components and states')`; `:268-277` - h2 `toHaveText([...8 names in order])` | PASS |
| C25 | 14 swatches, names and captions in mockup order | Playwright "colour swatches (C25)" passed | `e2e/dev-components.spec.ts:299` - `toHaveCount(14)`; `:301-302` - `items.nth(i).getByText(name/caption, { exact: true })).toBeVisible()` over the 14-row table at `e2e/dev-components.spec.ts:283-296` | PASS |
| C26 | 7 type rows at stated size/weight; Eyebrow uppercase | Playwright "type scale (C26)" passed | `e2e/dev-components.spec.ts:319` - `toHaveCount(7)`; `:322` - `font-size'), text).toBe(size)`; `:323` - `font-weight'), text).toBe(weight)` over `e2e/dev-components.spec.ts:310-316` (40/600, 36/600, 19/600, 18/600, 15/400, 13/400, 12/600); `:325` - `toBe('uppercase')` | PASS |
| C27 | 6 Buttons-section labels in order | Playwright "button labels (C27)" passed | `e2e/dev-components.spec.ts:330` - `locator('button, a')).toHaveText([...6 labels])` | PASS |
| C28 | Form controls contents | Playwright "form controls (C28)" passed | `e2e/dev-components.spec.ts:343` - `toHaveValue('Harbor Street Plumbing')`; `:344` hint visible; `:346` `$` visible; `:347` error visible; `:348` - `toHaveText('Ontario')`; `:350-352` - 2 switches, `aria-checked` true/false; `:353-354` - radios checked/unchecked; `:355` - Direction radios `toHaveText(['Money out', 'Money in'])` | PASS |
| C29 | 6 badge labels in order | Playwright "badge labels (C29)" passed | `e2e/dev-components.spec.ts:363` - `locator('[data-slot="badge"]')).toHaveText([...6 labels])` | PASS |
| C30 | warning and danger alert cards with bg, eyebrow, title | Playwright "alert cards (C30)" passed | `e2e/dev-components.spec.ts:376` - `toHaveCount(2)`; `:377` - `toBe('rgb(255, 244, 226)')`; `:378`, `:380` eyebrow/title; `:382` - `toBe('rgb(252, 237, 235)')`; `:383`, `:385` eyebrow/title | PASS |
| C31 | Loading >=4 skeletons; Empty, Error, Partial with buttons and one aria-hidden svg | Playwright "state cards (C31)" passed | `e2e/dev-components.spec.ts:393` - `skeleton"]').count()).toBeGreaterThanOrEqual(4)`; `:400` - `getByRole('button', { name: action })).toBeVisible()`; `:401` - `locator('svg[aria-hidden="true"]')).toHaveCount(1)` for Empty, Error, Partial | PASS |
| C32 | Dialog: heading, one textbox, Cancel then primary; Show toast shows message | Playwright "dialog and toast section (C32)" passed | `e2e/dev-components.spec.ts:410` - heading `toHaveCount(1)`; `:411` - textbox `toHaveCount(1)`; `:414` - `cancel).toBeGreaterThanOrEqual(0)`; `:416` - `dialog.getByRole('button').nth(cancel + 1)` `toHaveAttribute('data-variant', 'primary')`; `:419` - `toContainText('Expected payment added')` | PASS |
| C33 | production calls `notFound()`; `next start` 404 for page, 200 for `/` | Vitest "C33 production calls notFound" passed; `npm run build && node scripts/check-prod-gate.mjs` printed `GET / -> 200; GET /dev/components -> 404`, exit 0 | `tests/dev-gate.test.ts:16` - `digest).toBe('NEXT_HTTP_ERROR_FALLBACK;404')` under `vi.stubEnv('NODE_ENV', 'production')`; `scripts/check-prod-gate.mjs:35` - `failed = home !== 200 OR dev !== 404` (logical OR, written out so the table stays parseable) (HTTP boundary, `fetch` against `next start` on port 3100); gate at `app/dev/components/page.tsx:66` | PASS |
| C34 | axe 0 violations at 1440x900 and 375x812 | Playwright "axe at 1440 (C34)" and "axe at 375 (C34)" passed | `e2e/dev-components.spec.ts:424` - `[[1440, 900], [375, 812]]`; `:430` - `new AxeBuilder({ page }).exclude('nextjs-portal').analyze()`; `:431` - `expect(results.violations).toEqual([])` | PASS |
| C35 | 375px: scrollWidth 375; 2nd swatch, form control, state card below 1st | Playwright "phone layout (C35)" passed | `e2e/dev-components.spec.ts:438` - `scrollWidth)).toBe(375)`; `:442` - `expect(b.y).toBeGreaterThanOrEqual(a.y + a.height)`, applied at `:445`, `:446`, `:448` | PASS |
| C36 | 1920px: content <=1344 with 48px padding; 375px: 16px | Playwright "page width (C36)" passed | `e2e/dev-components.spec.ts:455-456` - `toBe('48px')` left/right; `:458` - `expect(content).toBeLessThanOrEqual(1344)`; `:460-461` - `toBe('16px')` left/right | PASS |
| C37 | Tab order through 17 controls; Escape closes Dialog, focus returns | Playwright "keyboard order (C37)" passed | `e2e/dev-components.spec.ts:489` - `await expect(target).toBeFocused()` after each Tab, over the 17-entry order at `e2e/dev-components.spec.ts:468-486`; `:494` - `toBeHidden()`; `:495` - Open dialog `toBeFocused()` | PASS |

## Swept existing re-read

| Row | Cited | In the code |
| --- | --- | --- |
| validation | C13 | `aria-invalid` and `aria-describedby` asserted live at `e2e/dev-components.spec.ts:126`, `e2e/dev-components.spec.ts:131` - present |
| authorization | C33 | `if (process.env.NODE_ENV === "production") notFound()` at `app/dev/components/page.tsx:66` - present |
| dependency failure | C5, C6 | `fallback: ["Segoe UI", "system-ui", "sans-serif"]` at `app/layout.tsx:9`, `fallback: ["Georgia", "serif"]` at `app/layout.tsx:16` - present |
| state transitions | C11, C15, C37 | disabled via `aria-disabled="true"` at `app/dev/components/page.tsx:112`; pressed swap and dialog close asserted live - present |

## Notes (non-failing)

Level and sampling: no check claims more members than its proof walks. C24 and C33 both cross the HTTP boundary (Playwright response status, and `fetch` against `next start`). These notes are about how precisely the checks are worded. They don't change any row.

1. C22 is narrower than plan AC 22, which also names the toast and `transition-duration`. The check and its proof cover only the Dialog content's `animation-duration`. The check is proven as written. The toast under reduced motion has no check.
2. C31 says "Each card has one `svg[aria-hidden]`", but the proof asserts it for Empty, Error and Partial only. The mockup's Loading card has no icon (`design/mockups/components.dc.html:152-156`), so the code is right and the check's wording is loose.
3. C32 says "shows a status message". The proof checks the toast's text through `[data-sonner-toast]` (`e2e/dev-components.spec.ts:419`), not the `status` role.

## Gate

- `npx vitest run tests/design-system.test.ts tests/dev-gate.test.ts --reporter=verbose`: 72 passed, 0 failed, exit 0
- `npx playwright test e2e/dev-components.spec.ts --reporter=list`: 40 passed, 0 failed, exit 0
- `npm run build && node scripts/check-prod-gate.mjs`: build succeeded, printed `GET / -> 200; GET /dev/components -> 404`, exit 0
- `python3 .claude/skills/tlc-spec-lean/scripts/validate_verification.py 06-web-design-system`: exit 0
