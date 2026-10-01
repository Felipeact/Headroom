# AGENTS.md

Instructions for AI coding agents working in this repository. Humans should start with `project-overview.md` and `Roadmap.md`.

## Project overview

Headroom is a cash flow forecasting product for small businesses in Canada with 2–50 employees, and for the bookkeepers who serve them. It connects to a business's bank accounts through Plaid. From that data it:

- forecasts the combined cash balance 13 weeks ahead
- warns when the balance will drop below the minimum the owner chose
- names the payments that cause each drop
- suggests fixes

**Current stage: v1 for the first clients, specs 01–36** (see `Roadmap.md`). Build only what your spec calls for. The features in `specs/later/` wait until clients confirm.

This file is the source of truth for commands. If a command here fails or is out of date, update the command or this file in the same change.

## How the work is organized

- The work is a series of short specs in `specs/`, numbered in build order. Each spec is one small piece that can be finished and reviewed in a day or two.
- A spec can start once every spec in its "Depends on" line is Done. Specs whose dependencies are all Done can be built at the same time, each in its own worktree.
- The repository is set up by hand before spec 01 (see "Before spec 01" in `Roadmap.md`).
- The set-up specs (01–05) create the project with official generators and commands, so they involve almost no hand-written code.

### Spec workflow

- **Start:** before you write any code for a spec, set its status to In progress in the spec file. Update the status whenever it changes (Not started, In progress, or Done), and set it to Done only once every "Done when" item passes.
- **Finish:** at the end of every implementation that adds or changes a screen, validate that screen with Playwright in the running app. Check the loading, empty, and error states, the layout at 375 pixels wide, and keyboard-only use. Fix anything that fails before you call the work done.

## Don't guess

AI agents make most of their mistakes when they write code from memory. These rules prevent most of them:

- **Generate, don't hand-write.** When a tool can create something, use the tool:
  - `create-next-app`
  - `npx shadcn@latest add`
  - `uv add`
  - `alembic revision`
  - `npm init playwright@latest`

  Never hand-write lockfiles, generated types, or components that the shadcn CLI provides.
- **Read the docs first.** Before using a library for the first time in this repository, read its official docs or the installed package's source. Specs link the docs they need.
- **Never invent an API.** If you can't confirm that a function, CLI flag, or config key exists in the installed version, stop and ask.
- **Stay small.** Change only what your spec needs. Don't refactor unrelated code.
- **Prove it.** Every "Done when" item needs a passing test, or a check someone else can repeat.

## Branches and worktrees

- `main` is production. Never commit to it directly.
- `development` collects finished specs and deploys to staging.
- Each spec gets its own branch, `spec/NN-name`, in its own worktree created from `development`:

```bash
# From the main checkout
git worktree add ../headroom-worktrees/12-bank-connect -b spec/12-bank-connect development

# .env.local files aren't in git, so copy them into the new worktree
cp services/core/.env.local ../headroom-worktrees/12-bank-connect/services/core/
cp frontend/.env.local ../headroom-worktrees/12-bank-connect/frontend/
```

- Work only inside your own worktree, and keep it current with `git rebase development`.
- When the spec's "Done when" items pass, open a pull request into `development`.
- After the pull request merges, remove the worktree with `git worktree remove <path>`, then delete the branch.

### Shared files

- **Lockfiles** (`uv.lock` and `package-lock.json`): never resolve a conflict in them by hand. Take `development`'s version, then rerun `uv lock` or `npm install`.
- **Generated files** (`contracts/openapi.json` and `frontend/lib/api/schema.d.ts`): regenerate them. Never edit them by hand.
- **Design files** (`DESIGN.md` and `design/`): change them only in a separate pull request, on a branch named `design/<what-changes>`.

## Repository layout

Once the set-up specs are done, the repository looks like this:

```text
.
├── AGENTS.md
├── DESIGN.md                   # The design system and writing guidelines
├── Roadmap.md
├── project-overview.md
├── docker-compose.yml          # Local Postgres, shared by every worktree
├── contracts/openapi.json      # Spec 09: generated from the API, never edited by hand
├── design/mockups/             # The source of every screen mockup
├── frontend/                   # Spec 01: created by create-next-app
│   ├── AGENTS.md               # Created by create-next-app; adds Next.js guidance to this file
│   ├── app/                    # Routes
│   ├── components/ui/          # Spec 06: shadcn/ui components
│   ├── lib/api/                # Spec 09: the typed API client
│   ├── lib/format.ts           # Spec 07: money and date formatting
│   └── messages/en.json        # Spec 07: all interface text
├── services/
│   ├── core/                   # Spec 02: created by uv init
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── settings.py     # Spec 03
│   │   │   ├── db.py           # Spec 03
│   │   │   ├── jobs/           # Spec 15: the hourly job runner
│   │   │   ├── fixtures/       # Spec 18: sample data
│   │   │   └── modules/        # accounts, bank_sync, forecasting, alerts, notifications
│   │   ├── migrations/         # Spec 03: Alembic
│   │   └── tests/
│   └── forecast-service/       # Later; not used in v1
├── specs/                      # v1 specs 01–36; specs/later/ holds the backlog
└── k8s/                        # Later; not used in v1
```

## Setup

After specs 01–03 are done:

```bash
# Shared Postgres: run once, from any worktree
docker compose up -d postgres

# Your worktree's own database: run once per worktree, named after your spec number
docker compose exec postgres createdb -U headroom headroom_12

# API (from services/core)
cp .env.example .env.local            # point DATABASE_URL at your database; use sandbox and test keys only
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py        # API docs at http://localhost:8000/docs

# Web (from frontend, in a second terminal)
cp .env.example .env.local
npm install
npm run dev                           # http://localhost:3000
```

If several worktrees run servers at the same time, give each one its own ports. For example, use `--port 8012` for the API and `npm run dev -- -p 3012` for the web app.

Never put production credentials in a local environment file. Never commit any `.env*` file except `.env.example`.

## Before you finish a task

Run the checks for every area you touched. All of them must pass. Never skip, disable, or weaken a check to make it pass.

```bash
# API (from services/core)
uv run ruff format --check . && uv run ruff check .
uv run mypy app
uv run pytest

# Web (from frontend)
npm run lint && npm run typecheck && npm test && npm run build
```

Some changes need an extra step:

- **Database model changed:** create a migration with `uv run alembic revision --autogenerate -m "short description"`. Then read the generated file and correct it before committing.
- **API endpoint changed:** run `uv run python -m app.export_openapi` (from `services/core`), then `npm run api:types` (from `frontend`). Commit both generated files.
- **Forecasting logic changed:** run the backtest from spec 22, and put the accuracy before and after your change in the pull request description.

## Architecture rules

### Modules

The API is one application made of five modules in `services/core/app/modules/`: `accounts`, `bank_sync`, `forecasting`, `alerts`, and `notifications`. Each one may become its own service later, so keep them independent.

```text
modules/<name>/
├── api.py          # FastAPI router: HTTP handling only, no business logic
├── service.py      # The module's public functions
├── models.py       # The module's database tables
├── repository.py   # Database access, limited to the module's own tables
└── events.py       # Events the module publishes or handles
```

- **Imports:** a module may use another module only through that module's `service.py` and `events.py`.
- **Data ownership:** each module owns its tables. Never query or join another module's tables.
- **Events:** modules notify each other through the in-process event bus from spec 14.
  - The v1 events are `transactions.synced`, `forecast_inputs.changed`, `forecast.updated`, `alert.created`, `alert.updated`, and `alert.resolved`.
  - Name new events `noun.past_tense_verb`.
- **Idempotency:** every event handler and job must produce the same result if it runs twice.

### API

- All routes live under `/v1`.
- Errors use RFC 9457 problem details (`application/problem+json`).
- The web app calls the API only from the server. The browser never calls it directly.

### Forecasting

- To add a forecasting method, write a new `ForecastStrategy` class and register it. Never edit `CashFlowForecastService` to add one.
- The `FORECAST_STRATEGY` setting selects which strategy runs.
- Every strategy returns exactly 13 weeks, and never fails when history is empty or short.

### Alerts

Every alert explanation names the specific payments that cause the gap.

## Domain conventions

- **Money:** store amounts as integers in the smallest currency unit (`amount_cents: int`), together with an ISO 4217 currency code. v1 uses only Canadian dollars (CAD), but every amount still carries its code. Never store, compare, or display money as a float. Forecasting math may use floats internally, but round to cents before a value leaves the forecasting module.
- **Sign:** positive means money coming in, and negative means money going out. Plaid reports outgoing money as positive, so flip the sign once, in `bank_sync`, and nowhere else.
- **Time:** store timestamps in UTC (`timestamptz`). Bank transaction dates are plain dates, not datetimes. Forecast weeks start on Monday in the business's own time zone.
- **Tenancy:** every row of customer data has a `business_id`. Repositories require the current business, and no query may run without filtering on it. Bookkeepers see only the businesses they're members of.
- **What counts as cash:** only included checking and savings accounts. Credit cards and lines of credit never count as cash. Transfers between the business's own accounts are never income or spending.

## Security and data handling

This product handles bank data, so these rules are hard requirements.

- Never log, print, or return in an API response any of the following:
  - Plaid access tokens
  - Clerk session tokens
  - full account numbers
  - raw data received from Plaid or other providers

  Log only through the structured logger, which removes known sensitive fields.
- Encrypt Plaid access tokens with Fernet before storing them. They never leave the backend.
- Verify each Plaid webhook's `Plaid-Verification` signature before doing any work.
- Verify the Clerk session token on every API request.
- Enforce permissions on the server. Hiding a button in the UI is not access control.
- Every endpoint that returns customer data needs a test proving that a user from another business is denied.
- Use only synthetic data and the Plaid sandbox in code, tests, fixtures, seed scripts, and prompts. Never copy real customer data anywhere.
- Keep secrets only in environment variables: `.env.local` on your machine, and Railway variables in staging and production. Never put secrets in source code.

## Frontend rules

- Use Next.js with the App Router, and TypeScript in strict mode. Avoid `any`. If it's truly unavoidable, add a comment explaining why.
- Pages load data in server components and make changes through server actions.
- Every call to the API goes through the typed client in `lib/api/`. Never hand-write request types.
- Follow `DESIGN.md` and the mockups in `design/mockups/`. Use only the tokens and the components in `components/ui/`. Never add new colors, fonts, or look-alike components. If something is missing, propose it in a `design/<what-changes>` pull request.
- Money arrives as integer cents. Format it only with `lib/format.ts`.
- All interface text comes from `messages/en.json`. Never hard-code text in components. v1 is English only; French comes later, with Quebec.
- Every screen:
  - has loading, empty, and error states
  - works at 375 pixels wide
  - can be used with the keyboard alone
  - has touch targets of at least 44 pixels

## Testing

- **API (pytest):** every spec adds tests for its "Done when" items.
- **Forecasting:** test every strategy on the sample data from spec 18. Include these edge cases:
  - an empty history
  - a single transaction
  - payroll on irregular dates
  - one large one-off payment
- **External services:** unit tests never call Plaid, Clerk, Resend, or PostHog. Use fakes that behave like them. Integration tests may use the Plaid sandbox.
- **Web:** use Vitest and Testing Library for components. Every screen gets a Playwright test that includes an axe check.

## Code Review

- Use the skill `/the-judge` to validate the implementation and the changes after every feature, do not do any integration with git.

## Token Used 

- create a folder `<foldername>` inside `context` and a  `<filename.md>` to track how many tokes is being used per request 
- Context window (~250.000 tokens)
- Smart zone | High quality  0% to 40%
- Attention degrades 40% to 60%
- Low quality 60% to 100%

| Feature  |  Token   | Quality  |
| -------- | -------- | -------- |
| Row 1    | Data A   | Data B   |
| Row 2    | Data C   | Data D   |


## Code style and pull requests

- **Python:** add type hints to every function, use Pydantic models at API boundaries, and use ruff for formatting and linting. Every public function in a `service.py` gets a docstring.
- **TypeScript:** name components in PascalCase, start hook names with `use`, and put one component in each file.
- **Commit messages and pull request titles:** use Conventional Commits, with the module as the scope and the spec number at the end. For example: `feat(forecasting): detect recurring payments (spec 19)`.
- **Pull requests:** target `development`, keep each one to a single spec, and link the spec. The description says what changed, why, and how it was tested. Also include:
  - backtest results, if forecasting changed
  - migration notes, if the database schema changed
  - screenshots, if the UI changed
- **Spec status:** set it to In progress when you start (see "Spec workflow"). In the pull request, set it to Done and tick off its "Done when" items.

## Deployment

- Railway deploys `development` to staging (spec 05) and `main` to production (spec 34). Nothing deploys from spec branches.
- Migrations run automatically before each deploy.
- The `jobs` service (spec 15) runs every hour, and must exit once its work is done.

## Ask before you

- Change files your spec doesn't need, or the shared design files.
- Start a spec whose dependencies aren't Done, or build something no spec covers.
- Build anything from `specs/later/`.
- Change authentication, encryption, or access checks outside a spec that's about them.
- Run migrations against any database other than your own worktree's.
- Guess. If a requirement, an API, or a command is unclear, stop and ask, or leave a comment starting with `TODO(question):` instead of inventing behavior.

## Glossary

- **13-week forecast:** the projected end-of-week cash balance for each of the next 13 weeks.
- **Minimum balance:** a threshold the owner sets. A projected balance below it triggers an alert.
- **Projected low:** the lowest projected balance in the 13-week window.
- **Cash gap:** a period when the projected balance is below the minimum balance.
- **Recurring pattern:** a payment detected as repeating on a regular schedule, such as payroll, rent, or a supplier bill.
- **Bank-only mode:** forecasting from bank data alone, for businesses without accounting software.
- **Included account:** a checking or savings account the owner counts as cash. Cash on hand is the total of the included accounts.
- **Internal transfer:** money moving between two of the business's own accounts. It's never counted as income or spending.
- **Generated file:** a file produced by a tool, such as `contracts/openapi.json`. Regenerate it; never edit it by hand.
- **Worktree:** a separate working folder for one branch, created with `git worktree add`, so that several specs can be built at the same time.
- **Account shortfall (later):** one account is projected to go below $0, even though the business's combined balance is fine.
- **Firm (later):** an accounting or bookkeeping practice that manages several client businesses.

## Nested instructions

create-next-app adds `frontend/AGENTS.md`, with guidance specific to Next.js. It adds to this file rather than replacing it. When a nested file conflicts with this one, follow the nested file inside its own folder, except for the security rules, which always apply. Direct instructions from the person you're working with override both.
