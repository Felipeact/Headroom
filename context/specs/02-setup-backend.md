# Spec 02: Backend scaffold

- **Milestone:** 1, set-up
- **Status:** Done
- **Depends on:** nothing. The repository is already set up (can run alongside 01)

## Goal

Create the FastAPI project with uv, using only official packages, plus a single health endpoint.

## Steps

```bash
# From the repository root, on branch development
uv init --app --python 3.12 services/core
cd services/core
uv add "fastapi[standard]" sqlalchemy "psycopg[binary]" alembic pydantic-settings
uv add --dev pytest ruff mypy
```

- Replace the generated `main.py` with `app/main.py`: a FastAPI app with `GET /healthz/live`, which returns `{"status": "ok"}`.
- Add `tests/test_health.py`, with one test that uses FastAPI's `TestClient`.
- Configure ruff and mypy in `pyproject.toml`: ruff's default rules plus import sorting, and mypy in strict mode.

```bash
uv run fastapi dev app/main.py     # http://localhost:8000/docs
uv run pytest
```

**Docs:** [uv projects](https://docs.astral.sh/uv/guides/projects/), [FastAPI](https://fastapi.tiangolo.com/)

## Done when

- [x] `uv run pytest`, `uv run ruff check .`, and `uv run mypy app` all pass.
- [x] `/docs` shows the health endpoint.
