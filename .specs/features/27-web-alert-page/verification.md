# 27 - The alert page verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 310f6b5..55e46c3 (fix diff 03c4dbf..55e46c3)
**Round**: 2 - scoped
**Verifier**: independent fresh sub-agent (author != verifier); not the author of this code, no inherited context; read-only over the real tree, fixed nothing

All 30 checks are proven. Round 1 (at 03c4dbf) failed only C26, because no test asserted the loading label "Loading". Commit 55e46c3 adds that assertion, and it passes at `HEAD`. The same commit changes the fix cards' React key from `fix.kind` to the index. C6–C14 and C15 were re-proven against that change and are green. The duplicate-key warning that round 1 noted under C12 is gone.

## Scope of this round

- **Fix diff** (`git diff 03c4dbf..55e46c3`), 2 files:
  - `frontend/app/(app)/states.test.tsx:48` adds `expect(busy!.getAttribute('aria-label')).toBe('Loading')`.
  - `frontend/components/alert-page/alert-view.tsx:101-102` changes `alert.fixes.map((fix, i) => ( <FixCard key={i} ...`, replacing `key={fix.kind}`.
- **Not PASS in round 1:** C26 only.
- **Proofs touching the changed files:**
  - C26 (states.test.tsx).
  - C6–C14 (the fix cards, alert-view.tsx).
  - C15 (the fix cards in the real page).
- **Proofs re-run:** every proof in `checks.md`, at `HEAD` 55e46c3. verify.md says proofs always re-run in full, and batched by runner that costs four invocations.
  - Checks in scope get fresh citations: C6–C15 and C26.
  - Every other check passed its proof again at 55e46c3. Its citation is **carried from 03c4dbf**, because the fix did not touch its file: `tests/alert-page.test.tsx`, `tests/alert-loader.test.ts`, `e2e/alert-page.spec.ts` and `services/core/tests/test_alerts_api.py` are unchanged in 03c4dbf..55e46c3.
- `git diff --quiet 55e46c3 -- frontend` succeeds, so the frontend that was tested is exactly `HEAD`.

## Binding sources

Profile `light`: step 1 does not run, and the plan marks no source as binding. The fix changes no copy or layout; it only changes a React key. Carried from 03c4dbf.

## Checks

Proofs run at `HEAD` 55e46c3, in one invocation per runner:

- **Vitest** (from `frontend`): `npx vitest run tests/alert-page.test.tsx tests/alert-loader.test.ts "app/(app)/states.test.tsx" -t "C1 header|C2 summary cards|C3 causes largest first|C4 arrives after|C5 row types|C6 fix cards|C7 pay early|C8 move payment|C9 draw credit|C10 financing|C11 counterparty first|C12 new lowest style|C13 text from messages|C14 no fixes|C16 dismiss shown|C17 dismiss pending|C18 dismiss success|C19 dismiss fails|C21 dismissed|C22 resolved|C23|C24 load outcomes" --reporter=verbose`.
  - Result: 27 passed, 4 skipped (states.test.tsx tests outside the filter), exit 0. Every test is listed by name as passed, including `app/(app)/states.test.tsx > C23 loading state`.
  - A separate run of "C12 new lowest style" prints 0 lines matching "same key", so the duplicate-key warning is gone.
- **Shell** (from `frontend`): `test -f "app/(app)/alerts/[alertId]/page.tsx" && test ! -e "app/(app)/alerts/[alertId]/loading.tsx"` exited 0.
- **Playwright** (from `frontend`): `npx playwright test e2e/alert-page.spec.ts -g "C15|C20|C25|C27|C28|C29|C30" --project=chromium --reporter=line | grep -v Clerk`.
  - Result: 9 passed (2 setup and 7 named), exit 0.
  - See "Environment note": the first attempt failed for a reason outside this feature.
- **pytest** (from `services/core`): `uv run pytest tests/test_alerts_api.py -k "test_alert_not_found" -v` gave 1 passed, 11 deselected, exit 0.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | back link `/`, "Cash gap", one h1 with the sample title | vitest "C1 header" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:71` `expect(back.getAttribute('href')).toBe('/')`; `:74-75` one h1 reading `'Cash falls below your $5,000 minimum the week of Nov 9'` | PASS |
| C2 | Projected low card in the warning style, Short by card without it | vitest "C2 summary cards" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:82-85` text `'Projected low $3,150 Week of Nov 9'`, `bg-warning-bg` true for low and false for short | PASS |
| C3 | causes listed largest first | vitest "C3 causes largest first" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:89-94` `toEqual(['Coastal Supply Co Thu, Nov 12 · Expected payment −$14,500', 'Payroll Fri, Nov 13 · Every 2 weeks −$11,200'])` | PASS |
| C4 | arrives-after row: order, colour, absence, counterparty fallback | vitest "C4 arrives after" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:101` order `['cause-row','cause-row','arrives-row']`; `:104-105` `text-positive`; `:109` absent `toBeNull()`; `:113` `'Birch & Co Ltd ...'` | PASS |
| C5 | 8 row types, table-driven | vitest "C5 row types" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:117-130`: `toHaveLength(8)` at `:127`, each row `toBe(\`Coastal Supply Co Thu, Nov 12 · ${expected} −$14,500\`)` | PASS |
| C6 | 3 fix cards in API order, with their new lowest balances | vitest "C6 fix cards" passed at 55e46c3 (re-proven against the key change) | `frontend/tests/alert-page.test.tsx:139` `expect(cards).toHaveLength(3)`; `:140` `toEqual(['pay_early', 'move_payment', 'draw_credit'])`; `:141-144` `'New lowest balance $12,750'`, `'$17,650'`, `'$5,150'`. The keyed map is at `frontend/components/alert-page/alert-view.tsx:101-102` | PASS |
| C7 | pay_early title and body | vitest "C7 pay early" passed at 55e46c3 (re-proven) | `frontend/tests/alert-page.test.tsx:151-153` `'Ask Birch & Co to pay a week early'` and `'Their $9,600 invoice is due Nov 17. Ask them to pay by Nov 10. A small early-payment discount can help.'` | PASS |
| C8 | move_payment title and body | vitest "C8 move payment" passed at 55e46c3 (re-proven) | `frontend/tests/alert-page.test.tsx:160-161` `'Move the Coastal Supply Co payment by a week'` / `'Ask Coastal Supply Co to move the $14,500 payment to Nov 19.'` | PASS |
| C9 | draw_credit text with and without an arrives-after item | vitest "C9 draw credit" passed at 55e46c3 (re-proven) | `frontend/tests/alert-page.test.tsx:167-168` `'Draw $2,000 on your line of credit'` / `'...Repay it when Birch & Co pays.'`; `:173` `'You have $20,000 available. Repay it on Nov 17.'` | PASS |
| C10 | financing card | vitest "C10 financing" passed at 55e46c3 (re-proven) | `frontend/tests/alert-page.test.tsx:179-182` `toHaveLength(1)`, `'Arrange $2,000 of short-term financing'`, `'Borrow it on Nov 9 and repay it on Nov 16, after the gap.'` | PASS |
| C11 | counterparty used first | vitest "C11 counterparty first" passed at 55e46c3 (re-proven) | `frontend/tests/alert-page.test.tsx:188` `toBe('Ask Birch and Company Ltd to pay a week early')` | PASS |
| C12 | above or equal to the minimum: positive style with a check; below: warning, no check | vitest "C12 new lowest style" passed at 55e46c3 (re-proven). The test feeds three `draw_credit` fixes, and the index key now renders all three with no duplicate-key warning | `frontend/tests/alert-page.test.tsx:196-197` `bg-positive-bg` true and `fix-ok` not null for 515000 and 500000; `:199-201` for 499999, `bg-warning-bg` true, `bg-positive-bg` false, `fix-ok` `toBeNull()` | PASS |
| C13 | every text node is a message key or an alert value | vitest "C13 text from messages" passed at 55e46c3 (re-proven) | `frontend/tests/alert-page.test.tsx:234` `expect(stray).toEqual([])` | PASS |
| C14 | no fixes: no section, causes still shown | vitest "C14 no fixes" passed at 55e46c3 (re-proven) | `frontend/tests/alert-page.test.tsx:239-241` heading `toBeNull()`, `'New lowest balance'` `toBeNull()`, `cause-row` `toHaveLength(2)` | PASS |
| C15 | the dashboard link lands on `/alerts/{id}` with 200; the API's values in DOM order at 375 px | playwright "C15" passed at 55e46c3 (re-proven against the key change) | `frontend/e2e/alert-page.spec.ts:68` pathname `toBe(\`/alerts/${alert.id}\`)`; `:70` `status()).toBe(200)`; `:84` `cards toHaveCount(alert.fixes.length)`; `:85-86` per fix `toContainText(money(fix.new_lowest_balance_cents))`; `:101` DOM order `toBe(true)` | PASS |
| C16 | Dismiss button with the note after it | vitest "C16 dismiss shown" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:248-250` | PASS |
| C17 | called once, disabled, "Dismissing…" while pending | vitest "C17 dismiss pending" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:259-263` | PASS |
| C18 | success: `push("/")` once and the toast | vitest "C18 dismiss success" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:271-273` | PASS |
| C19 | failure: no push, button enabled again, role=alert message | vitest "C19 dismiss fails" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:280-283` | PASS |
| C20 | a real dismissal returns to `/` and the card stays gone | playwright "C20" passed at 55e46c3; citation carried from 03c4dbf | `frontend/e2e/alert-page.spec.ts:108-115` | PASS |
| C21 | dismissed note uses the Toronto date, no button | vitest "C21 dismissed" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:289-291` | PASS |
| C22 | resolved note, no button | vitest "C22 resolved" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:296-297` | PASS |
| C23 | loader outcomes and their Sentry reports | vitest `C23` (5 tests) passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-loader.test.ts:28`, `:37-39`, `:44-45`, `:50-51` | PASS |
| C24 | not_found calls notFound(); the other failures reject | vitest "C24 load outcomes" passed at 55e46c3; citation carried from 03c4dbf | `frontend/tests/alert-page.test.tsx:303-314` | PASS |
| C25 | not-found state with noindex; a foreign id is 404 at the API | playwright "C25" and pytest `test_alert_not_found` passed at 55e46c3; citations carried from 03c4dbf | `frontend/e2e/alert-page.spec.ts:119-124`; `services/core/tests/test_alerts_api.py:238-239` | PASS |
| C26 | the route sits under `(app)` with no `loading.tsx` of its own; the loading state renders `aria-busy="true"` with the label "Loading" | shell test exit 0; vitest "C23 loading state" passed at 55e46c3 (re-proven, round-1 FAIL) | `frontend/app/(app)/states.test.tsx:46-47` `querySelector('[aria-busy="true"]')).not.toBeNull()`; `frontend/app/(app)/states.test.tsx:48` `expect(busy!.getAttribute('aria-label')).toBe('Loading')`, a literal next to the assertion. The label is rendered at `frontend/app/(app)/loading.tsx:8` `aria-label={t("loading")}`, with `frontend/messages/en.json:25` `"loading": "Loading"` | PASS |
| C27 | signed out ends on `/sign-in` | playwright "C27" passed at 55e46c3; citation carried from 03c4dbf | `frontend/e2e/alert-page.spec.ts:198` | PASS |
| C28 | 375 px fit, 44 px targets, dismiss as wide as the cards; 640 px column at 1280 px | playwright "C28" passed at 55e46c3; citation carried from 03c4dbf | `frontend/e2e/alert-page.spec.ts:130`, `:138`, `:141`, `:145` | PASS |
| C29 | keyboard order, focus outline, Enter dismisses | playwright "C29" passed at 55e46c3; citation carried from 03c4dbf | `frontend/e2e/alert-page.spec.ts:162`, `:170`, `:173` | PASS |
| C30 | axe clean at 375 and 1280 px and on the not-found state | playwright "C30" passed at 55e46c3; citation carried from 03c4dbf | `frontend/e2e/alert-page.spec.ts:183`, `:189` | PASS |

### Level and sampling notes (not failures)

- **C26:** the fix closes round 1's gap exactly as recommended. The expected value `'Loading'` is a literal at the assertion, so renaming the `States.loading` message or dropping `aria-label` from `loading.tsx` now turns the test red.
- **Fix-card key:**
  - The index key is stable here: the list is rendered on the server from one API response and never reordered or edited on the client.
  - It removes round 1's latent duplicate-key problem, which would have appeared if the API ever repeated a fix kind.
  - `data-kind` is still emitted per card, so C6's order assertion (`frontend/tests/alert-page.test.tsx:140`) still reads the kinds.
- **C29, C25, C15:** the round-1 notes on these still apply (carried from 03c4dbf); the fix touched none of them.

### Environment note (outside this feature)

- **What failed:** the first Playwright attempt at 55e46c3 failed 6 of the 9 tests in `loadSample` (`frontend/e2e/dashboard-steps.ts:8`).
  - `uv run python -m app.fixtures.load` exited with "Settings are missing or invalid: email_sender, email_from, email_mailing_address, web_url, api_public_url, clerk_secret_key".
- **Cause:** someone has uncommitted, in-progress spec 28 edits in the working tree. The edited files are:
  - `services/core/app/settings.py`
  - `services/core/pyproject.toml`
  - `services/core/uv.lock`
  - `services/core/tests/conftest.py`
  - `services/core/tests/test_settings.py`

  They add required settings, and they are not part of 55e46c3.
- **Workaround:** without touching any file, I reran with these variables set in the shell for that one run only:
  - placeholder values for `EMAIL_SENDER=console`, `EMAIL_FROM`, `EMAIL_MAILING_ADDRESS`, `WEB_URL` and `API_PUBLIC_URL`
  - `CLERK_SECRET_KEY` taken from `frontend/.env.local` (a test key, not printed)
- **Result:** 9 of 9 passed.
- **What was tested:** the frontend under test is exactly `HEAD`. The backend is `HEAD` plus spec 28's uncommitted settings additions, which the alert page does not use. Spec 28's builder must add those variables to the e2e environment, or the shared Playwright suite stays red for everyone.

## Coverage

Profile `light`: the Coverage recompute does not run. Carried from 03c4dbf. The fix adds no branch and no set member.

## Faults injected

Profile `light`: fault injection does not run.

## Swept existing

No `## Swept` row resolves to `existing`. The two references round 1 re-read are carried from 03c4dbf:

- `services/core/app/modules/alerts/service.py:381`
- `frontend/components/alert-page/dismiss-alert.tsx:39`

The fix touched neither file.

## Gate

| Runner | Passed | Failed | Exit |
| --- | --- | --- | --- |
| Vitest | 27 | 0 | 0 |
| Playwright | 9 | 0 | 0 (rerun with the environment workaround above) |
| pytest | 1 | 0 | 0 |
| Shell proof | - | - | 0 |

All runs are at 55e46c3.

## Ranked gaps

None.
