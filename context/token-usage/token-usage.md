# Token usage

Context used per request, measured against a context window of about 250,000 tokens. Counts are estimates taken at the end of each request.

| Zone | Share of the window | Quality |
| --- | --- | --- |
| Smart zone | 0% to 40% | High |
| Attention degrades | 40% to 60% | Medium |
| Low quality | 60% to 100% | Low |

| Feature | Token | Quality |
| --- | --- | --- |
| Spec 01: frontend scaffold (plan, checks, build) | ~65,000 (~26%) | High (smart zone) |
| Spec 02: backend scaffold (plan) | ~45,000 (~18%) | High (smart zone) |
| Spec 02: backend scaffold (checks, build, verify) | ~90,000 (~36%) | High (smart zone) |
| Spec 03: database and migrations (plan) | ~55,000 (~22%) | High (smart zone) |
| Spec 03: database and migrations (checks, build) | ~75,000 (~30%) | High (smart zone) |
| Spec 04: tests and CI (plan) | ~50,000 (~20%) | High (smart zone) |
| Spec 04: tests and CI (checks, build) | ~95,000 (~38%) | High (smart zone) |
| Spec 04: tests and CI (verify, the-judge review, cleanup fix) | ~140,000 (~56%) | Medium (attention degrades) |
| Spec 04: verifier sub-agent (separate context) | ~93,000 (~37%) | High (smart zone) |
| Spec 05: staging on Railway (plan) | ~70,000 (~28%) | High (smart zone) |
| Spec 05: staging on Railway (checks, provisioning, IaC switch, build, verify rounds) | ~140,000 (~56%) | Medium (attention degrades) |
| Spec 05: verifier sub-agent, rounds 1 and 2 (separate context) | ~123,000 (~49%) | Medium (attention degrades) |
| Spec 08: API errors, logging, and monitoring (plan) | ~75,000 (~30%) | High (smart zone) |
| Spec 08: API errors, logging, and monitoring (checks, build S1-S4) | ~110,000 (~44%) | Medium (attention degrades) |
| Spec 06: design system in the web app (plan) | ~75,000 (~30%) | High (smart zone) |
| Spec 06: design system in the web app (checks, build, verify) | ~135,000 (~54%) | Medium (attention degrades) |
| Spec 06: verifier sub-agent (separate context) | ~108,000 (~43%) | Medium (attention degrades) |
| Spec 07: app shell, translations, and formatting (plan) | ~95,000 (~38%) | High (smart zone) |
| Spec 07: app shell, translations, and formatting (checks, build S1-S6, round 1 fixes) | ~150,000 (~60%) | Medium (attention degrades) |
| Spec 07: verifier sub-agent, rounds 1 and 2 (separate context) | ~151,000 (~60%) | Medium (attention degrades) |
| Spec 08: API errors, logging, and monitoring (external proofs C21, C22, C32, Railway apply, done) | ~80,000 (~32%) | High (smart zone) |
| Spec 08: verifier sub-agent (separate context) | ~110,000 (~44%) | Medium (attention degrades) |
| Spec 09: typed API client (plan) | ~65,000 (~26%) | High (smart zone) |
| Spec 09: typed API client (checks, build, CI proofs, verify rounds 1-3 fixes) | ~150,000 (~60%) | Medium (attention degrades) |
| Spec 09: verifier sub-agent, rounds 1-3 (separate context) | ~146,000 (~58%) | Medium (attention degrades) |
| Spec 09: typed API client (the-judge review, F1/F2 fixes, verify round 4) | ~70,000 (~28%) | High (smart zone) |
| Spec 10: login with Clerk (plan) | ~115,000 (~46%) | Medium (attention degrades) |
| Spec 10: login with Clerk (checks, build, verify rounds 1-2 fixes) | ~190,000 (~76%) | Low (past 60%) |
| Spec 10: verifier sub-agent, rounds 1-2 (separate context) | ~173,000 (~69%) | Low (past 60%) |
| Spec 11: businesses and access (plan) | ~75,000 (~30%) | High (smart zone) |
| Spec 11: businesses and access (checks, build, verify round 1 fixes, close) | ~150,000 (~60%) | Medium (attention degrades) |
| Spec 11: verifier sub-agent, rounds 1-2 (separate context) | ~143,000 (~57%) | Medium (attention degrades) |
| Spec 12: connect a bank (plan) | ~70,000 (~28%) | High (smart zone) |
| Spec 12: connect a bank (checks, build S1-S5, sandbox and e2e proofs) | ~150,000 (~60%) | Medium (attention degrades) |
| Spec 12: verifier sub-agents, rounds 1-2 (separate contexts) | ~152,000 + ~107,000 (~61%, ~43%) | Medium (attention degrades) |
| Spec 13: choose cash accounts (plan) | ~75,000 (~30%) | High (smart zone) |
| Spec 13: choose cash accounts (checks, build S1-S5, sandbox and e2e proofs) | ~185,000 (~74%) | Low (past 60%) |
| Spec 13: verifier sub-agent, round 1 (separate context) | ~136,000 (~54%) | Medium (attention degrades) |
| Spec 14: transaction sync (plan, checks) | ~95,000 (~38%) | High (smart zone) |
| Spec 14: transaction sync (build S1-S7, proofs c46, c47) | ~180,000 (~72%) | Low (past 60%) |
| Spec 14: verifier sub-agents, rounds 1-2 (separate contexts) | ~145,000 + ~108,000 (~58%, ~43%) | Medium (attention degrades) |
| Spec 15: nightly sync job (plan) | ~70,000 (~28%) | High (smart zone) |
| Spec 15: nightly sync job (checks, build S1-S5, staging, verifier rounds 1-2, date fix) | ~200,000 (~80%) | Low (past 60%) |
| Spec 15: close-out (verifier round 3 sub-agent ~125,000 separate context, the-judge, lessons) | ~45,000 (~18%) | High (smart zone) |
| Spec 16: transaction labels (plan) | ~70,000 (~28%) | High (smart zone) |
| Spec 16: transaction labels (checks, build, proofs) | ~85,000 (~34%) | High (smart zone) |
| Spec 16: verifier sub-agent, round 1 (separate context) | ~120,000 (~48%) | Medium (attention degrades) |
| Spec 16: close-out (gate check, the-judge local review, F1 repro) | ~35,000 (~14%) | High (smart zone) |
| Spec 16: F1 fix (AC 27, C29) and verifier round 2 (sub-agent ~99,000 separate context) | ~20,000 (~8%) | High (smart zone) |
| Spec 17: bank connection settings (plan, checks, build, proofs) | ~150,000 (~60%) | Medium (attention degrades) |
| Spec 17: verifier sub-agent, round 1 (separate context) | ~154,000 (~62%) | Low (past 60%) |
| Spec 18: sample data (plan, checks, build, proofs) | ~135,000 (~54%) | Medium (attention degrades) |
| Spec 18: verifier sub-agent, round 1 (separate context) | ~129,000 (~52%) | Medium (attention degrades) |
| Spec 19: recurring payments (plan) | ~80,000 (~32%) | High (smart zone) |
| Spec 19: recurring payments (checks, build, proofs, 2 AC 4 amendments) | ~150,000 (~60%) | Medium (attention degrades) |
| Spec 19: verifier sub-agents, rounds 1-2 (separate contexts) | ~136,000 + ~78,000 (~54%, ~31%) | Medium (attention degrades) |
| Spec 20: expected payments (resume: proofs, local DB upgrade, 3 e2e fixes, C45 amendment) | ~85,000 (~34%) | High (smart zone) |
| Spec 20: verifier sub-agents, rounds 1-2 (separate contexts) | ~153,000 + ~86,000 (~61%, ~34%) | Low (past 60%) |
| Spec 21: the 13-week forecast (plan, 2 user decisions) | ~180,000 (~72%) | Low (past 60%) |
| Spec 21: the 13-week forecast (build, proofs, 44 checks) | ~140,000 (~56%) | Medium (attention degrades) |
| Spec 21: verifier sub-agent, round 1 (separate context) | ~139,000 (~56%) | Medium (attention degrades) |
| Spec 22: forecast accuracy (plan, prototype, 3 user decisions, build T1-T8) | ~175,000 (~70%) | Low (past 60%) |
| Spec 22: verifier sub-agent (separate context) | ~123,000 (~49%) | Medium (attention degrades) |
| Spec 24: cash gap alerts (plan research, engine probe, 2 user decisions; stopped for the realignment spike) | ~165,000 (~66%) | Low (past 60%) |
| Spec 23a + 24: realignment spike (design B, 7 conditions), plans for 23a and 24 | ~110,000 (~44%) | Medium (attention degrades) |
| Spec 23a + 24: checks, build, 2 verifier dispatches, C26 amendment, C9/C21 clock fix | ~130,000 (~52%) | Medium (attention degrades) |
| Spec 25: suggested fixes (plan, sample forecast probe, 2 open questions) | ~75,000 (~30%) | High (smart zone) |
| Spec 25: checks, build, verifier dispatch, 2 gap tests | ~70,000 (~28%) | High (smart zone) |
| Spec 25: verifier sub-agent (separate context) | ~109,000 (~44%) | Medium (attention degrades) |
| Spec 26: the dashboard (plan, 2 user decisions) | ~85,000 (~34%) | High (smart zone) |
| Spec 26: checks, S1 API build (stopped on 2 environment blockers) | ~120,000 (~48%) | Medium (attention degrades) |
| Spec 26: resume, S1 proofs, frontend build and Vitest proofs (stopped: stale test API on 8100) | ~175,000 (~70%) | Low (past 60%) |
| Spec 26: e2e fixes, perf, 2 verifier dispatches, gap fixes, visual pass | ~95,000 (~38%) | High (smart zone) |
| Spec 26: verifier sub-agents, rounds 1-2 (separate contexts) | ~132,000 + ~120,000 (~53%, ~48%) | Medium (attention degrades) |
| Fix: Sentry router hook, local API_URL, push | ~55,000 (~22%) | High (smart zone) |
| Spec 27: the alert page (plan) | ~60,000 (~24%) | High (smart zone) |
| Spec 27: re-check plan for review | ~30,000 (~12%) | High (smart zone) |
| Spec 28: email foundation (plan) | ~85,000 (~34%) | High (smart zone) |
| Spec 27: checks, build, 2 verifier dispatches, C26 fix, visual pass | ~95,000 (~38%) | High (smart zone) |
| Spec 27: verifier sub-agents, rounds 1-2 (separate contexts) | ~117,000 + ~100,000 (~47%, ~40%) | Medium (attention degrades) |
| Spec 28: email foundation (checks, build, API + web, e2e) | ~200,000 (~80%) | Low (past 60%) |
| Spec 28: verifier sub-agents, rounds 1-3 (separate contexts) | ~147,000 + ~111,000 + ~120,000 (~59%, ~44%, ~48%) | Medium (attention degrades) |
| Spec 28: the-judge review and fixes (F1, F3) | ~30,000 (~12%) | High (smart zone) |
| Spec 29: alert emails (plan) | ~140,000 (~56%) | Medium (attention degrades) |
| Audit: missed steps across Done specs 01-28 | ~110,000 (~44%) | Medium (attention degrades) |
| Re-audit: specs 01-28 at HEAD (all suites, sandbox proofs, e2e), .env.example quoting fix | ~95,000 (~38%) | High (smart zone) |
| Spec 29: proofs on local Postgres, C5/C6/C9 log-capture fix, F1 fix (non-CAD render), verifier rounds 1-2 | ~85,000 (~34%) | High (smart zone) |
| Spec 29: verifier sub-agent, round 1 (separate context) | ~113,000 (~45%) | Medium (attention degrades) |
| Spec 29: verifier sub-agent, round 2 (separate context) | ~82,000 (~33%) | High (smart zone) |
| Spec 29: C22 evidence (AD-117), mark Done, full suite, push | ~25,000 (~10%) | High (smart zone) |
| Spec 29: verifier sub-agent, round 3 (separate context) | ~91,000 (~36%) | High (smart zone) |
| Spec 32: analytics and metrics report (plan, checks, build web + API) | ~170,000 (~68%) | Low (past 60%) |
| Fix: /welcome redirect to localhost (checks, build, proofs) | ~90,000 (~36%) | High (smart zone) |
| Fix: /welcome redirect, verifier sub-agent (separate context) | ~68,000 (~27%) | High (smart zone) |
| Spec 33: signed-in CSP pass (embedded Postgres), 2FA table, incident rehearsal and plan fixes, decision log | ~95,000 (~38%) | High (smart zone) |
| Spec 33: verifier rounds 1-3 (separate contexts), the-judge review, F1-F4 fixes, mark Done | ~150,000 (~60%) | Medium (attention degrades) |
| Spec 34: plan (no domain, Plaid Trial research), checks, local build (alerts, IaC, credential check, runbook) | ~140,000 (~56%) | Medium (attention degrades) |
| Spec 17a: Flinks provider plan (Flinks docs research), checks | ~75,000 (~30%) | High (smart zone) |
| Spec 17a: build (schema rename, Flinks client, service dispatch, API, web), proofs, e2e pass | ~150,000 (~60%) | Medium (attention degrades) |
| Spec 17a: verifier round 1 (separate context) | ~177,000 (~71%) | Low (past 60%) |
| Spec 17a: round-1 fixes (Sentry redaction, parsing, tests), verifier round 2 (separate context, ~128,000) | ~60,000 (~24%) | High (smart zone) |
| Spec 17a: the-judge review and fixes (providers.py extraction, token refresh, fixtures) | ~40,000 (~16%) | High (smart zone) |
| Spec 17b: provider search (Plaid RBC OAuth check, Mastercard, Yodlee, direct RBC), plan, checks | ~95,000 (~38%) | High (smart zone) |
| Spec 17b: build (sandbox probes, settings, migration, Yodlee client, service, API, web, tests), proofs, e2e | ~210,000 (~84%) | Low (past 60%) |
| Spec 17b: verifier rounds 1-3 (separate contexts, ~194k, ~138k, ~150k) | ~480,000 across three contexts (each 55-78%) | Low to Medium |
| Spec 17b: verification fixes (rounds 1-2), C4 reword, decisions, STATE | ~110,000 (~44%) | Medium (attention degrades) |
