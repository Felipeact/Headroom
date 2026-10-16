# 08 - API errors, logging, and monitoring checks

Profile: light
Plan: `.specs/features/08-api-errors-logging-monitoring/plan.md`

32 checks in 5 slices · 4 one-way doors · 2 open, of which 1 blocks (Sentry DSN: C19, C21) and 1 blocks go-live (push go-ahead: C21, C31)

Every pytest proof runs from `services/core/` with the local Postgres up (`docker compose up -d postgres`). Tests that touch `audit_log` create their own database and run `alembic upgrade head` on it, as `tests/test_migrations.py` already does, because CI runs `pytest` without migrating. Sentry tests use a fake transport and never reach the network. Proofs that need Sentry or Railway are functions in `.specs/features/08-api-errors-logging-monitoring/proofs.sh`, run from the repository root as `bash .specs/features/08-api-errors-logging-monitoring/proofs.sh cN`. They read Sentry only through its documented events API, with `SENTRY_AUTH_TOKEN`, `SENTRY_ORG` and `SENTRY_PROJECT` from the shell environment (never committed), and print IDs and pass/fail, never the DSN or a token.

## Checks

### S1 - Every error is problem details · 3 files · ~8k

**C1** - `GET /does-not-exist?x=1` returns `404`, `Content-Type: application/problem+json`, body exactly `{"type": "about:blank", "title": "Not Found", "status": 404, "detail": "Not Found", "instance": "/does-not-exist"}` (AC 1, door 1)
Proof: `uv run pytest tests/test_problems.py::test_unknown_route_returns_404_problem`

**C2** - `POST /healthz/live` returns `405`, `Content-Type: application/problem+json`, `"status": 405`, `"title": "Method Not Allowed"`, and an `Allow` header containing `GET` (AC 2)
Proof: `uv run pytest tests/test_problems.py::test_wrong_method_returns_405_problem_with_allow`

**C3** - A route raising `HTTPException(status_code=409, detail="Already connected", headers={"X-Test": "1"})` returns `409`, `Content-Type: application/problem+json`, body exactly `{"type": "about:blank", "title": "Conflict", "status": 409, "detail": "Already connected", "instance": <its path>}`, and header `X-Test: 1` (AC 3)
Proof: `uv run pytest tests/test_problems.py::test_http_exception_becomes_problem_with_headers`

**C4** - A request failing validation returns `422`, `Content-Type: application/problem+json`, `"title"` equal to `http.HTTPStatus(422).phrase`, and a non-empty `errors` list whose every item has exactly the keys `loc`, `msg`, `type` (AC 4, door 1)
Proof: `uv run pytest tests/test_problems.py::test_validation_error_returns_422_problem`

**C5** - A request failing validation that carries `access-sandbox-00000000-0000-0000-0000-000000000000` gets a `422` whose raw body text does not contain that value (AC 5)
Proof: `uv run pytest tests/test_problems.py::test_validation_error_does_not_echo_input`

**C6** - A route raising `RuntimeError("boom-secret-detail")` returns `500`, `Content-Type: application/problem+json`, `"detail": "An unexpected error occurred."`, and the raw body contains neither `boom-secret-detail` nor `RuntimeError` (AC 6, door 1)
Proof: `uv run pytest tests/test_problems.py::test_unhandled_exception_returns_generic_500`

**C7** - The same request emits exactly one `error`-level record with `event` `request.unhandled_exception`, the method `GET`, the route path, and an exception traceback containing `RuntimeError` (AC 7)
Proof: `uv run pytest tests/test_problems.py::test_unhandled_exception_logged_once`

**C8** - With the database refusing connections, `GET /healthz/ready` returns `503` with `Content-Type: application/json` (not `application/problem+json`) and body exactly `{"status": "unavailable"}` (AC 8, AD-002)
Proof: `uv run pytest tests/test_health.py::test_ready_503_stays_plain_json`

### S2 - Logs are JSON and never carry secrets · 3 files · ~7k

**C9** - After `configure_logging()`, `structlog.get_logger("t").info("thing.happened", count=3)` writes exactly one stdout line that parses as a JSON object with `"event": "thing.happened"`, `"level": "info"`, `"logger": "t"`, `"count": 3` and a `timestamp` string ending in `Z` (AC 9, door 2)
Proof: `uv run pytest tests/test_log.py::test_line_is_json_with_core_keys`

**C10** - For each of the 11 key fragments `token`, `secret`, `password`, `passwd`, `authorization`, `cookie`, `api_key`, `apikey`, `dsn`, `account_number`, `private_key`, a log call with a key containing it in mixed case (e.g. `Plaid_Access_TOKEN`) renders `"[REDACTED]"` as the value and the original value appears nowhere in the line (AC 10, door 2)
Proof: `uv run pytest tests/test_log.py::test_secret_named_keys_redacted`

**C11** - `payload={"items": [{"access_token": "s3cr3t"}], "meta": {"inner": {"password": "pw-9"}}}` renders a line containing neither `s3cr3t` nor `pw-9` (AC 11)
Proof: `uv run pytest tests/test_log.py::test_nested_secret_keys_redacted`

**C12** - For each of the 4 token forms `access-sandbox-<uuid>`, `access-development-<uuid>`, `access-production-<uuid>`, `Bearer abc.def-123`, placed once in the event message and once in a non-secret string value, the line contains `[REDACTED]` and not the token (AC 12)
Proof: `uv run pytest tests/test_log.py::test_token_patterns_redacted_in_strings`

**C13** - For each stdlib logger `uvicorn.error`, `uvicorn.access`, `sqlalchemy.engine`, a record logged after `configure_logging()` with a Plaid sandbox token in its message is written as one JSON line with `"logger"` equal to that name and without the token (AC 13)
Proof: `uv run pytest tests/test_log.py::test_stdlib_loggers_render_json_with_redaction`

**C14** - `logger.exception(...)` inside `except` for an exception whose message holds a Plaid sandbox token renders an `exception` field that contains `[REDACTED]` and `Traceback`, and not the token (AC 14)
Proof: `uv run pytest tests/test_log.py::test_exception_traceback_redacted`

**C15** - `uv run fastapi run app/main.py` on a free port, after one `GET /does-not-exist`, has written at least one log line, and every line it wrote that starts with `{` is valid JSON; the access record for `/does-not-exist` is one of them (AC 13 in the real server assembly)
Proof: `uv run pytest tests/test_log.py::test_real_server_writes_json_access_log`

### S3 - Crashes reach Sentry · 3 files + proofs · ~8k

**C16** - With Sentry initialised through the app's lifespan (`with TestClient(app)`) and a fake transport, a route raising `RuntimeError` makes the transport receive exactly one error event whose exception type is `RuntimeError` (AC 15, door 3)
Proof: `uv run pytest tests/test_sentry.py::test_unhandled_exception_sends_one_event`

**C17** - Same setup, a route raising `HTTPException(status_code=404)` and one raising `HTTPException(status_code=409)` make the transport receive zero events (AC 16)
Proof: `uv run pytest tests/test_sentry.py::test_4xx_http_exception_sends_no_event`

**C18** - Same setup, an unhandled exception on a request sent with `Authorization: Bearer abc.def-123`, while the scope carries extra `access_token="access-sandbox-<uuid>"`, delivers an event that contains neither `abc.def-123` nor the token anywhere in its serialized JSON, and has no `user.ip_address` (AC 17, door 3)
Proof: `uv run pytest tests/test_sentry.py::test_event_redacted_before_send`

**C19** - With `SENTRY_DSN` unset, entering the app's lifespan leaves `sentry_sdk.get_client().is_active()` false and `GET /healthz/live` returns `200` (AC 18)
Proof: `uv run pytest tests/test_sentry.py::test_no_dsn_no_client`

**C20** - With `SENTRY_DSN` unset, `uv run python -m app.sentry_check` exits `1`, stderr contains `SENTRY_DSN is not set`, and stdout is empty (AC 20)
Proof: `uv run pytest tests/test_sentry.py::test_sentry_check_without_dsn_exits_1`

**C21** - With your DSN in `services/core/.env.local`, `uv run python -m app.sentry_check` exits `0` and prints a 32-hex event ID, and Sentry's events API returns that event within 60 seconds with tag `environment` = `local` (AC 19, spec Done-when 3)
Proof: `bash .specs/features/08-api-errors-logging-monitoring/proofs.sh c21`

**C22** - `railway ssh --service api --environment staging` running `python -m app.sentry_check` exits `0` with an event ID, and Sentry's events API returns that event within 60 seconds with tag `environment` = `staging` (AC 21)
Proof: `bash .specs/features/08-api-errors-logging-monitoring/proofs.sh c22`

### S4 - Later specs can record audit entries · 4 files · ~9k

**C23** - `audit.record(session, action="bank_connection.created", business_id=<uuid4>, actor_user_id="user_test", target_type="bank_connection", target_id="42", details={"institution": "Sandbox Bank"})` followed by `session.commit()` leaves exactly one new `audit_log` row with those 7 values and `occurred_at` within 5 seconds of UTC now (AC 22, door 4)
Proof: `uv run pytest tests/test_audit.py::test_record_commits_with_caller`

**C24** - `audit.record(...)` followed by `session.rollback()` leaves the `audit_log` row count unchanged (AC 23, door 4)
Proof: `uv run pytest tests/test_audit.py::test_record_rolls_back_with_caller`

**C25** - `UPDATE audit_log SET action = 'x.y' WHERE id = <id>` raises a database error, and a fresh connection reads the row unchanged (AC 24, door 4)
Proof: `uv run pytest tests/test_audit.py::test_update_is_rejected`

**C26** - `DELETE FROM audit_log WHERE id = <id>` raises a database error, and the row count is unchanged (AC 25, door 4)
Proof: `uv run pytest tests/test_audit.py::test_delete_is_rejected`

**C27** - `TRUNCATE audit_log` raises a database error, and the row count is unchanged (AC 26, door 4)
Proof: `uv run pytest tests/test_audit.py::test_truncate_is_rejected`

**C28** - For each of `"BankConnected"`, `"bank_connection"`, `"bank-connection.created"`, `"bank_connection.created.extra"`, `".created"`, `audit.record` raises `ValueError` and `session.new` is empty afterwards (AC 27)
Proof: `uv run pytest tests/test_audit.py::test_invalid_action_raises_value_error`

**C29** - A direct SQL `INSERT INTO audit_log (action) VALUES ('BankConnected')` raises an `IntegrityError` naming the check constraint (AC 28, door 4)
Proof: `uv run pytest tests/test_audit.py::test_check_constraint_rejects_invalid_action`

**C30** - `details={"plaid": {"access_token": "access-sandbox-<uuid>"}, "items": [{"password": "pw"}], "institution": "Sandbox Bank"}` is stored as `{"plaid": {"access_token": "[REDACTED]"}, "items": [{"password": "[REDACTED]"}], "institution": "Sandbox Bank"}` (AC 29)
Proof: `uv run pytest tests/test_audit.py::test_details_redacted`

**C31** - On a newly created database, `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` and `alembic check` each exit `0`, and after the downgrade `audit_log` and the function `audit_log_append_only` no longer exist (AC 30)
Proof: `uv run pytest tests/test_migrations.py::test_audit_log_upgrade_downgrade_and_check`

### S5 - The checks stay green · ~1k

**C32** - In `services/core/`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy app` and `uv run pytest` each exit `0`; and the latest `CI` run on `development` for the pushed commit has job `api` with conclusion `success` (AC 31)
Proof: `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest`
Proof: `bash .specs/features/08-api-errors-logging-monitoring/proofs.sh c32`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| error sources mapped to problem details (5) | unknown route C1 · wrong method C2 · `HTTPException` C3 · validation C4 · unhandled exception C6 | - |
| problem body members, door 1 (6) | `type` C1 · `title` C1, C2, C3, C4 · `status` C1, C2, C3 · `detail` C1, C3, C6 · `instance` without query string C1 · `errors` C4 | - |
| things a problem must not leak (3) | submitted input C5 · exception text C6 · exception class C6 | - |
| `HTTPException` headers kept (2) | `Allow` C2 · custom header C3 | - |
| secret key fragments, door 2 (11) | C10, table-driven over all 11 | - |
| redaction positions (4) | top-level key C10 · nested dict/list C11 · string value and message C12 · traceback C14 | - |
| token value patterns (4) | C12, table-driven over all 4 | - |
| stdlib loggers routed (3) | C13, table-driven over all 3 | - |
| startup config: logging configured (2 assemblies) | real server `fastapi run` C15 · test harness importing `app.main` C7 | - |
| startup config: Sentry initialised (2 places) | app lifespan C16 (TestClient runs the same lifespan as uvicorn) · `app.sentry_check` C20, C21 | - |
| Sentry delivery outcomes (3) | 5xx sent C16 · 4xx not sent C17 · DSN unset, nothing sent C19, C20 | - |
| Sentry environments (2) | `local` C21 · `staging` C22 | - |
| `sentry_check` exit codes (2) | `0` C21 · `1` C20 | - |
| `audit_log` write paths (2) | through `audit.record` C23 · direct SQL C29 | - |
| `audit_log` forbidden operations, door 4 (3) | `UPDATE` C25 · `DELETE` C26 · `TRUNCATE` C27 | - |
| `audit.record` transaction outcomes (2) | caller commits C23 · caller rolls back C24 | - |
| `audit.record` values stored (7) | `action` C23 · `business_id` C23 · `actor_user_id` C23 · `target_type` C23 · `target_id` C23 · `details` C23 · `occurred_at` C23 | - |
| invalid `action` shapes (5) | C28, table-driven over all 5 | - |
| migration directions (3) | upgrade C31 · downgrade C31 · models match migration (`alembic check`) C31 | - |

- Claims naming a status code or response shape: C1-C8 - each proof sends a real request through `TestClient`, crossing the HTTP boundary
- Claims about Sentry delivery (C16-C18) assert on what the transport receives, the last point before the network; C21 and C22 assert on what Sentry stored
- No other check claims more than the single case its proof exercises

## Swept

- validation: C4, C5 (request validation becomes `422` without echoing input); C28, C29 (`action` shape)
- failure modes: C6, C7 (unhandled exception: generic `500` plus one log record); C24 (audit entry rolls back with its caller)
- idempotency: n/a - nothing here is retried or deduplicated; each `audit.record` call is one entry by design, and its caller's transaction decides whether it persists (C23, C24)
- authorization: n/a - no route is added; authentication arrives with spec 10. The `audit_log` trigger applies to every database role, including the owner (C25-C27)
- concurrency: n/a - no shared mutable state; `audit_log` is insert-only with an identity key, so concurrent inserts cannot conflict
- data lifecycle: C25-C27 (rows cannot be changed or removed); retention and deletion requests are out of scope in the plan
- dependency failure: C19, C20 (Sentry absent: app runs, check command fails clearly); C8 (database down keeps the probe body)
- state transitions: n/a - no entity has states in this spec
- observability: C9-C15 (structured, redacted logs), C16-C18 (error reporting), C21, C22 (proved end to end in Sentry)

## Handoff

- Files read or written: `app/main.py` 1.2 KB, `app/settings.py` 0.6 KB, `app/db.py` 1.0 KB, `migrations/env.py` 2.4 KB, `.railway/railway.ts` 2.3 KB, `.env.example`, `pyproject.toml`, existing tests 7 KB, plus about 9 new files of 2-5 KB each (~30 KB). About 45 KB in all, / 4 = ~11k tokens of file content; with test runs, docs lookups for structlog and sentry-sdk, and rework, an estimated ~45k. `uv.lock` is regenerated by `uv add`, never read
- S1 = 8k, S2 enters `app/log.py` at 15k, S3 enters Sentry at 23k, S4 enters the audit log and migration at 32k, S5 at 33k; ~45k with overhead, under the 150k budget - one builder

- **Boundary:** C1-C20 and C23-C31 closed at `23f9ed6` (pytest 65 passed; ruff, mypy green). Open: C21 and C22 (need the Sentry DSN plus `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` in the shell), C22 and C32 (need the go-ahead to push `development`, set `SENTRY_DSN` on Railway and apply `SENTRY_ENVIRONMENT=staging` from `.railway/railway.ts`)
- **Settled mid-build:** plan doors 5 (`instance` redacted, found by C5) and 6 (logging configured in the lifespan, found by C15); Sentry ignores the `app.problems` logger so a 500 is one event, not two (found by C16); the lifespan rebuilds the middleware stack so a raised 5xx `HTTPException` reaches Sentry (extra test `test_5xx_http_exception_sends_one_event`)
- **Abandoned:** a shared `json_logs` fixture that configured logging during fixture setup - pytest swaps `sys.stdout` between setup and the test call, so the handler wrote to a closed stream; each log test now calls `configure_logging()` in its own body
