# 08 - API errors, logging, and monitoring verification

**Verdict**: PASS
**Profile**: light
**Diff range**: ec63c5f..1fa01d5181ea004c249661c580baa083417ce271
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

All 32 checks pass, each with located evidence. Where each one was proven:

- **Locally at HEAD (one pytest run):** C1-C20, apart from the database-backed tests. The run was `uv run pytest -v tests/test_problems.py tests/test_log.py tests/test_sentry.py tests/test_health.py::test_ready_503_stays_plain_json` and passed 36 of 36, with every named test listed `PASSED`. `ruff format --check`, `ruff check` and `mypy app` also exit 0 locally.
- **CI at HEAD:** C23-C31 need Postgres, and this machine has none (port 5432 closed, no Docker). They are proven from the CI log of run `37056211324` (workflow `CI`, job `api`, head SHA `1fa01d5`, conclusion `success`):
  - The job runs `uv run pytest` non-verbose against a Postgres service.
  - The log shows `tests/test_audit.py ............` (12 dots, no `F`, `E` or `s`) and `tests/test_migrations.py ....` (4 dots), then `65 passed`.
  - `pytest --collect-only` at HEAD maps those positions to the 12 `test_audit.py` IDs and the 4 `test_migrations.py` IDs, including every proof named in C23-C31.
  - So each named DB test ran and passed at HEAD, but only by position: the log does not print test names.
- **External:**
  - **C21:** re-run live; it printed `PASS c21` with event `b6c0128c9f60470db64c87b62f380d9d` (`environment=local`).
  - **C32:** `proofs.sh c32` printed `PASS c32` after HEAD's CI run finished.
  - **C22:** its command was **not re-run** (see C22 below).

## Binding sources

Not applicable under profile `light`. The plan marks no design source as binding. Its sources are the spec, `AGENTS.md` and the Sentry FastAPI docs, which the checks restate as values.

## Checks

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | unknown route -> 404 problem, exact body, `instance` without query | local pytest batch: `test_problems.py::test_unknown_route_returns_404_problem PASSED` | `services/core/tests/test_problems.py:45` - `assert response.status_code == 404`; `:46` content-type `== PROBLEM_JSON`; `:47` - `assert response.json() == {"type": "about:blank", "title": "Not Found", "status": 404, "detail": "Not Found", "instance": "/does-not-exist"}` (request `/does-not-exist?x=1` at `:43`) | PASS |
| C2 | `POST /healthz/live` -> 405 problem with `Allow: GET` | local: `test_wrong_method_returns_405_problem_with_allow PASSED` | `services/core/tests/test_problems.py:62` - `assert body["status"] == 405`; `:63` - `assert body["title"] == "Method Not Allowed"`; `:64` - `assert "GET" in response.headers["allow"]`; `:60` content-type | PASS |
| C3 | `HTTPException(409, headers)` -> exact problem body + `X-Test` header | local: `test_http_exception_becomes_problem_with_headers PASSED` | `services/core/tests/test_problems.py:73` - `assert response.headers["x-test"] == "1"`; `:74` - `assert response.json() == {... "title": "Conflict", "status": 409, "detail": "Already connected", "instance": "/test/conflict"}` | PASS |
| C4 | validation -> 422 problem, title phrase, errors with exactly `loc,msg,type` | local: `test_validation_error_returns_422_problem PASSED` | `services/core/tests/test_problems.py:91` - `assert body["title"] == HTTPStatus(422).phrase`; `:92` - `assert body["errors"]`; `:94` - `assert set(error) == {"loc", "msg", "type"}` | PASS |
| C5 | 422 never echoes the sandbox token | local: `test_validation_error_does_not_echo_input PASSED` | `services/core/tests/test_problems.py:102` - `assert SANDBOX_TOKEN not in response.text` (`SANDBOX_TOKEN` = `access-sandbox-00000000-...` at `:13`) | PASS |
| C6 | unhandled exception -> generic 500 problem, no message/class leak | local: `test_unhandled_exception_returns_generic_500 PASSED` | `services/core/tests/test_problems.py:111` - `assert response.json()["detail"] == "An unexpected error occurred."`; `:112` - `"boom-secret-detail" not in response.text`; `:113` - `"RuntimeError" not in response.text` | PASS |
| C7 | exactly one error record `request.unhandled_exception` with method, path, traceback | local: `test_unhandled_exception_logged_once PASSED` | `services/core/tests/test_problems.py:123` - `assert len(records) == 1`; `:125` level `== "error"`; `:126` method `== "GET"`; `:127` path `== "/test/boom"`; `:128` - `assert "RuntimeError" in str(record["exception"])` | PASS |
| C8 | DB refusing -> `/healthz/ready` 503 plain JSON `{"status": "unavailable"}` | local: `test_health.py::test_ready_503_stays_plain_json PASSED` (fixture points the engine at a closed port); also passed in CI | `services/core/tests/test_health.py:90` - `assert response.status_code == 503`; `:91` - `== "application/json"`; `:92` - `assert response.json() == {"status": "unavailable"}` | PASS |
| C9 | one JSON line with event/level/logger/count/timestamp `Z` | local: `test_log.py::test_line_is_json_with_core_keys PASSED` | `services/core/tests/test_log.py:47` - `assert len(lines) == 1`; `:49-52` event/level/logger/count; `:54` - `assert line["timestamp"].endswith("Z")` | PASS |
| C10 | 11 secret key fragments in mixed case -> `[REDACTED]`, value absent | local: 11 parametrized `test_secret_named_keys_redacted[...] PASSED` (one per fragment, `SECRET_KEYS` at `:20-32`) | `services/core/tests/test_log.py:65` - `assert "hunter2-value" not in out`; `:66` - `assert json.loads(out)[key] == "[REDACTED]"` | PASS |
| C11 | nested dict/list secrets redacted | local: `test_nested_secret_keys_redacted PASSED` | `services/core/tests/test_log.py:78` - `assert "s3cr3t" not in out`; `:79` - `assert "pw-9" not in out` | PASS |
| C12 | 4 token forms in message and string value -> `[REDACTED]` | local: 4 parametrized `test_token_patterns_redacted_in_strings[...] PASSED` | `services/core/tests/test_log.py:90` - `assert token not in out`; `:92` - `"[REDACTED]" in line["event"]`; `:93` - `"[REDACTED]" in line["note"]` | PASS |
| C13 | `uvicorn.error`, `uvicorn.access`, `sqlalchemy.engine` -> one JSON line, logger name, token removed | local: 3 parametrized `test_stdlib_loggers_render_json_with_redaction[...] PASSED` | `services/core/tests/test_log.py:108` - `assert len(lines) == 1`; `:110` - `assert line["logger"] == name`; `:111` - `assert token not in out` | PASS |
| C14 | traceback field redacted, contains `Traceback` | local: `test_exception_traceback_redacted PASSED` | `services/core/tests/test_log.py:123` - `assert token not in out`; `:125` - `"Traceback" in exception`; `:126` - `"[REDACTED]" in exception` | PASS |
| C15 | real `fastapi run` writes valid JSON lines incl. access record | local: `test_real_server_writes_json_access_log PASSED` (subprocess `python -m fastapi run app/main.py`) | `services/core/tests/test_log.py:165` - `assert json_lines, output`; `:166` - `json.loads` over every `{` line; `:167-168` - `any(r.get("logger") == "uvicorn.access" and "/does-not-exist" in str(r["event"]) ...)` | PASS |
| C16 | lifespan-initialised Sentry: one `RuntimeError` event | local: `test_sentry.py::test_unhandled_exception_sends_one_event PASSED` | `services/core/tests/test_sentry.py:109` - `assert len(sentry_events) == 1`; `:110` - `assert exception_types(sentry_events) == ["RuntimeError"]` | PASS |
| C17 | 404 and 409 `HTTPException` -> zero events | local: `test_4xx_http_exception_sends_no_event PASSED` | `services/core/tests/test_sentry.py:117-118` statuses 404/409; `:121` - `assert sentry_events == []` | PASS |
| C18 | event carries neither bearer value nor token; no `user.ip_address` | local: `test_event_redacted_before_send PASSED` | `services/core/tests/test_sentry.py:145` - `assert "abc.def-123" not in serialized`; `:146` - `assert SANDBOX_TOKEN not in serialized`; `:147` - `assert "ip_address" not in sentry_events[0].get("user", {})` | PASS |
| C19 | DSN unset -> no active client, `/healthz/live` 200 | local: `test_no_dsn_no_client PASSED` | `services/core/tests/test_sentry.py:161` - `assert active is False`; `:162` - `assert response.status_code == 200` | PASS |
| C20 | `sentry_check` without DSN -> exit 1, stderr message, empty stdout | local: `test_sentry_check_without_dsn_exits_1 PASSED` | `services/core/tests/test_sentry.py:176` - `assert result.returncode == 1`; `:177` - `"SENTRY_DSN is not set" in result.stderr`; `:178` - `assert result.stdout == ""` | PASS |
| C21 | local `sentry_check` -> exit 0, 32-hex ID, Sentry stores it with `environment=local` | `bash .specs/features/08-api-errors-logging-monitoring/proofs.sh c21` exit 0 at HEAD: `event b6c0128c9f60470db64c87b62f380d9d` / `PASS c21` | `.specs/features/08-api-errors-logging-monitoring/proofs.sh:51` - `is_event_id "$id"` (regex `^[0-9a-f]{32}$` at `:42`); `:54` - `[ "$environment" = "local" ]` on the tag read from Sentry's events API (`:30-34`) | PASS |
| C22 | staging `sentry_check` -> exit 0, Sentry stores event with `environment=staging` | **Not re-run.** `railway ssh` needs an SSH key, which the user removed after the author's run, so this verifier did not run it. Instead I made an independent read-only GET of the author's event `4f6b45f52221471e9b57ea4412592252` from Sentry's events API (HTTP 200). It returned tag `environment=staging`, title `SentryCheckError: Headroom API Sentry check 2026-10-02T19:44:50...`, and `server_name` `2d3ac0e9e8f0` (a container host, not this machine). The event was created after `f68233f` deployed the staging variables. Between `f68233f` and HEAD, nothing under `services/` or `.railway/` changed. | `.railway/railway.ts:34` - `SENTRY_ENVIRONMENT: "staging",`; `.railway/railway.ts:33` - `SENTRY_DSN: preserve(),`; `services/core/app/sentry_check.py:83-87` - prints the ID and `return 0` only when `capture_exception` returned an ID; proof assertion `.specs/features/08-api-errors-logging-monitoring/proofs.sh:66` - `[ "$environment" = "staging" ]` | PASS |
| C23 | `audit.record` + commit -> one row with 7 values, `occurred_at` within 5s | CI run `37056211324` (HEAD) `tests/test_audit.py` 12/12 passed; collected ID `test_record_commits_with_caller` | `services/core/tests/test_audit.py:67` - `assert count(engine) == before + 1`; `:72-77` action/business_id/actor_user_id/target_type/target_id/details; `:78` - `assert abs(row.occurred_at - datetime.now(UTC)) < timedelta(seconds=5)` | PASS |
| C24 | rollback leaves count unchanged | CI HEAD, `test_record_rolls_back_with_caller` | `services/core/tests/test_audit.py:89` - `assert count(engine) == before` | PASS |
| C25 | `UPDATE` raises, row unchanged | CI HEAD, `test_update_is_rejected` | `services/core/tests/test_audit.py:95` - `pytest.raises(DBAPIError)`; `:104` - `assert action == "thing.created"` (fresh connection at `:100`) | PASS |
| C26 | `DELETE` raises, count unchanged | CI HEAD, `test_delete_is_rejected` | `services/core/tests/test_audit.py:111` - `pytest.raises(DBAPIError)`; `:114` - `assert count(engine) == before` | PASS |
| C27 | `TRUNCATE` raises, count unchanged | CI HEAD, `test_truncate_is_rejected` | `services/core/tests/test_audit.py:121` - `pytest.raises(DBAPIError)`; `:124` - `assert count(engine) == before` | PASS |
| C28 | 5 invalid actions -> `ValueError`, `session.new` empty | CI HEAD, 5 parametrized `test_invalid_action_raises_value_error[...]` (collected IDs match all 5) | `services/core/tests/test_audit.py:139` - `with pytest.raises(ValueError):`; `:141` - `assert not session.new` | PASS |
| C29 | direct SQL invalid action -> `IntegrityError` naming the check | CI HEAD, `test_check_constraint_rejects_invalid_action` | `services/core/tests/test_audit.py:145` - `pytest.raises(IntegrityError)`; `:148` - `assert "ck_audit_log_action_format" in str(raised.value)` | PASS |
| C30 | nested secret `details` stored redacted | CI HEAD, `test_details_redacted` | `services/core/tests/test_audit.py:170` - `assert stored == {"plaid": {"access_token": "[REDACTED]"}, "items": [{"password": "[REDACTED]"}], "institution": "Sandbox Bank"}` | PASS |
| C31 | upgrade/downgrade/upgrade/check exit 0; table and function gone after downgrade | CI HEAD `tests/test_migrations.py` 4/4 passed; collected ID `test_audit_log_upgrade_downgrade_and_check` | `services/core/tests/test_migrations.py:87` - `assert result.returncode == 0, result.stderr` (upgrade, downgrade); `:98` - `assert "audit_log" not in tables`; `:99` - `assert function is None`; `:103` - returncode 0 for upgrade and `check` | PASS |
| C32 | ruff format, ruff check, mypy, pytest exit 0; CI job `api` success on pushed HEAD | Local: `ruff format --check` exit 0 (`20 files already formatted`), `ruff check` exit 0, `mypy app` exit 0 (`no issues found in 9 source files`). The full pytest suite needs Postgres, so it was taken from CI: run `37056211324` on `1fa01d5` shows `65 passed`. `PATH=<gh shim>:$PATH bash .../proofs.sh c32` exit 0 printed `PASS c32`. | `.specs/features/08-api-errors-logging-monitoring/proofs.sh:73` - HEAD equals `origin/development`; `:76` - `[ "$conclusion" = "success" ]` for job `api` of the HEAD run | PASS |

## Level and sampling

- **C1-C8 (status codes and response shapes):** every proof goes through `TestClient` across the HTTP boundary. No level gap.
- **C15:** proven in the real `fastapi run` assembly, which is the other startup assembly. Logging is configured in the lifespan at `services/core/app/main.py:23`.
- **C16-C18:** go through the app's own lifespan `init_sentry`, with the fake transport injected by patching `sentry_sdk.init` (`services/core/tests/test_sentry.py:82`). This sits at the right level: the last point before the network.
- **C10, C12, C13, C28:** each is parametrized over every member of its set (11, 4, 3 and 5), so there is no sampling gap.
- **C19, C20 and C15 ("DSN unset"):** the tests set `SENTRY_DSN=""` rather than removing the variable. That is the only way to override a DSN in `.env.local`, which pydantic-settings reads. `init_sentry` treats both cases the same (`services/core/app/monitoring.py:18` - `if not settings.sentry_dsn`). This is a minor precision note, not a gap.
- **C23-C31:** the CI evidence is per file and per position, because pytest runs non-verbose. It is not a log of test names. Collection at HEAD maps every position to a named test, and no test in those files was skipped or failed.

## C22 judgment

The C22 command was not re-run, because doing so would need an SSH key the user removed. The stored-event evidence still settles what the claim is about:

- **What the evidence covers:**
  - An event exists in Sentry whose exception and message come from `app.sentry_check`.
  - Its `environment` tag is `staging`.
  - It came from a container host.
  - It was ingested while the deployed code matched HEAD.
- **What it does not cover:**
  - The command's exit code on staging, which nobody independently observed. It follows from the code instead: `sentry_check.py` returns 0 exactly when an event ID exists.
  - Whether the command reproduces at HEAD today.

I judge the stored event enough for PASS, but this is the one check proven by evidence rather than by a re-run.

## Swept existing - re-read

- **validation (C4, C5; C28, C29):**
  - `services/core/app/problems.py:78-80` builds the field errors from `loc`, `msg` and `type` only.
  - `services/core/app/problems.py:46` redacts tokens in `instance`.
  - `services/core/app/audit.py:61` checks `ACTION_PATTERN.fullmatch`.
  - The migration's check constraint is at `services/core/migrations/versions/99b26f739028_create_audit_log.py:54-57`.
  - Present.
- **failure modes (C6, C7, C24):**
  - `services/core/app/problems.py:14` holds `UNEXPECTED_ERROR` and `:95` logs `request.unhandled_exception`.
  - `services/core/app/audit.py:75` calls `session.flush()` and never commits.
  - Present.
- **data lifecycle (C25-C27):** the triggers are at `services/core/migrations/versions/99b26f739028_create_audit_log.py:62-69` (`BEFORE UPDATE OR DELETE ... FOR EACH ROW`, and `BEFORE TRUNCATE ... FOR EACH STATEMENT`). They apply to every role, owners included, as the authorization row claims. Present.
- **dependency failure (C19, C20; C8):**
  - `services/core/app/monitoring.py:18` returns `False` without a DSN.
  - `services/core/app/sentry_check.py:73-75` exits 1 with the message.
  - `services/core/app/main.py:66-68` returns the 503 body directly.
  - Present.
- **observability (C9-C18, C21, C22):**
  - `services/core/app/log.py:11` holds `SECRET_KEY_FRAGMENTS` and `:28` the `Bearer` pattern.
  - `services/core/app/monitoring.py:46-53` calls `init` with `send_default_pii=False` and `before_send=_before_send`.
  - Present.
- **idempotency, authorization (route level), concurrency, state transitions:** `n/a` is policy the user approved, so there is nothing to re-read.

## Gate

- **Local, at HEAD `1fa01d5`:** `uv run pytest -v tests/test_problems.py tests/test_log.py tests/test_sentry.py tests/test_health.py::test_ready_503_stays_plain_json` - 36 passed, 0 failed. `ruff format --check`, `ruff check` and `mypy app` all exit 0.
- **CI, at HEAD `1fa01d5`:** run `37056211324`, job `api` success - `65 passed`, 0 failed.

## Ranked gaps

None that fail the verdict. Notes:

1. **C22 was not re-run at verification time.** The SSH key it needs was removed. It rests on Sentry's stored event `4f6b45f52221471e9b57ea4412592252` with `environment=staging`, which I read independently.
2. **C23-C31 rest on CI's non-verbose output.** The evidence is per position and mapped to names by `--collect-only`. A `-v` or `-rA` flag on the CI pytest step would make each named DB test appear in the log.
