# Spec 03: Local database and migrations

- **Milestone:** 1, set-up
- **Status:** Not started
- **Depends on:** 02

## Goal

Connect the API to PostgreSQL, reading settings from environment variables, with migrations managed by Alembic.

## Steps

- Start the shared local Postgres with `docker compose up -d postgres`.
- Read settings in `app/settings.py` with pydantic-settings, starting with `DATABASE_URL`. Load them from `.env.local`, and add a `.env.example`. Use the `postgresql+psycopg://` URL scheme.
- Create the SQLAlchemy 2 engine, the session, and a `Base` for models in `app/db.py`.
- Run `uv run alembic init migrations`, then point `migrations/env.py` at the settings URL and at `Base.metadata`.
- Add `GET /healthz/ready`, which returns 200 only when the database answers.

**Docs:** [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [SQLAlchemy 2 ORM quickstart](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)

## Done when

- [ ] `uv run alembic upgrade head` runs cleanly on an empty database.
- [ ] `/healthz/ready` returns 200 when Postgres is running and 503 when it's stopped (tested).
- [ ] No database URL or password appears in the code.
