# Spec 05: Staging on Railway

- **Milestone:** 1, set-up
- **Status:** Not started
- **Depends on:** 01, 03 (can run alongside 04)

## Goal

Deploy `development` to a staging environment automatically.

## Steps

- Create a Railway project in the US East region, with a `staging` environment that deploys from `development`. The `production` environment comes in spec 34.
- Add three services:
  - **`postgres`:** Railway PostgreSQL.
  - **`api`:** root directory `services/core`, started with `uv run fastapi run app/main.py --port $PORT`. Run `uv run alembic upgrade head` before each deploy, and set the health check to `/healthz/ready`.
  - **`web`:** root directory `frontend`.
- Let Railway's builder detect each app. If it can't build the API, add a minimal Dockerfile based on uv's Docker guide.
- Set watch paths, so each service redeploys only when its own folder changes.
- Keep all variables in Railway, never in the repository.

**Docs:** [Railway monorepos](https://docs.railway.com/guides/monorepo), [uv with Docker](https://docs.astral.sh/uv/guides/integration/docker/)

## Done when

- [ ] Merging into `development` deploys both apps to staging.
- [ ] Staging's `/healthz/ready` returns 200, and the web app loads.
