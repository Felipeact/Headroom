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
