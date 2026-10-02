# core

The Headroom API. Setup and checks are in the root [`AGENTS.md`](../../AGENTS.md).

## Deploy

This API runs on Railway as the `api` service. A push to `development` that changes this folder deploys it to staging once CI passes: Railway runs `alembic upgrade head` first, and switches traffic only after `/healthz/ready` answers `200`. The service settings live in [`.railway/railway.ts`](../../.railway/railway.ts).
