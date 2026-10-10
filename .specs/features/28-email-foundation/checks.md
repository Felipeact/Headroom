# 28 - Email foundation checks

Profile: light
Plan: `.specs/features/28-email-foundation/plan.md`

47 checks in 4 slices · 6 one-way doors · 2 open, of which 0 block (2 block go-live)

`uv run` proofs run from `services/core`, `npx` proofs from `frontend`. API tests use the real local Postgres from `tests/conftest.py`, a `FakeEmailSender` that records every send and can be told to raise a given error on the next N sends, and a `FakeClerkUsers` that returns a set primary email and first name per Clerk user id (no test calls Resend or Clerk, AGENTS.md "External services"). "A test email" is a delivery of kind `alert` with the test-only template `test_message` (subject "Test subject", one heading and one paragraph from params `heading` and `body`), registered only in the test that uses it. Settings in tests: `WEB_URL=https://app.example.test`, `API_PUBLIC_URL=https://api.example.test`, `EMAIL_MAILING_ADDRESS=1 Test St, Toronto ON M5V 1A1`, `EMAIL_FROM=Headroom <test@example.test>`. Playwright proofs need the stack from `playwright.config.ts` (API on 8100, Clerk test users).

## Checks

### S1 - An email is sent once, in the house layout · 22 files · 120 KB · ~30k

**C1** - Requesting a test email for a user with default preferences, then committing, leaves exactly one `email_deliveries` row whose state is `sent` after the immediate attempt, with `attempts` 1, and `FakeEmailSender` received 1 send whose `to` is the Clerk primary address and whose subject is "Test subject" (AC 1, door 1)
Proof: `uv run pytest tests/test_email_delivery.py -k "request_sends_once"`

**C2** - Requesting the same test email twice with dedup key `"evt-1"` for the same user (two requests, two commits, as if one event were handled twice) leaves 1 row and 1 send. The same key for a second user gives 2 rows and 2 sends, and key `"evt-2"` for the first user gives a third (AC 2, door 1)
Proof: `uv run pytest tests/test_email_delivery.py -k "same_key_twice"`

**C3** - With one `pending` delivery, a first session claims it and holds the lock while a second session runs the delivery attempt for the same row: the second attempt sends nothing and returns. After the first finishes, `FakeEmailSender` holds exactly 1 send (AC 3)
Proof: `uv run pytest tests/test_email_delivery.py -k "concurrent_attempts"`

**C4** - Each send hands the sender the delivery's id as text as its idempotency key, and `ResendSender` calls `resend.Emails.send` with `options == {"idempotency_key": "<delivery id>"}` (checked with `resend.Emails.send` patched, no network) (AC 4, door 5)
Proof: `uv run pytest tests/test_email_delivery.py -k "idempotency_key"`
Proof: `uv run pytest tests/test_email_senders.py -k "resend_sender_params"`

**C5** - With the user's `alerts` preference off, requesting a test email of kind `alert` records 1 delivery in state `skipped` and makes 0 sends. With only `weekly_digest` off, an `alert` email is still sent (AC 5)
Proof: `uv run pytest tests/test_email_delivery.py -k "skipped_at_request"`

**C6** - A delivery left `pending` (sender failed with a retryable error), whose user then turns `alerts` off, is `skipped` on the next attempt with 0 further sends (AC 6)
Proof: `uv run pytest tests/test_email_delivery.py -k "skipped_at_send"`

**C7** - The send goes to the primary address `FakeClerkUsers` holds at attempt time: change it between the request and a retry and the retry goes to the new one. The template receives `first_name` "Dana"; a Clerk user with no first name renders the greeting with `first_name` null. No `email_deliveries` or `email_preferences` column holds the address (AC 7, door 6)
Proof: `uv run pytest tests/test_email_delivery.py -k "address_from_clerk"`

**C8** - `accounts.service` maps a Clerk user to its contact: the address whose `id` equals `primary_email_address_id` (not the first in the list), and `first_name`. `primary_email_address_id` null, or a Clerk "not found" error, gives "no contact". Proven against a fake of the `clerk-backend-api` `users.get` response (door 6)
Proof: `uv run pytest tests/test_clerk_contact.py -k "primary_address"`

**C9** - When Clerk has no primary address for the user, or no such user, the delivery is `failed` after one attempt with 0 sends, and the next job run attempts it 0 more times (AC 8)
Proof: `uv run pytest tests/test_email_delivery.py -k "no_contact_fails"`

**C10** - The rendered HTML has one 600 px wide column (`width="600"` or `width: 600px` on the outer table), "Headroom" as the first text, set in `Georgia`, the `h1` in Georgia, body text in `-apple-system, 'Segoe UI', Helvetica, sans-serif`, the page background `#F5F3EE`, the card `#FFFFFF`, and text `#16202B` (AC 9)
Proof: `uv run pytest tests/test_email_template.py -k "layout"`

**C11** - The HTML footer's text, in order, is the reason "You're getting this email because you're an owner of Harbor Street Plumbing on Headroom.", then "Email preferences" with `href="https://app.example.test/settings/email"`, " · ", "Unsubscribe" with `href="https://app.example.test/unsubscribe/<the user's token>"`, then "Headroom · 1 Test St, Toronto ON M5V 1A1" (AC 10, door 3)
Proof: `uv run pytest tests/test_email_template.py -k "footer"`

**C12** - The plain-text part holds the heading, the paragraph, the reason line, "Email preferences: https://app.example.test/settings/email", "Unsubscribe: https://app.example.test/unsubscribe/<token>" and "Headroom · 1 Test St, Toronto ON M5V 1A1", and contains no `<` tag (AC 11)
Proof: `uv run pytest tests/test_email_template.py -k "plain_text"`

**C13** - Every send carries headers `List-Unsubscribe: <https://api.example.test/v1/unsubscribe/<token>>` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, and `ResendSender` passes them in `params["headers"]` (AC 12, door 3)
Proof: `uv run pytest tests/test_email_delivery.py -k "unsubscribe_headers"`
Proof: `uv run pytest tests/test_email_senders.py -k "resend_sender_params"`

**C14** - A param `<b>Acme</b> & Co` appears in the HTML as `&lt;b&gt;Acme&lt;/b&gt; &amp; Co` and never as a `<b>` element, and appears unescaped in the text part (AC 13)
Proof: `uv run pytest tests/test_email_template.py -k "escapes_params"`

**C15** - `ConsoleSender` prints to standard output the recipient, the subject and the plain-text part (checked with `capsys`), and with `EMAIL_SENDER=console` a delivery is `sent` while `resend.Emails.send` (patched to fail the test) is never called (AC 14, door 5)
Proof: `uv run pytest tests/test_email_senders.py -k "console_sender"`

**C16** - `Settings()` fails with a `ValidationError` naming `email_sender` when `EMAIL_SENDER` is unset or `"smtp"`, and naming `resend_api_key` when `EMAIL_SENDER=resend` with no key; the error text never holds the rejected value. `CLERK_SECRET_KEY`, `EMAIL_FROM`, `EMAIL_MAILING_ADDRESS`, `WEB_URL` and `API_PUBLIC_URL` are each required (AC 15)
Proof: `uv run pytest tests/test_settings.py -k "email_settings"`

**C17** - Across a sent, a skipped, a retried and a failed delivery, every captured log line holds none of: the recipient address, the unsubscribe token, the Resend API key, the subject, any part of the HTML or text. `email.sent` carries `delivery_id`, `kind` and `provider_id`; `email.send_failed` and `email.failed` carry `delivery_id`, `kind`, `error_type` and `attempts` (AC 16)
Proof: `uv run pytest tests/test_email_delivery.py -k "logs_no_pii"`

**C18** - `uv run alembic upgrade head` creates `email_deliveries` with `uq_email_deliveries_dedup_key_user_id`, `ck_email_deliveries_state` and `ck_email_deliveries_kind`, and `email_preferences` with primary key `user_id` and a unique `unsubscribe_token`. Inserting a second row with the same `(dedup_key, user_id)` raises `IntegrityError`, a `state` of `"queued"` raises, and a `kind` of `"invite"` raises. `alembic downgrade -1` then `upgrade head` round-trips (door 1, door 2)
Proof: `uv run pytest tests/test_email_delivery.py -k "schema_constraints"`
Proof: `uv run pytest tests/test_migrations.py -k "email_tables_upgrade_downgrade_and_check"`

**C19** - `pyproject.toml` lists `resend`, `jinja2` and `clerk-backend-api` in `dependencies`, added with `uv add` (the lockfile is the tool's), and `app/modules/notifications/` holds `api.py`, `service.py`, `models.py`, `repository.py`; `migrations/env.py` imports its `models` (door 1, door 5, door 6)
Proof: `uv run pytest tests/test_email_senders.py -k "module_layout"`

### S2 - A failed send is retried until it goes out · 4 files · 40 KB · ~10k

**C20** - Each retryable error leaves the delivery `pending` with `attempts` raised by 1 and logs `email.send_failed`: a network timeout, Resend `429 rate_limit_exceeded`, `409 concurrent_idempotent_requests`, `409 resource_locked`, `500 application_error`, `503 service_unavailable`, and a Clerk lookup that times out (AC 17)
Proof: `uv run pytest tests/test_email_delivery.py -k "retryable_errors"`

**C21** - With a `FakeEmailSender` that fails with `503` on the first 2 sends: the immediate attempt fails, `email_retries` run 1 fails, run 2 sends. The delivery ends `sent` with `attempts` 3, and the sender received exactly 1 successful send. A 4th run sends nothing more (AC 18, Done-when 3)
Proof: `uv run pytest tests/test_email_retries_job.py -k "retried_until_sent"`

**C22** - A delivery that failed 50 times in a row is still attempted on run 51: there is no attempt cap (AC 18)
Proof: `uv run pytest tests/test_email_retries_job.py -k "no_attempt_cap"`

**C23** - Each permanent error marks the delivery `failed`, logs `email.failed`, and is never attempted by a later run: Resend `400 validation_error`, `401 missing_api_key`, `403 invalid_permission`, `409 invalid_idempotent_request`, `422 invalid_parameter` (AC 19)
Proof: `uv run pytest tests/test_email_delivery.py -k "permanent_errors"`

**C24** - `email_retries(now)` returns exactly the keys `emails_sent`, `emails_failed`, `emails_pending`: with one delivery that sends, one that fails permanently and one that fails retryably, it returns `{"emails_sent": 1, "emails_failed": 1, "emails_pending": 1}`. `sent`, `failed` and `skipped` rows are not attempted. `JOBS` is `(nightly_bank_sync, forecast_accuracy, email_retries)`, and `run_due` merges its counts into `jobs.run_finished` (AC 20)
Proof: `uv run pytest tests/test_email_retries_job.py -k "counts"`
Proof: `uv run pytest tests/test_run_due.py -k "email_retries"`

### S3 - Email preferences · 14 files · 90 KB · ~23k

**C25** - A signed-in user with no `email_preferences` row gets `GET /v1/me/email-preferences` `200` with exactly `{"alerts": true, "weekly_digest": true}`, and no row is created by the read (AC 21, door 2)
Proof: `uv run pytest tests/test_email_preferences_api.py -k "defaults"`

**C26** - `PUT /v1/me/email-preferences` with `{"alerts": false, "weekly_digest": true}` answers `200` with that body, the next `GET` returns it, and a second `PUT` with `{"alerts": true, "weekly_digest": false}` replaces it (AC 22)
Proof: `uv run pytest tests/test_email_preferences_api.py -k "put_saves"`

**C27** - `PUT` answers `422` `application/problem+json` and leaves the saved values unchanged for each of: `{"alerts": false}`, `{"weekly_digest": false}`, `{}`, `{"alerts": false, "weekly_digest": true, "sms": true}`, `{"alerts": "no", "weekly_digest": true}`, `{"alerts": null, "weekly_digest": true}` (AC 23)
Proof: `uv run pytest tests/test_email_preferences_api.py -k "invalid_body"`

**C28** - `GET` and `PUT` with no token, and with an invalid token, answer `401` problem details (AC 24)
Proof: `uv run pytest tests/test_email_preferences_api.py -k "unauthenticated"`

**C29** - User A's `PUT` turns their alerts off; user B's `GET` still returns `{"alerts": true, "weekly_digest": true}`, and B's `PUT` changes nothing of A's. A `?user_id=` query parameter set to the other user's id is ignored (AC 25)
Proof: `uv run pytest tests/test_email_preferences_api.py -k "own_preferences_only"`

**C30** - `contracts/openapi.json` lists `GET` and `PUT /v1/me/email-preferences` and `POST /v1/unsubscribe/{token}`, re-exporting gives no diff, and `npm run api:types` gives no diff in `lib/api/schema.d.ts` (door 4)
Proof: `uv run pytest tests/test_export_openapi.py -k "email_routes"`
Proof: `uv run python -m app.export_openapi && git diff --exit-code ../../contracts/openapi.json`
Proof: `npm run api:types && git diff --exit-code lib/api/schema.d.ts`

**C31** - The `/settings/email` page, rendered with the loader returning `{alerts: true, weekly_digest: false}`, shows the heading "Email preferences", then a switch labelled "Cash gap alerts" (checked) with "Email me when cash is projected to fall below my minimum.", then "Weekly digest" (unchecked) with "A summary of my forecast every Monday morning.", in that DOM order; each switch is a `role="switch"` with an accessible name (AC 26)
Proof: `npx vitest run tests/email-preferences-page.test.tsx -t "shows both switches"`

**C32** - Flipping "Weekly digest" on calls the save action once with `{alerts: true, weekly_digest: true}` and, on success, shows the toast "Email preferences saved" (AC 27)
Proof: `npx vitest run tests/email-preferences-page.test.tsx -t "saves on flip"`

**C33** - The save server action calls `PUT /v1/me/email-preferences` with the session's auth headers and both booleans, and returns `{ok: false}` on a non-2xx answer or a thrown error, never throwing (AC 27, AC 28)
Proof: `npx vitest run tests/email-preferences-actions.test.ts -t "save action"`

**C34** - When the save action returns `{ok: false}`, the flipped switch returns to its previous state and "We couldn't save your email preferences. Try again." appears in a `role="alert"` element (AC 28)
Proof: `npx vitest run tests/email-preferences-page.test.tsx -t "save fails"`

**C35** - When the loader throws, the page renders the existing settings error state ("We couldn't load this page" with "Try again"), and `app/(app)/settings/email/loading.tsx` renders the existing skeleton (AC 29)
Proof: `npx vitest run tests/email-preferences-page.test.tsx -t "error and loading"`

**C36** - In the running app, a signed-in user opens Settings → Email preferences, turns off "Weekly digest", reloads, and sees it still off. At 375 px the page has no horizontal scroll and each switch row is at least 44 px tall; Tab reaches both switches in order and Space flips the focused one; axe reports 0 violations; signed out, `/settings/email` redirects to `/sign-in` (AC 24, AC 26, AC 27, AC 30)
Proof: `npx playwright test e2e/email-preferences.spec.ts --grep "email preferences"`

### S4 - Unsubscribe in one click without signing in · 14 files · 80 KB · ~20k

**C37** - `POST /v1/unsubscribe/{token}` with a user's token and no `Authorization` header answers `200` `{"status": "unsubscribed"}`; that user's `GET /v1/me/email-preferences` straight after returns `{"alerts": false, "weekly_digest": false}`. A user who had only alerts on ends with both off (AC 31, door 4, Done-when 2)
Proof: `uv run pytest tests/test_unsubscribe_api.py -k "unsubscribes_without_login"`

**C38** - Posting the same token a second time answers `200` `{"status": "unsubscribed"}` and leaves both preferences off and `updated_at` unchanged (AC 32)
Proof: `uv run pytest tests/test_unsubscribe_api.py -k "twice"`

**C39** - An unknown 43-character token, a 500-character token and `"x"` each answer `404` `application/problem+json`, and no user's preferences change (AC 33)
Proof: `uv run pytest tests/test_unsubscribe_api.py -k "unknown_token"`

**C40** - A `POST` with `Content-Type: application/x-www-form-urlencoded` and body `List-Unsubscribe=One-Click` unsubscribes the same way and answers `200`; so does an empty body and a JSON body (AC 34)
Proof: `uv run pytest tests/test_unsubscribe_api.py -k "one_click_body"`

**C41** - After an unsubscribe, a delivery to that user that was `pending` is `skipped` on its next attempt with 0 sends, and a new test-email request is recorded `skipped` with 0 sends (AC 35, Done-when 2)
Proof: `uv run pytest tests/test_unsubscribe_api.py -k "takes_effect_immediately"`

**C42** - A user's unsubscribe token matches `^[A-Za-z0-9_-]{43}$`, is the same in two emails sent a day apart and after a `PUT` of preferences, and two users never share one (AC 36, door 3)
Proof: `uv run pytest tests/test_unsubscribe_api.py -k "token_shape"`

**C43** - `tests/auth-protect.test.ts` exempts exactly `unsubscribe/[token]/page.tsx` beyond the root layout, sign-in and sign-up, and every other page and layout still calls `await auth.protect()`; the unsubscribe page lives outside `(app)` and renders without calling `auth` (door 4)
Proof: `npx vitest run tests/auth-protect.test.ts -t "every page protected"`

**C44** - The `/unsubscribe/[token]` page renders the "Headroom" wordmark, the `h1` "Unsubscribe from Headroom emails?", "You'll stop getting cash gap alerts and the weekly digest." and a primary "Unsubscribe" button, and rendering it calls no server action and no API (AC 37)
Proof: `npx vitest run tests/unsubscribe-page.test.tsx -t "asks before unsubscribing"`

**C45** - Pressing "Unsubscribe" calls the action once with the token, disables the button and shows "Unsubscribing…" while pending. On `{status: "unsubscribed"}` the page shows "You're unsubscribed" and "You won't get any more emails from Headroom. To turn them back on, go to Email preferences." with a link to `/settings/email`. On `{status: "invalid"}` it shows "This unsubscribe link isn't valid" and "To change your emails, go to Email preferences." with the same link. On `{status: "error"}` it shows "We couldn't unsubscribe you. Try again." in a `role="alert"` element and the button is enabled again (AC 38, AC 39, AC 40, AC 41)
Proof: `npx vitest run tests/unsubscribe-page.test.tsx -t "outcomes"`

**C46** - The unsubscribe action posts to `/v1/unsubscribe/{token}` with no `Authorization` header and maps `200` to `unsubscribed`, `404` to `invalid`, and any other status or a thrown error to `error` (AC 38-41, door 4)
Proof: `npx vitest run tests/unsubscribe-action.test.ts -t "unsubscribe action"`

**C47** - In the running app, a signed-out visitor opens `/unsubscribe/<the test user's token>` and is not redirected; opening it leaves the user's preferences on; pressing "Unsubscribe" shows "You're unsubscribed", and the user's preferences read both off. At 375 px there is no horizontal scroll and the button is at least 44 px tall; at 1280 px the column is at most 480 px wide and centred; Tab reaches "Unsubscribe" and Enter presses it; axe reports 0 violations (AC 37, AC 39, AC 42)
Proof: `npx playwright test e2e/unsubscribe.spec.ts --grep "unsubscribe"`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /v1/me/email-preferences` statuses (2) | 200 C25 · 401 C28 | - |
| `PUT /v1/me/email-preferences` statuses (3) | 200 C26 · 401 C28 · 422 C27 | - |
| `POST /v1/unsubscribe/{token}` statuses (2) | 200 C37 · 404 C39 | - |
| `GET /settings/email` page outcomes (2) | 200 C36 · 307 to `/sign-in` C36 | - |
| `GET /unsubscribe/{token}` page outcomes (1) | 200 with no sign-in C47 | - |
| delivery states (4) | `pending` C20 · `sent` C1 · `failed` C9, C23 · `skipped` C5, C6 | - |
| delivery transitions (5) | request -> `pending` C1 · request -> `skipped` C5 · `pending` -> `sent` C21 · `pending` -> `failed` C9, C23 · `pending` -> `skipped` C6 | - |
| email kinds (2) | `alert` C5 · `weekly_digest` C5 | - |
| retryable errors (7) | timeout C20 · `429` C20 · `409 concurrent_idempotent_requests` C20 · `409 resource_locked` C20 · `500` C20 · `503` C20 · Clerk timeout C20 | - |
| permanent errors (7) | `400` C23 · `401` C23 · `403` C23 · `409 invalid_idempotent_request` C23 · `422` C23 · no Clerk primary address C9 · no Clerk user C9 | - |
| `PUT` body rejections (6) | missing `alerts` C27 · missing `weekly_digest` C27 · empty C27 · extra field C27 · string value C27 · null value C27 | - |
| unsubscribe bodies (3) | form `List-Unsubscribe=One-Click` C40 · empty C40 · JSON C40 | - |
| footer parts (5) | reason C11 · preferences link C11 · unsubscribe link C11 · mailing address C11 · text-part copies C12 | - |
| email headers (2) | `List-Unsubscribe` C13 · `List-Unsubscribe-Post` C13 | - |
| unsubscribe page outcomes (4) | before pressing C44 · `unsubscribed` C45 · `invalid` C45 · `error` C45 | - |
| preferences screen states (4) | loaded C31 · save failed C34 · load failed C35 · loading C35 | - |
| Landing doors (6) | 1 C2, C18 · 2 C18, C25 · 3 C11, C13, C42 · 4 C37, C43, C46 · 5 C4, C15, C19 · 6 C7, C8 | - |
| startup config: `JOBS` (1 assembly) | `run_due.main()`, the only reader of `JOBS` (AD-056); this spec adds no event subscription C24 | - |
| startup config: email settings (1 shared assembly) | the one cached `get_settings()` that `api` and `jobs` both build from (AD-001; Railway's `jobs` reads `api`'s values by reference, AD-054) C16 | - |

- Claims naming a status code, route or response shape: C25-C30, C37-C40, C46 - each has a proof that crosses the HTTP boundary.
- No other check claims more than the cases its proof exercises.

## Swept

- validation: C16 (settings), C27 (PUT body), C39 (token shape and length)
- failure modes: C9, C20, C23 (send and lookup failures leave a recorded state), C34, C35, C45 (web failure states)
- idempotency: C2 (same key twice), C4 (provider idempotency key), C38 (unsubscribe twice)
- authorization: C28 (no session), C29 (own preferences only), C37 (token is the only credential), C43 (public page exemption is exactly one)
- concurrency: C3 (two processes, one delivery)
- data lifecycle: n/a - rows are kept with no purge in v1 (plan, Out of scope); a preferences row is created lazily, and C25 proves a read creates none
- dependency failure: C20, C21 (Resend and Clerk outages retried), C23 (permanent provider errors stop)
- state transitions: C1, C5, C6, C9, C21, C23, C24 (terminal states never re-attempted)
- observability: C17 (send logs carry ids and error types, never PII), C24 (job counts in `jobs.run_finished`)

## Handoff

Size from `wc -c` on the existing files each slice reads or edits, plus an estimate of the new files, divided by four:

- S1 = ~30k (new `notifications` module, templates, two senders, migration, `settings.py` 3.5 KB, `accounts/service.py` 4.9 KB, `test_settings.py` 6.3 KB, `conftest.py` 4 KB, `log.py` 3 KB); S2 adds ~10k (`jobs/__init__.py`, `test_run_due.py` 11.8 KB) for 40k; S3 enters the web at ~23k (`accounts/api.py` 4.6 KB, `en.json` 18.8 KB, settings banks pattern ~7 KB) for 63k; S4 adds ~20k (`main.py` 3.6 KB, `auth-protect.test.ts`, `railway.ts` 4.2 KB, `.env.example`) for ~83k, under the 150k budget - one builder
- Mechanism: one builder (under budget, no ask)
