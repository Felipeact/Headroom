# Welcome redirect host verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 9e60eab..e00c0e1
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

## Checks

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | request received as `http://localhost:8080/welcome?...` answers 307 with `Location: /invite/abc`, no scheme or host | `npx vitest run tests/welcome-route.test.ts --reporter=verbose` exit 0; "goes on to a same-site next path and never names the host the server listens on" ran, passed | `frontend/tests/welcome-route.test.ts:39` - `expect(response.headers.get('location')).toBe('/invite/abc')` (status at :38, localhost origin at :37) | PASS |
| C2 | no `next` answers 307 `Location: /`, protect then capture | same run; "protects the route, records the sign-up, and redirects to / with 307" ran, passed | `frontend/tests/welcome-route.test.ts:28` - `expect(order).toEqual(['protect', 'capture'])`; `:31` - `expect(response.headers.get('location')).toBe('/')` | PASS |
| C3 | `//evil.test`, `https://evil.test`, empty answer 307 `Location: /` | same run; three `refuses next=` cases ran, passed | `frontend/tests/welcome-route.test.ts:45` - `expect(response.headers.get('location')).toBe('/')` (status at :44) | PASS |

Judgment: level is right for light - the claims name a status and header and every proof calls the real `GET` with a `NextRequest`, so the boundary is the handler's own Response. The `.test.ts` proofs exercise tests the diff touched (`git diff` shows all three modified). Sampling is complete: the 5 `next` values and the one status in the Coverage table each map to a proof. Swept `authorization: existing` holds: `frontend/app/welcome/route.ts:11` calls `auth.protect()` first, asserted by C2's order check.

## Fix judgment

The fix addresses the reported bug. `next-server.js:1284` builds `initUrl` from `fetchHostname:port` when both are set, so under `next start` `request.url` names the listening address. The old `new URL(next, request.url)` therefore produced `http://localhost:<port>/invite/<token>`. The new handler (`route.ts:14`) returns `new Response(null, {status: 307, headers: {Location: next}})` and never reads the host. `safePath` (`lib/safe-path.ts`) only returns paths, so `next` is always same-site. A relative Location is valid under RFC 9110 and followed by every browser, resolved against the URL the browser requested, which is the public host. Clerk's `forceRedirectUrl` is a client-side navigation to `/welcome`; the browser then follows the 307 itself, so it needs no knowledge of the host. No other absolute redirect is built from `request.url`: the only matches in `frontend/` are the comment in `route.ts` and the `new URL(value)` parse in `safe-path.ts`, which does not produce a redirect. All other redirects are `next/navigation` `redirect("/path")` calls with relative paths, and `proxy.ts` contains no `redirect(` or `nextUrl` use.

Caveats, not failures: no test goes through a real `next start` behind a proxy, so the host behaviour is proven at handler level plus the Next source line, not end to end. The invitation email link depends on `WEB_URL` in Railway variables, which is out of scope per `checks.md` and still needs checking by the user.

## Gate

`npx vitest run tests/welcome-route.test.ts --reporter=verbose` - 9 passed, 0 failed
