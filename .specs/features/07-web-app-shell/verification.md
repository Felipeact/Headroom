# 07 - App shell, translations, and formatting verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 61cfae80fbfd67d685f5f8f18cad3f4f4539e1cd..313bfd53d6737899d16a2f5443ced9ad51287c43 (round 3 fix diff: bb7d02a..313bfd5)
**Round**: 3 - scoped
**Verifier**: independent sub-agent (author != verifier)

43 of 43 checks PASS with located evidence. C37 and C38 now pass on a live run against the `headroom-web` Sentry project:

- **Run:** `check17909675334579`.
- **Proof:** `proofs.sh` exited 0 in 27s, printing `PASS c37` and `PASS c38`.
- **Negative control:** a never-sent tag matches 0 issues.
- **Runtimes:** I confirmed by hand that each check's event came from the right runtime. That includes a `platform: node` event for C38.

One precision gap remains, and it does not fail the verdict: `proofs.sh` alone cannot tell the server event in C38 from a browser-side duplicate (see "Ranked gaps").

Round 3 scope:

- **What changed:**
  - Fix commit `313bfd5` rewrote `.specs/features/07-web-app-shell/proofs.sh` and added a handoff line to `checks.md`.
  - `3936c86` committed the round 2 report and some notes, with no code change. `967a288` is spec 08's STATE note and is outside this feature.
  - No file under `frontend/` changed, so every citation in `frontend/` stands.
- **Proofs:** all re-run in full at `313bfd5`.
- **Re-judged:** C37, C38, C42 (now that `.env.local` holds a DSN) and C43 (now that `.env.local` holds `SENTRY_AUTH_TOKEN`).
- **Carried from bb7d02a:** citation judgments for C1-C36 and C39-C41.

The credentials were loaded with `set -a; . frontend/.env.local; set +a`. I never printed a value. Presence checks only printed `set` or `unset`.

## Binding sources

Carried from 32e806a. Step 1 (comparing the checks against the binding sources) does not run under profile `light`. Neither fix touched the interface.

## Checks

Verified at 313bfd5. Every proof re-ran at HEAD `313bfd5` from `frontend/`:

- **Vitest:** one batched run of `npx vitest run lib/format.test.ts components/shell/app-header.test.tsx "app/(app)/states.test.tsx" tests/i18n.test.ts tests/i18n-keys.test.ts tests/sentry-config.test.ts tests/dev-gate.test.ts --reporter=verbose`. All 7 files and 26 tests passed, and each named test is listed individually.
- **Playwright:** one run of `NEXT_PUBLIC_SENTRY_DSN= npx playwright test e2e/shell.spec.ts --reporter=list`. All 26 tests passed (exit 0) on the first run, with port 3000 free.
- **Sentry proofs:** `set -a; . frontend/.env.local; set +a; bash .specs/features/07-web-app-shell/proofs.sh c37 c38`, run from the repo root with port 3000 free. Exit 0 after 27s, printing `run check17909675334579`, `PASS c37` and `PASS c38`.

No file under `frontend/` changed after bb7d02a. For C1-C36 and C39-C41, the `file:line` citations and assertion judgments are carried from bb7d02a, and the proofs are green again at 313bfd5.

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
| C37 | client error event found in `headroom-web` through the Sentry API within 60s | `proofs.sh c37 c38` at 313bfd5, exit 0: `PASS c37` for run `check17909675334579` | Proof assertion `.specs/features/07-web-app-shell/proofs.sh:55` - `[ "$(event_count "Headroom web Sentry check (client) $RUN_ID")" -gt 0 ]`. `event_count` (`:41-49`) polls `/api/0/projects/$SENTRY_ORG/$SENTRY_PROJECT/issues/` for up to 60s (`:41` `deadline=$((SECONDS + 60))`) and counts issues whose title contains the full message plus the nonce (`:45` `m in (i.get("title") or "")`). A 403 or any non-list reply counts as 0 (`isinstance(d,list) else 0`).<br>Independent checks, no value printed:<br>- `SENTRY_PROJECT` is `headroom-web`, and the project id in the DSN equals the API's id for `headroom-web`.<br>- The matching issue 7768827132 is `platform: javascript` (the browser SDK), environment `development`, created 2026-10-02T18:58:58Z, inside the 27s run.<br>- Negative control: `Headroom web Sentry check (client) neversent1771021867` matched 0 issues of 0 returned | PASS |
| C38 | server error event found in `headroom-web` within 60s | same run, exit 0: `PASS c38` | `.specs/features/07-web-app-shell/proofs.sh:63` - `[ "$(event_count "Headroom web Sentry check (server) $RUN_ID")" -gt 0 ]`, same lookup as C37.<br>Independent check: the server nonce matched 2 issues.<br>- Issue 7768827055 is `platform: node`, tag `runtime: node v24.16.0`. This is the server SDK via `frontend/instrumentation.ts:13` (`onRequestError = Sentry.captureRequestError`).<br>- Issue 7768826997 is `platform: javascript`. It is the browser's `unhandledRejection` of the server action's dev-mode error, seen in the run's `[browser] ⨯ unhandledRejection` log.<br>- Negative control: `Headroom web Sentry check (server) neversent1594830914` matched 0.<br>The check as worded is met, and the server runtime is proven by the `node` event. Precision gap: the proof's count alone would pass on the browser duplicate, even if the server SDK sent nothing (see "Ranked gaps") | PASS |
| C39 | dev renders, production calls notFound; `next start` answers 404 for `/dev/sentry-check` and 200 for the 4 pages | Vitest `C39 sentry check: ...` (2 tests) passed. `env -u SENTRY_AUTH_TOKEN npm run build` exit 0, then `node scripts/check-prod-gate.mjs` exit 0, printing `GET / -> 200; GET /expected-payments -> 200; GET /alerts -> 200; GET /settings -> 200; GET /dev/components -> 404; GET /dev/sentry-check -> 404` | `frontend/tests/dev-gate.test.ts:32` - `digest).toBe('NEXT_HTTP_ERROR_FALLBACK;404')`; `:38-40` - `resolves.toBeDefined()`; `frontend/scripts/check-prod-gate.mjs:34-39,45` - expected map plus `if (got !== want) failed = true` | PASS |
| C40 | no `sentry-example-page` or `sentry-example-api` path under `app/` | Vitest `C40 no example routes` passed | `frontend/tests/sentry-config.test.ts:22` - `paths.filter(...sentry-example-(page or api) regex...)).toEqual([])` | PASS |
| C41 | 3 init files: DSN from env plus shared options, no tracing, replay or logs; 6 dataCollection values; no DSN literal in any git-tracked or would-track file | Vitest `C41 init options` and `C41 no dsn in source` passed | `frontend/tests/sentry-config.test.ts:28-31` - `toContain('dsn: process.env.NEXT_PUBLIC_SENTRY_DSN')`, `toContain('...sentryOptions')`, 4 forbidden strings `not.toContain`; `:34-41` - `dataCollection).toEqual({userInfo:false, cookies:false, httpHeaders:false, httpBodies:[], urlQueryParams:false, stackFrameVariables:false})`; `:47` - `git ls-files --cached --others --exclude-standard`; `:63` - `expect(leaks).toEqual([])`. The check text (`checks.md:149`) now names the same scope, so round 1's precision gap is closed | PASS |
| C42 | empty DSN: 4 pages, no pageerror, no request to a host containing "sentry" | PW `no sentry without dsn (C42)` passed at 313bfd5 with `NEXT_PUBLIC_SENTRY_DSN=` | `frontend/e2e/shell.spec.ts:351-352` - `expect(errors).toEqual([])`, `expect(sentryRequests).toEqual([])`.<br>Negative control, since `.env.local` now holds a DSN: the same test run without the empty override failed (`1 failed`, `sentryRequests` received 5 entries). So the assertion discriminates, and the empty override wins over `.env.local` | PASS |
| C43 | build exits 0 with SENTRY_AUTH_TOKEN unset | At 313bfd5:<br>- `env -u SENTRY_AUTH_TOKEN npm run build` exit 0. Next printed `Environments: .env.local`, so this build still read the token from `.env.local` and on its own is not a tokenless build.<br>- `SENTRY_AUTH_TOKEN= npm run build` exit 0. The C42 control shows an empty process variable wins over `.env.local`, so this build ran without a token. `.env.local` was not edited or moved | Command exit codes. `frontend/next.config.ts:12-16` - `withSentryConfig` does not require a token. The upload step is not observable in the log (`silent: !process.env.CI`), and C43 claims only the exit code | PASS |

## Coverage

The Sentry runtimes row was verified at 313bfd5. The C5 placements row is carried from bb7d02a, and the rest from 32e806a. Under `light` I did not recompute the coverage join, and I did not judge `Test policy` rows (`checks.md` has none).

| Set (size) | Recomputed from | Member -> proof | Unproven |
| --- | --- | --- | --- |
| nav link placements for metrics (2) | checks.md row added in bb7d02a | desktop nav: C5 `shell.spec.ts:118-120`; menu Dialog: C5 `shell.spec.ts:213-215` | - |
| Sentry runtimes (2) | Sentry API issue `platform` and `runtime` tag for run `check17909675334579` | client: C37, issue 7768827132 `platform: javascript`; server: C38, issue 7768827055 `platform: node`, `runtime: node v24.16.0` | - |

## Swept

Carried from 32e806a, except observability, which was verified at 313bfd5. No fix touched code these rows cite.

- **validation:** `frontend/lib/format.ts:10-12` (`Number.isSafeInteger`) and `:37-46` (regex plus a round-trip check on the date). Present.
- **failure modes:** `frontend/app/(app)/error.tsx:19-21` (`captureException`) and `:29` (`retry()`). Present.
- **authorization:** `frontend/app/dev/sentry-check/page.tsx:8` (`if (process.env.NODE_ENV === "production") notFound()`). Present.
- **dependency failure:** `frontend/lib/sentry-options.ts`, plus DSN-gated init in the 3 config files. Present. C42's negative control shows the DSN gate is real.
- **observability:** client and server events reach `headroom-web` (C37, C38 above). The boundary path, C26, is proven at component level.

## Handoff corrections ("Settled mid-build")

The C25 and C41 `dataCollection` items are carried from 32e806a. The C41 scoping item and the plan Impact row are carried from bb7d02a. The "Settled after round 2" line was verified at 313bfd5.

- **C25 `retry`:** faithful. The installed Next is 16.3.8. `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/error.md:117-121,155-157,331` names `retry` as the stable prop that re-fetches (since v16.3.0), and `reset` as the one that only clears the error state. Plan AC 25 already says `retry`.
- **C41 `dataCollection`:** faithful. In `@sentry/nextjs` 11.3.0, a grep for `sendDefaultPii` in `@sentry/core/build/types` finds nothing, and `types/datacollection.d.ts:27-108` declares the 6 named categories. Plan door 4 explicitly allows "the installed SDK's equivalent".
  - Observation, not a failure: the same interface also has `graphQL`, `genAI`, `databaseQueryData`, `queues` and `frameContextLines`, left at their defaults. None of them applies to this web app today.
- **C41 scoping to git-tracked files:** faithful to the plan, because open question 1 puts the DSN in the ignored `frontend/.env.local`. The C41 check text now states this scope.
- **Plan Impact "starter page" row:** it records that `e2e/home.spec.ts` is unchanged and `app/page.test.tsx` was deleted, which matches the diff.
- **Settled after round 2 (`SENTRY_READ_TOKEN`, project issues endpoint):**
  - **Faithful to C37 and C38:** the lookup stays inside `headroom-web` (the slug and DSN project id are confirmed), matches the full message plus the nonce, and is bounded at 60s.
  - **Never-sent nonce:** matches 0.
  - **Title matching:** it can only give a false FAIL, never a false PASS. If a later run groups into an older issue whose title carries a different nonce, the proof fails, which is safe.
  - **The handoff's own run:** it names a different run, `check179096744025449`. I did not rely on it; my run was `check17909675334579`.

## Faults injected

Carried from 32e806a. Fault injection does not run under profile `light`. Two non-mutating negative controls ran in this round: a never-sent nonce matched 0 Sentry issues, and C42 failed with the DSN active.

## Gate

Verified at 313bfd5:

- **Vitest:** `npx vitest run <7 files> --reporter=verbose` - 26 passed, 0 failed.
- **Playwright:** `NEXT_PUBLIC_SENTRY_DSN= npx playwright test e2e/shell.spec.ts --reporter=list` - 26 passed, 0 failed, on the first run.
- **Typecheck:** `npm run typecheck` - exit 0.
- **Build, token unset:** `env -u SENTRY_AUTH_TOKEN npm run build` - exit 0. Note that `.env.local` still supplies the token to this build.
- **Build, token empty:** `SENTRY_AUTH_TOKEN= npm run build` - exit 0. This is the tokenless build.
- **Production gate:** `node scripts/check-prod-gate.mjs` - exit 0, printing `GET / -> 200; GET /expected-payments -> 200; GET /alerts -> 200; GET /settings -> 200; GET /dev/components -> 404; GET /dev/sentry-check -> 404`.
- **Sentry proofs:** `set -a; . frontend/.env.local; set +a; bash .specs/features/07-web-app-shell/proofs.sh c37 c38` - exit 0, `PASS c37`, `PASS c38`.

## Ranked gaps

None of these fails a check. They are findings for the author.

1. **C38 precision gap.** `.specs/features/07-web-app-shell/proofs.sh:63` and `:45` count any issue whose title holds the server message. In development, the server action's error is re-raised in the browser and reported by the browser SDK (issue 7768826997, `platform: javascript`). So the proof would print `PASS c38` even if `sentry.server.config.ts` or `onRequestError` sent nothing. This round the server runtime is proven by the `platform: node` issue. To make the script prove it alone, filter on `platform == "node"` for C38, and on `javascript` for C37.
2. **The C43 proof command does not unset the token any more.** The command in `checks.md` is `env -u SENTRY_AUTH_TOKEN npm run build`, but `.env.local` now supplies `SENTRY_AUTH_TOKEN`, so that build is not tokenless. `SENTRY_AUTH_TOKEN= npm run build` (exit 0) is the run that actually tests C43. The check's proof line should use it.
3. **Minor: `proofs.sh` line endings.** 313bfd5 committed `proofs.sh` with CRLF endings on all 74 lines, plus a literal CR inside `tr -d '<CR>'` at `:45`; bb7d02a had 0 CR bytes. It runs under Git Bash, but a POSIX bash on Linux or CI would fail on a carriage return (`$'\r': command not found`).

Round 1's gaps 2, 3 and 4 were closed in bb7d02a. The blocked-Sentry gap was closed in 313bfd5.
