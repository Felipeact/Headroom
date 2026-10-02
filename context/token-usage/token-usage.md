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
