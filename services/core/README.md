# core

The Headroom API and the hourly jobs. It's a FastAPI application backed by PostgreSQL. It syncs bank data from Plaid, forecasts cash 13 weeks ahead, detects cash gaps, and sends email.

The commands and rules in the root [AGENTS.md](../../AGENTS.md) are the source of truth. This file is a guide to this folder.

## Setup

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), and the local database from the repository root (`docker compose up -d postgres`).

```bash
cp .env.example .env.local     # use sandbox and test keys only
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py # http://localhost:8000/docs
```

### Environment variables

`.env.example` lists every variable with a comment. The main groups are:

| Variables | Used for |
|---|---|
| `DATABASE_URL` | PostgreSQL connection |
| `CLERK_JWT_KEY`, `CLERK_AUTHORIZED_PARTIES`, `CLERK_SECRET_KEY` | Verifying sessions, and reading a user's contact details |
| `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV`, `PLAID_WEBHOOK_URL` | Bank connections (sandbox locally) |
| `TOKEN_ENCRYPTION_KEYS` | Fernet keys that encrypt Plaid access tokens |
| `FORECAST_STRATEGY` | Which forecasting strategy runs |
| `EMAIL_SENDER`, `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_MAILING_ADDRESS` | Sending email |
| `WEB_URL`, `API_PUBLIC_URL` | Links in emails and webhooks |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | Error monitoring (optional locally) |

Never commit `.env.local`, and never put production credentials in it.

## Layout

```text
app/
├── main.py             # The app and its routers; every route is under /v1
├── settings.py         # Settings read from the environment
├── db.py               # Database engine and sessions
├── auth.py             # Clerk session verification
├── events.py           # The in-process event bus
├── problems.py         # RFC 9457 problem details for errors
├── log.py              # The structured logger, which removes sensitive fields
├── dashboard.py        # The dashboard endpoint, built from the modules' services
├── export_openapi.py   # Writes contracts/openapi.json
├── fixtures/           # Synthetic sample data (harbor_street)
├── jobs/               # The hourly job runner and its jobs
└── modules/
    ├── accounts/       # Users, businesses, and members
    ├── bank_sync/      # Plaid connections, accounts, transactions, webhooks, labels
    ├── forecasting/    # Recurring and expected payments, strategies, the engine, backtest
    ├── alerts/         # Cash gaps and suggested fixes
    └── notifications/  # Email templates, delivery, preferences, unsubscribe
migrations/             # Alembic
tests/                  # pytest
```

### Modules

Each module has the same files: `api.py` (HTTP only), `service.py` (its public functions), `models.py` (its tables), `repository.py` (access to its own tables), and `events.py`.

- A module may use another module only through that module's `service.py` and `events.py`.
- A module never queries or joins another module's tables.
- Modules notify each other through events: `transactions.synced`, `forecast_inputs.changed`, `forecast.updated`, `alert.created`, `alert.updated`, and `alert.resolved`.
- Every event handler and job gives the same result if it runs twice.

## API

All routes are under `/v1`, and errors use `application/problem+json`. The interactive docs at `/docs` list every route. The main groups are:

| Area | Routes |
|---|---|
| Accounts | `/me`, `/businesses`, `/businesses/{id}` |
| Bank | `/businesses/{id}/bank/link-token`, `/bank/connections`, `/bank/accounts/{id}`, `/bank/transactions` |
| Forecast | `/businesses/{id}/forecast`, `/forecast/status`, `/minimum-balance`, `/recurring-patterns`, `/expected-payments`, `/upcoming` |
| Alerts | `/businesses/{id}/alerts`, `/alerts/{id}`, `/alerts/{id}/dismiss` |
| Dashboard | `/businesses/{id}/dashboard` |
| Email | `/me/email-preferences`, `/unsubscribe/{token}` |
| Webhooks | `/webhooks/plaid` (signature-verified) |
| Health | `/healthz/live`, `/healthz/ready` (outside `/v1`) |

Every request needs a valid Clerk session, except webhooks, unsubscribe links, and health checks. Members see only their own businesses.

### After you change an endpoint

Regenerate the contract and the web app's types, and commit both files:

```bash
uv run python -m app.export_openapi   # from services/core
npm run api:types                     # from frontend
```

CI fails if either file is out of date.

## Database

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "short description"
```

Always read and correct a generated migration before you commit it. Run migrations only against your local database.

## Conventions

- **Money:** integer cents (`amount_cents`) plus an ISO 4217 currency code. Never use floats for money.
- **Sign:** positive means money in, negative means money out. Plaid's sign is flipped once, in `bank_sync`.
- **Time:** timestamps are stored in UTC. Bank transaction dates are plain dates. Forecast weeks start on Monday in the business's time zone.
- **Tenancy:** every row of customer data has a `business_id`, and every query filters on it.
- **Cash:** only included checking and savings accounts count. Transfers between the business's own accounts are never income or spending.

## Forecasting

- To add a forecasting method, write a new `ForecastStrategy` class in `modules/forecasting/strategies.py` and register it. Don't edit the engine.
- `FORECAST_STRATEGY` selects the strategy that runs.
- Every strategy returns exactly 13 weeks, even when the history is empty or short.

To measure accuracy, run the backtest. It replays the sample data and reports the average error at 1, 4, and 13 weeks for each strategy:

```bash
uv run python -m app.modules.forecasting.backtest
```

If you change the forecasting logic, put the accuracy before and after your change in the commit message.

## Jobs

```bash
uv run python -m app.jobs.run_due
```

This runs every job that is due, then exits. Railway's `jobs` service starts it every hour. The jobs are:

- `nightly_bank_sync`: syncs each business's bank data overnight
- `forecast_accuracy`: scores past forecasts against what actually happened
- `email_retries`: retries emails that failed to send

## Sample data

`harbor_street` is a synthetic business with realistic payroll, rent, supplier bills, and uneven customer payments. Load it into your local database with:

```bash
uv run python -m app.fixtures.load harbor_street
```

## Tests and checks

```bash
uv run ruff format --check . && uv run ruff check .
uv run mypy app
uv run pytest
```

- Unit tests never call Plaid, Clerk, or Resend. They use fakes.
- Tests marked `plaid_sandbox` call the real Plaid sandbox and are skipped by default. They need sandbox keys in `.env.local`.
- Every endpoint that returns customer data has a test proving that a user from another business is denied.

## Deploy

This API runs on Railway as the `api` service. A push to `development` that changes this folder deploys it to staging once CI passes: Railway runs `alembic upgrade head` first, and switches traffic only after `/healthz/ready` answers `200`. The service settings live in [`.railway/railway.ts`](../../.railway/railway.ts).
