# Welcome redirect host checks

Profile: light
Plan: none - change under three files, no one-way door

## Intent

A new user who finishes Clerk's sign-up lands on `/welcome`, which records the sign-up and then
redirects to where they were headed - for an invited bookkeeper, `/invite/<token>`. The route
builds that redirect as an absolute URL from `request.url`, and under `next start` Next.js 16.3.8
builds `request.url` from the address the server listens on, not the public host
(`node_modules/next/dist/server/next-server.js:1284`). Behind Railway's proxy the bookkeeper is
sent to `http://localhost:<port>/invite/<token>`. After this change the redirect carries only a
same-site path, so the browser resolves it against the host it actually used.

3 checks in 1 slice · 0 one-way doors · 0 open

## Checks

### S1 - Relative welcome redirect · 2 files · 3 KB · ~1k

**C1** - `GET /welcome?next=/invite/abc` received as `http://localhost:8080/welcome?...` answers `307` with `Location: /invite/abc` - no scheme, no host
Proof: `npx vitest run tests/welcome-route.test.ts -t "never names the host the server listens on"`

**C2** - `GET /welcome` with no `next` answers `307` with `Location: /`, after `auth.protect` then `capture("sign_up_completed")`
Proof: `npx vitest run tests/welcome-route.test.ts -t "protects the route, records the sign-up"`

**C3** - `next` of `//evil.test`, `https://evil.test` or empty answers `307` with `Location: /`
Proof: `npx vitest run tests/welcome-route.test.ts -t "refuses next="`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| `GET /welcome` next values (5) | none C2 · same-site path C1 · `//evil.test` C3 · `https://evil.test` C3 · empty C3 | - |
| `GET /welcome` statuses (1) | 307 C1 | - |

- Claims naming a status code or header: C1, C2, C3 - each calls the route handler with a `NextRequest`

## Swept

- validation: C3
- failure modes: n/a - the handler has no branch that can fail besides `auth.protect`, unchanged
- idempotency: n/a - a redirect; `capture` behaviour unchanged by this fix
- authorization: existing - `auth.protect()` first in the handler, asserted by C2
- concurrency: n/a - stateless redirect
- data lifecycle: n/a - nothing stored
- dependency failure: n/a - unchanged analytics path
- state transitions: n/a - none
- observability: n/a - `sign_up_completed` unchanged, asserted by C2

## Out of scope

- `WEB_URL` in staging Railway variables - the invitation email's link is built from it; not visible from the repo, flagged to the user

## Handoff

- S1 = ~1k, one route and its test, under the 150k budget - one builder
