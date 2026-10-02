# Headroom roadmap

*Last updated: October 1, 2026. Update this file whenever a milestone or gate is passed.*

**The plan:** generate the project with official tools, then build Headroom one short spec at a time until it's ready for its first clients. Scale up only after they confirm the product is worth paying for.

This file says **when** things happen. The specs in [`specs/`](specs/) say **what** to build, and `project-overview.md` explains **why**.

## How the work flows

- **Specs 01–05 set the project up** with official generators and commands, so almost nothing is written by hand.
- **Every later spec is short:** one piece of the product, finished and reviewed in a day or two.
- **A spec starts when its dependencies are done.** Specs are built one at a time on the `development` branch.

## Before spec 01

You set up the repository yourself. The specs assume it already has:

- a `main` branch for production, protected so changes arrive only through pull requests from `development`
- a `development` branch, where the work happens
- a root `.gitignore` that excludes `.env*` files, except `.env.example`
- these documents committed: `AGENTS.md`, `context/DESIGN.md`, `context/Roadmap.md`, `context/project-overview.md`, `context/specs/`, `docker-compose.yml`, and `design/`

## v1: first clients (about 3–4 months)

### Milestone 1: Set-up (about 1 week): done October 1, 2026

Specs 01–05 are done. Staging runs on Railway, and its service settings live in `.railway/railway.ts`.

| Spec | What it does | Depends on |
|---|---|---|
| [01](specs/01-setup-frontend.md) | Frontend scaffold with create-next-app and shadcn/ui | — |
| [02](specs/02-setup-backend.md) | Backend scaffold with uv and FastAPI | — |
| [03](specs/03-setup-database.md) | Local database and migrations | 02 |
| [04](specs/04-setup-tests-and-ci.md) | Tests and CI | 01, 03 |
| [05](specs/05-setup-railway-staging.md) | Staging on Railway | 01, 03 |

### Milestone 2: Foundations (1–2 weeks)

| Spec | What it does | Depends on |
|---|---|---|
| [06](specs/06-web-design-system.md) | Design system in the web app | 01 |
| [07](specs/07-web-app-shell.md) | App shell, translations, and formatting | 06 |
| [08](specs/08-api-errors-logging-monitoring.md) | API errors, logging, and monitoring | 03 |
| [09](specs/09-api-typed-client.md) | Typed API client | 01, 02 |
| [10](specs/10-accounts-login.md) | Login with Clerk | 07, 08, 09 |
| [11](specs/11-accounts-businesses-and-access.md) | Businesses and access (onboarding step 2) | 10 |

### Milestone 3: Bank data (2–3 weeks)

| Spec | What it does | Depends on |
|---|---|---|
| [12](specs/12-bank-connect.md) | Connect a bank (onboarding step 3) | 11 |
| [13](specs/13-bank-cash-accounts.md) | Choose cash accounts | 12 |
| [14](specs/14-bank-transaction-sync.md) | Transaction sync | 12 |
| [15](specs/15-bank-nightly-sync-job.md) | Nightly sync job | 05, 14 |
| [16](specs/16-bank-transaction-labels.md) | Transaction labels | 14 |
| [17](specs/17-bank-connection-settings.md) | Bank connection settings | 13, 14 |

### Milestone 4: Forecast (2–3 weeks)

| Spec | What it does | Depends on |
|---|---|---|
| [18](specs/18-forecast-sample-data.md) | Sample data | 14 |
| [19](specs/19-forecast-recurring-payments.md) | Recurring payments | 16, 18 |
| [20](specs/20-forecast-expected-payments.md) | Expected payments | 13, 14 |
| [21](specs/21-forecast-engine.md) | The 13-week forecast | 19, 20 |
| [22](specs/22-forecast-accuracy.md) | Forecast accuracy | 21 |
| [23](specs/23-forecast-minimum-balance-and-first-forecast.md) | Minimum balance and the first forecast (onboarding steps 4 and 5) | 21 |

### Milestone 5: Alerts and dashboard (about 2 weeks)

| Spec | What it does | Depends on |
|---|---|---|
| [24](specs/24-alerts-cash-gaps.md) | Cash gap alerts | 23 |
| [25](specs/25-alerts-suggested-fixes.md) | Suggested fixes | 24 |
| [26](specs/26-web-dashboard.md) | The dashboard | 13, 21, 24 |
| [27](specs/27-web-alert-page.md) | The alert page | 25 |

### Milestone 6: Emails and bookkeepers (1–2 weeks)

| Spec | What it does | Depends on |
|---|---|---|
| [28](specs/28-email-foundation.md) | Email foundation | 10 |
| [29](specs/29-email-alerts.md) | Alert emails | 25, 28 |
| [30](specs/30-email-weekly-digest.md) | Weekly digest | 15, 21, 28 |
| [31](specs/31-accounts-bookkeeper-invitations.md) | Bookkeeper invitations | 11, 28 |

### Milestone 7: Production (1–2 weeks)

| Spec | What it does | Depends on |
|---|---|---|
| [32](specs/32-launch-analytics-and-metrics.md) | Analytics and the weekly metrics report | 26 |
| [33](specs/33-launch-security-review.md) | Security review | 17, 20, 27, 29, 30, 31, 32 |
| [34](specs/34-launch-production.md) | Production | 33 |
| [35](specs/35-launch-legal-and-support.md) | Legal pages and support | 07 |
| [36](specs/36-launch-pilot.md) | Pilot launch | 34, 35 |

These times assume one or two people working with coding agents. Stretch them if you're building part-time. During milestone 1, also start the privacy policy, the terms of service, and the application for Plaid production access, and confirm Plaid's pricing, because these take time.

## Pilot: confirm clients (about 3 months)

- Onboard 5–10 small businesses in Canada, outside Quebec, at 50% off for three months. They pay in Canadian dollars through Stripe Payment Links, handled by hand.
- Add 1–2 bookkeepers who each bring a few clients.
- Hold a 15-minute check-in with each business every week.
- Track weekly use, alerts opened, and forecast accuracy, using the report from spec 32.

**Scale up only when:**
- at least 60% of pilot businesses still check their forecast every week after eight weeks
- at least 50% pay full price when the discount ends
- you have at least 2 testimonials, and at least 1 bookkeeper wants to add more clients

If the pilot doesn't meet these conditions, fix what it revealed before adding features.

## After clients confirm

Build from [`specs/later/`](specs/later/README.md), in its priority order, starting with billing in the app and alerts for a single account running short. Before building each one, split it into short specs in the same format as specs 01–36.

## Architecture by stage

| Stage | Structure | Runs on |
|---|---|---|
| v1 and pilot | A Next.js web app, one FastAPI application organized into modules, and an hourly jobs service | Railway, with staging and production environments |
| After clients confirm | Adds separate forecast workers and a message queue | Railway |
| At scale | Separate services | Kubernetes, only if Railway stops being enough |

## Decision log

| Decision | Choice | Why |
|---|---|---|
| Problem | Cash flow forecasting | A clear, recurring, costly pain, and a leading cause of small-business failure |
| Name | Headroom | Plain English, and it names the core promise: room between your balance and your minimum |
| First market | Small businesses in Canada, outside Quebec, billed in Canadian dollars | That's where the first clients are. Quebec needs French and has stricter privacy rules, so it comes later |
| First customers | Small businesses with 2–50 employees, with bookkeepers as a sales channel | The pain is sharpest for these businesses, and each bookkeeper can bring many clients |
| Pricing | $39 for Starter, $79 for Growth, and $15–20 per client for firms | Within the range of competitors' entry prices ($29–59 a month), and cheaper than Float and Dryrun |
| Scope | v1 is specs 01–36; everything else waits for paying clients | Prove that people will pay before building more |
| Validation | No separate validation phase; the paid pilot is the real test | Start building right away |
| Set-up | Official generators: create-next-app, shadcn/ui, uv, and Alembic | Generated code is accurate; boilerplate written from memory often isn't |
| Spec size | Short specs, one piece each, built in dependency order | Small changes are easier to get right and to review |
| Workflow | Work on the `development` branch; `main` is production only | One branch keeps the work simple; `main` changes only for a release |
| Tech stack | Next.js, FastAPI, and PostgreSQL | Python's data libraries for the forecast, and Next.js for the web app |
| Hosting | Railway, in its US East region | Simple and cheap while the idea is being proven. Railway has no Canadian region |
| Data location | Stored in the United States, and disclosed in the privacy policy | Canadian privacy law allows this when customers are told and the data is protected; the lawyer confirms it |
| Services | Clerk for login, Plaid for bank data, Resend for email, Sentry for errors, and PostHog for analytics | Proven services that cost little at small scale |
| Pilot billing | Stripe Payment Links, handled by hand | No billing code until clients confirm |
| Architecture | One application first; split into services only when there's evidence it's needed | Fast to build now, and easy to split later |
