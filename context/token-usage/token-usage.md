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
