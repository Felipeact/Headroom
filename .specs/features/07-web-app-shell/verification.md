# 07 - App shell, translations, and formatting verification

**Verdict**: FAIL
**Profile**: light
**Diff range**: 61cfae80fbfd67d685f5f8f18cad3f4f4539e1cd..bb7d02a6aba737f39a78293ce7d222d13ef7cdd8 (round 2 fix diff: 32e806a..bb7d02a)
**Round**: 2 - scoped
**Verifier**: independent sub-agent (author != verifier)

41 of 43 checks PASS with located evidence. C37 and C38 are still BLOCKED. Their proof needs the `headroom-web` Sentry project, its DSN and an API token (plan open question 1, kind `blocks`). `proofs.sh` still stops at `FAIL c37: SENTRY_AUTH_TOKEN is not set in this shell` (exit 1). The FAIL comes from that outside dependency, not from a code defect, and it stands until the proof passes.

Round 2 scope: fix commit `bb7d02a` touched `frontend/e2e/shell.spec.ts`, `checks.md` (C5 and C41 text, plus a new Coverage row) and `plan.md` (the Impact row). `8ebfaa1`, between the two, changes only `.specs/STATE.md` for spec 08 and is outside this feature.

- **Proofs:** all re-run in full at `bb7d02a`.
- **Citations:** refreshed for `frontend/e2e/shell.spec.ts`. The new test at lines 204-217 shifts every line after it by 15.
- **Re-judged:** C5, C41 and the round 1 gaps.
- **Carried from `32e806a`:** everything else.

## Binding sources

Carried from 32e806a. Step 1 (comparing the checks against the binding sources) does not run under profile `light`. The fix did not touch the interface.

## Checks

Verified at bb7d02a. Every proof re-ran at HEAD `bb7d02a` from `frontend/`:

- **Vitest:** one batched run of `npx vitest run lib/format.test.ts components/shell/app-header.test.tsx "app/(app)/states.test.tsx" tests/i18n.test.ts tests/i18n-keys.test.ts tests/sentry-config.test.ts tests/dev-gate.test.ts --reporter=verbose`. All 7 files and 26 tests passed, and each named test is listed individually.
- **Playwright:** one run of `NEXT_PUBLIC_SENTRY_DSN= npx playwright test e2e/shell.spec.ts --reporter=list`. All 26 tests passed (exit 0) on the first run, including the new `phone › link metrics in the menu (C5)`. Port 3000 was free beforehand.

For files the fix did not touch (every file except `e2e/shell.spec.ts`), the assertion judgments are carried from 32e806a.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | 4 pages 200, one header, one main, h1 per page | PW `shell pages (C1)` passed | `frontend/e2e/shell.spec.ts:64` - `expect(response?.status(), path).toBe(200)`; `:65-67` - `toHaveCount(1)` x2, `expect(page.locator('main h1')).toHaveText(title)` over `PAGES` (4) | PASS |
| C2 | wordmark Fraunces 22px 600 at 1440 | PW `desktop › wordmark (C2)` passed | `frontend/e2e/shell.spec.ts:78-80` - `split(',')[0]).toContain('Fraunces')`, `toBe('22px')`, `toBe('600')` | PASS |
| C3 | Main nav: exactly 4 links in order with hrefs | PW `desktop › nav links (C3)` passed | `frontend/e2e/shell.spec.ts:86` - `expect(links).toHaveCount(4)`; `:88-89` - `toHaveText(name)`, `toHaveAttribute('href', href)` | PASS |
| C4 | current link: aria-current, rgb(233,229,220), 600; others: none, transparent, rgb(69,79,92), 500, on all 4 pages | PW `desktop › current link (C4)` passed | `frontend/e2e/shell.spec.ts:100-102` - `toHaveAttribute('aria-current','page')`, `toBe('rgb(233, 229, 220)')`, `toBe('600')`; `:104-107` - `not.toHaveAttribute('aria-current')`, `toBe('rgba(0, 0, 0, 0)')`, `toBe('rgb(69, 79, 92)')`, `toBe('500')` | PASS |
| C5 | the 4 desktop nav links at 1440 and the 4 menu Dialog links at 375: >=44px tall, radius 10px, 15px text | PW `desktop › link metrics (C5)` and `phone › link metrics in the menu (C5)` passed (both match `-g "link metrics"`) | desktop: `frontend/e2e/shell.spec.ts:118-120` - `height).toBeGreaterThanOrEqual(44)`, `toBe('10px')`, `toBe('15px')`. Menu: `:208` - `expect(links).toHaveCount(4)` inside `getByRole('dialog', { name: 'Menu' })`; `:213-215` - the same three assertions on each of the 4, read after `settle(page)` (`:211`) so the 95% open zoom does not shrink the box. Round 1's sampling gap is closed | PASS |
| C6 | 1440 and 1024: 4 links visible, no "Open menu" | PW `desktop nav at 1440 (C6)`, `desktop nav at 1024 (C6)` passed | `frontend/e2e/shell.spec.ts:154` - `toBeVisible()`; `:156` - `getByRole('button', { name: 'Open menu' })).toHaveCount(0)` | PASS |
| C7 | 375 and 1023: 44x44 "Open menu", no nav link visible | PW `phone menu button at 375 (C7)`, `at 1023 (C7)` passed | `frontend/e2e/shell.spec.ts:167` - `expect([b.width, b.height]).toEqual([44, 44])`; `:169` - `toBeHidden()` | PASS |
| C8 | menu dialog "Menu" with 4 links in order, aria-current on Alerts only | PW `phone › menu dialog (C8)` passed | `frontend/e2e/shell.spec.ts:183` - `toHaveCount(4)`; `:185-190` - `toHaveText`, `href`, `aria-current` only when `name === 'Alerts'` | PASS |
| C9 | Settings in menu navigates and closes dialog | PW `phone › menu navigates (C9)` passed | `frontend/e2e/shell.spec.ts:199-201` - `toHaveURL(/\/settings$/)`, `main h1` `toHaveText('Settings')`, `getByRole('dialog')).toHaveCount(0)` | PASS |
| C10 | with business name: caption, name, divider, phone name | Vitest `C10 with business name` passed | `frontend/components/shell/app-header.test.tsx:20-23` - `getByText('Business')`, `getByText('Harbor Street Plumbing')`, `getByTestId('business-divider')`, `header-phone-identity` `.textContent).toBe('Harbor Street Plumbing')`. Proven at component level only (declared in checks.md) | PASS |
| C11 | no name: no caption or divider, "Headroom" in both blocks; 4 live pages show no "Business" | Vitest `C11 without business name` and PW `no business yet (C11)` passed | `frontend/components/shell/app-header.test.tsx:29-32` - `queryByText('Business')).toBeNull()`, `queryByTestId('business-divider')).toBeNull()`, `toBe('Headroom')`; `frontend/e2e/shell.spec.ts:243` - `getByText('Business', { exact: true })).toHaveCount(0)` over 4 pages x 2 viewports | PASS |
| C12 | 375: scrollWidth 375 and 16px padding on 4 pages | PW `phone layout (C12)` passed | `frontend/e2e/shell.spec.ts:254` - `scrollWidth ... toBe(375)`; `:256-257` - `toBe('16px')` x2 | PASS |
| C13 | 1920: content <=1344px, 48px padding | PW `desktop width (C13)` passed | `frontend/e2e/shell.spec.ts:265-266` - `toBe('48px')` x2; `:268` - `expect(width - 96).toBeLessThanOrEqual(1344)` | PASS |
| C14 | header border 1px solid rgb(226,221,211); body rgb(245,243,238) | PW `desktop › header border (C14)` passed | `frontend/e2e/shell.spec.ts:127-130` - `toBe('1px')`, `toBe('solid')`, `toBe('rgb(226, 221, 211)')`, body `toBe('rgb(245, 243, 238)')` | PASS |
| C15 | first Tab hits a visible skip link; Enter focuses main, on 4 pages | PW `skip link (C15)` passed | `frontend/e2e/shell.spec.ts:276` - `expect(skip).toBeFocused()`; `:278-279` - `toBeGreaterThan(1)` x2; `:281` - `expect(page.locator('main')).toBeFocused()` | PASS |
| C16 | Tab order of the 4 nav links, 2px solid rgb(29,78,137), offset 2px | PW `desktop › keyboard nav (C16)` passed | `frontend/e2e/shell.spec.ts:139` - `toBeFocused()`; `:141-144` - `toBe('solid')`, `toBe('2px')`, `toBe('rgb(29, 78, 137)')`, `toBe('2px')` | PASS |
| C17 | 10 Tabs stay in dialog; Escape closes it and focus returns to "Open menu" | PW `phone › menu focus (C17)` passed | `frontend/e2e/shell.spec.ts:230` - `expect(inside, ...).toBe(true)` over 10 iterations; `:233-234` - `toHaveCount(0)`, `expect(button).toBeFocused()` | PASS |
| C18 | axe 0 violations: 4 pages x {1440, 375} plus the menu at 375 | PW `axe at 1440 (C18)`, `axe at 375 (C18)`, `axe on the open menu (C18)` passed | `frontend/e2e/shell.spec.ts:293` - `expect(results.violations, path).toEqual([])`; `:305` - `expect(results.violations).toEqual([])` | PASS |
| C19 | request config resolves to locale en and en.json; `<html lang="en">` | Vitest `C19 request config ...` and PW `html lang (C19)` passed | `frontend/tests/i18n.test.ts:13-14` - `expect(config.locale).toBe('en')`, `expect(config.messages).toEqual(messages)`; `frontend/e2e/shell.spec.ts:310` - `toHaveAttribute('lang', 'en')` | PASS |
| C20 | every text node and aria-label comes from en.json (4 pages x 2 widths, menu, loading, error) | PW `text from messages (C20)` and Vitest `C20 text from messages` passed | `frontend/e2e/shell.spec.ts:319` and `:328` - `expect(MESSAGE_VALUES, ...).toContain(text)`; `frontend/app/(app)/states.test.tsx:79-81` - `strings.length).toBeGreaterThan(0)`, `expect(values, ...).toContain(text)` | PASS |
| C21 | title "Headroom" on 4 pages | PW `title (C21)` passed | `frontend/e2e/shell.spec.ts:335` - `await expect(page).toHaveTitle('Headroom')` | PASS |
| C22 | an unknown key under `@ts-expect-error` keeps `npm run typecheck` at exit 0 | `npm run typecheck` exit 0; Vitest `C22 unknown key is a type error` passed | `frontend/tests/i18n-keys.test.ts:11-12` - `// @ts-expect-error` above `return t('noSuchKey')` on a `useTranslations<'Nav'>` translator (typed via `frontend/global.ts:5-6` `AppConfig.Messages`); `:17` - `expect(t('dashboard')).toBe('Dashboard')` | PASS |
| C23 | loading: aria-busy=true with >=1 skeleton | Vitest `C23 loading state` passed | `frontend/app/(app)/states.test.tsx:47-48` - `expect(busy).not.toBeNull()`, `querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(1)` | PASS |
| C24 | error.tsx beside layout.tsx; title, one aria-hidden svg, "Try again" | Vitest `C24 error state` passed | `frontend/app/(app)/states.test.tsx:52-53` - `existsSync(... 'layout.tsx')).toBe(true)`, `existsSync(... 'error.tsx')).toBe(true)`; `:55-57` - `getByText("We couldn't load this page")`, `svg[aria-hidden="true"]')).toHaveLength(1)`, `getByRole('button', { name: 'Try again' })`. Placement is proven by file location only (declared in checks.md) | PASS |
| C25 | "Try again" calls `retry` exactly once | Vitest `C25 try again resets` passed | `frontend/app/(app)/states.test.tsx:64` - `expect(retry).toHaveBeenCalledTimes(1)` | PASS |
| C26 | captureException exactly once, with the error | Vitest `C26 reports to sentry` passed | `frontend/app/(app)/states.test.tsx:70-71` - `toHaveBeenCalledTimes(1)`, `toHaveBeenCalledWith(error)` | PASS |
| C27 | $3,200 / −$3,200, first char U+2212 | Vitest `C27 money whole dollars` passed | `frontend/lib/format.test.ts:8-10` - `toBe('$3,200')`, ``toBe(`${MINUS}$3,200`)``, `codePointAt(0)).toBe(0x2212)` | PASS |
| C28 | $42,300 and $0 | Vitest `C28 money grouping` passed | `frontend/lib/format.test.ts:14-15` - `toBe('$42,300')`, `toBe('$0')` | PASS |
| C29 | 320050 to $3,201; −320050 to −$3,201; 320049 to $3,200 | Vitest `C29 money rounding` passed | `frontend/lib/format.test.ts:19-21` | PASS |
| C30 | ±49 and 0 give "$0" for both functions | Vitest `C30 zero has no sign` passed | `frontend/lib/format.test.ts:25-29` - five `toBe('$0')` | PASS |
| C31 | +$8,000 and −$640 | Vitest `C31 signed money` passed | `frontend/lib/format.test.ts:33-34` | PASS |
| C32 | RangeError for 3200.5, NaN, Infinity, 2**53 on both functions | Vitest `C32 rejects non-integer cents` passed | `frontend/lib/format.test.ts:38-40` - loop over all 4 inputs, `toThrow(RangeError)` for both functions | PASS |
| C33 | no U+002D over 7 cents inputs x 2 functions and 3 dates x 2 styles | Vitest `C33 no hyphen minus` passed | `frontend/lib/format.test.ts:72-80` - all 7 cents values and all 3 dates in both styles; `expect(output).not.toContain('-')` | PASS |
| C34 | "Nov 9" and "Fri, Oct 2" | Vitest `C34 date styles` passed | `frontend/lib/format.test.ts:53-54` | PASS |
| C35 | "Oct 2" under Vancouver and Auckland TZ | Vitest `C35 date ignores time zone` passed | `frontend/lib/format.test.ts:58-61` - sets `process.env.TZ` each time, then `toBe('Oct 2')` | PASS |
| C36 | RangeError for 4 malformed dates | Vitest `C36 rejects malformed dates` passed | `frontend/lib/format.test.ts:65-66` - all 4 inputs, `toThrow(RangeError)` | PASS |
| C37 | client error event found in `headroom-web` through the Sentry API within 60s | `bash ../.specs/features/07-web-app-shell/proofs.sh c37 c38` at bb7d02a: `FAIL c37: SENTRY_AUTH_TOKEN is not set in this shell`, exit 1 | no evidence. The supporting code exists: `frontend/app/dev/sentry-check/sentry-check-buttons.tsx:12` throws `` `Headroom web Sentry check (client) ${runId}` ``. `frontend/e2e/sentry-check.spec.ts:14` (run in round 1 with no DSN, 1 passed) only proves the button throws, not that Sentry receives the event | BLOCKED (open question 1) |
| C38 | server error event found in `headroom-web` within 60s | same `proofs.sh` run, which stopped before reaching c38, exit 1 | no evidence. The supporting code exists: `frontend/app/dev/sentry-check/actions.ts:4` throws `` `Headroom web Sentry check (server) ${runId}` ``, and `frontend/instrumentation.ts:13` sets `onRequestError = Sentry.captureRequestError` | BLOCKED (open question 1) |
| C39 | dev renders, production calls notFound; `next start` answers 404 for `/dev/sentry-check` and 200 for the 4 pages | Vitest `C39 sentry check: ...` (2 tests) passed. `env -u SENTRY_AUTH_TOKEN npm run build` exit 0, then `node scripts/check-prod-gate.mjs` exit 0, printing `GET / -> 200; GET /expected-payments -> 200; GET /alerts -> 200; GET /settings -> 200; GET /dev/components -> 404; GET /dev/sentry-check -> 404` | `frontend/tests/dev-gate.test.ts:32` - `digest).toBe('NEXT_HTTP_ERROR_FALLBACK;404')`; `:38-40` - `resolves.toBeDefined()`; `frontend/scripts/check-prod-gate.mjs:34-39,45` - expected map plus `if (got !== want) failed = true` | PASS |
| C40 | no `sentry-example-(page\|api)` path under `app/` | Vitest `C40 no example routes` passed | `frontend/tests/sentry-config.test.ts:22` - `paths.filter(... /sentry-example-(page\|api)/ ...)).toEqual([])` | PASS |
| C41 | 3 init files: DSN from env plus shared options, no tracing, replay or logs; 6 dataCollection values; no DSN literal in any git-tracked or would-track file | Vitest `C41 init options` and `C41 no dsn in source` passed | `frontend/tests/sentry-config.test.ts:28-31` - `toContain('dsn: process.env.NEXT_PUBLIC_SENTRY_DSN')`, `toContain('...sentryOptions')`, 4 forbidden strings `not.toContain`; `:34-41` - `dataCollection).toEqual({userInfo:false, cookies:false, httpHeaders:false, httpBodies:[], urlQueryParams:false, stackFrameVariables:false})`; `:47` - `git ls-files --cached --others --exclude-standard`; `:63` - `expect(leaks).toEqual([])`. The check text (`checks.md:149`) now names the same scope, so round 1's precision gap is closed | PASS |
| C42 | empty DSN: 4 pages, no pageerror, no request to a host containing "sentry" | PW `no sentry without dsn (C42)` passed (run with `NEXT_PUBLIC_SENTRY_DSN=`) | `frontend/e2e/shell.spec.ts:351-352` - `expect(errors).toEqual([])`, `expect(sentryRequests).toEqual([])` | PASS |
| C43 | build exits 0 with SENTRY_AUTH_TOKEN unset | `env -u SENTRY_AUTH_TOKEN npm run build` exit 0 at bb7d02a | command exit code 0. `frontend/next.config.ts:12-16` - `withSentryConfig` does not require a token | PASS |

## Coverage

Verified at bb7d02a for the row the fix added; the rest is carried from 32e806a. Under `light` I did not recompute the coverage join, and I did not judge `Test policy` rows (`checks.md` has none).

The fix added the row `nav link placements for metrics (2)`: desktop nav C5, menu Dialog C5. Both members now have an asserting proof (`frontend/e2e/shell.spec.ts:118-120` and `:213-215`).

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| nav link placements for metrics (2) | checks.md row added in bb7d02a | desktop nav: C5 `shell.spec.ts:118-120`; menu Dialog: C5 `shell.spec.ts:213-215` | - |
| Sentry runtimes (2) | checks.md row (not recomputed under light) | client C37, server C38: both BLOCKED | client (C37), server (C38) |

## Swept

Carried from 32e806a. The fix touched no code these rows cite.

- **validation:** `frontend/lib/format.ts:10-12` (`Number.isSafeInteger`) and `:37-46` (regex plus a round-trip check on the date). Present.
- **failure modes:** `frontend/app/(app)/error.tsx:19-21` (`captureException`) and `:29` (`retry()`). Present.
- **authorization:** `frontend/app/dev/sentry-check/page.tsx:8` (`if (process.env.NODE_ENV === "production") notFound()`). Present.
- **dependency failure:** `frontend/lib/sentry-options.ts`, plus DSN-gated init in the 3 config files. Present.
- **observability:** C37 and C38 are unproven, as above.

## Handoff corrections ("Settled mid-build")

C25 and the C41 `dataCollection` items are carried from 32e806a. The C41 scoping item and the plan Impact row were verified at bb7d02a.

- **C25 `retry`:** faithful. The installed Next is 16.3.8. `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/error.md:117-121,155-157,331` names `retry` as the stable prop that re-fetches (since v16.3.0), and `reset` as the one that only clears the error state. Plan AC 25 already says `retry`.
- **C41 `dataCollection`:** faithful. In `@sentry/nextjs` 11.3.0, a grep for `sendDefaultPii` in `@sentry/core/build/types` finds nothing, and `types/datacollection.d.ts:27-108` declares the 6 named categories. Plan door 4 explicitly allows "the installed SDK's equivalent".
  - Observation, not a failure: the same interface also has `graphQL`, `genAI`, `databaseQueryData`, `queues` and `frameContextLines`, left at their defaults. None of them applies to this web app today.
- **C41 scoping to git-tracked files:** faithful to the plan, because open question 1 puts the DSN in the ignored `frontend/.env.local`. The C41 check text now states this scope, so the check and its proof agree.
- **Plan Impact "starter page" row:** it now records that `e2e/home.spec.ts` is unchanged and `app/page.test.tsx` was deleted. `git diff 61cfae8..bb7d02a` confirms both: `home.spec.ts` is absent from the diff, and `app/page.test.tsx` shows as a deletion. Round 1's gap 4 is closed.

## Faults injected

Carried from 32e806a. Fault injection does not run under profile `light`.

## Gate

Verified at bb7d02a:

- **Vitest:** `npx vitest run <7 files> --reporter=verbose` - 26 passed, 0 failed.
- **Playwright:** `NEXT_PUBLIC_SENTRY_DSN= npx playwright test e2e/shell.spec.ts --reporter=list` - 26 passed, 0 failed, on the first run.
- **Typecheck:** `npm run typecheck` - exit 0.
- **Build:** `env -u SENTRY_AUTH_TOKEN npm run build` - exit 0.
- **Production gate:** `node scripts/check-prod-gate.mjs` - exit 0.
- **Sentry proofs:** `bash ../.specs/features/07-web-app-shell/proofs.sh c37 c38` - exit 1 (`FAIL c37: SENTRY_AUTH_TOKEN is not set in this shell`).

## Ranked gaps

1. **C37 and C38 have no evidence.** They are blocked on plan open question 1, which needs the `headroom-web` Sentry project, its DSN in `frontend/.env.local`, and `SENTRY_AUTH_TOKEN`, `SENTRY_ORG` and `SENTRY_PROJECT`. AC 37 and 38 stay unproven, and the spec's Sentry Done-when item stays open.

Round 1's gaps 2 (C41 text), 3 (C5 menu links) and 4 (plan Impact row) are closed in bb7d02a.
