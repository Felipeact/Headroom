# CSP report-only pass (spec 33, C15)

Local production build on port 3100, 375 px wide, Playwright. The console shows 0 errors; every
Content-Security-Policy message is a report-only violation, listed with a decision in
`context/security/rules.md`.

| Screen | Result | Note |
| --- | --- | --- |
| `/sign-in` | ok | renders the Clerk form; 0 console errors; violations recorded |
| `/` | not run | needs a signed-in Clerk session, which the agent cannot create |
| `/alerts` | not run | same |
| `/settings/banks` | not run | same |
| `/settings/email` | not run | same |
