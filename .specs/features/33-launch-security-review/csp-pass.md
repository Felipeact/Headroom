# CSP report-only pass (spec 33, C15)

Local production build (`npm run build`, `npm start -p 3200`), API on port 8100 over an embedded
Postgres (no Docker), 375 px wide, Playwright. Signed in as the Clerk test user (`clerk.signIn`
from `@clerk/testing`) with the Harbor Street sample loaded (`python -m app.fixtures.load
harbor_street`). Run on 2026-10-16. The console shows 0 errors on every screen; every
Content-Security-Policy message is a report-only violation, listed with a decision in
`context/security/rules.md`.

| Screen | Result | Note |
| --- | --- | --- |
| `/sign-in` | ok | renders the Clerk form; 0 console errors; violations recorded (2026-10-15) |
| `/` | ok | "Cash flow" with the sample's forecast, accounts and next 14 days; 0 console errors |
| `/alerts` | ok | "Alerts"; 0 console errors |
| `/settings/banks` | ok | both sample banks and their accounts; 0 console errors; adds the Plaid Link violations |
| `/settings/email` | ok | email preferences; 0 console errors |
| `/expected-payments` | ok | 0 console errors |
| `/settings/members` | ok | 0 console errors |
| `/settings/business` | ok | 0 console errors |
| `/settings/data` | ok | 0 console errors |
| `/onboarding/*` | ok | not reachable once the business exists: `/onboarding/business` redirects to `/` |
