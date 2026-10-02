# Spec 04: Tests and CI

- **Milestone:** 1, set-up
- **Status:** Done
- **Depends on:** 01, 03 (can run alongside 05)

## Goal

Run every check automatically on each pull request.

## Steps

- Set up Vitest and Testing Library by following the Vitest guide in the Next.js docs. Set up Playwright with `npm init playwright@latest`.
- Add three npm scripts: `typecheck` (`tsc --noEmit`), `test` (Vitest), and `test:e2e` (Playwright).
- Create `.github/workflows/ci.yml` with two jobs:
  - **web:** `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build`
  - **api:** install uv with `astral-sh/setup-uv`, then run `uv run ruff check .`, `uv run mypy app`, and `uv run pytest`, with a Postgres service container
- Turn on Dependabot alerts.
- Require CI to pass before merging into `development` or `main`.

**Docs:** [setup-uv](https://github.com/astral-sh/setup-uv), [Playwright](https://playwright.dev/docs/intro)

## Done when

- [x] A pull request shows both jobs passing.
- [x] A deliberate type error makes CI fail.
