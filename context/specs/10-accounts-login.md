# Spec 10: Login with Clerk

- **Milestone:** 2, foundations
- **Status:** In progress
- **Depends on:** 07, 08, 09

## Goal

Let people sign up and sign in, and let the API know who is calling.

## Build

- **Web:**
  - Set up Clerk by following its current Next.js quickstart.
  - Theme the sign-in and sign-up pages through Clerk's appearance settings.
  - Every page except sign-in and sign-up requires login.
- **Client:** the typed client sends the Clerk session token to the API.
- **API:**
  - Verify the Clerk session token on every request.
  - The first verified request from a new user creates a `users` row, keyed by the Clerk user ID.
  - `GET /v1/me` returns the current user.

**Docs:** [Clerk](https://clerk.com/docs)

## Done when

- [ ] Signing in shows the app shell with the user's name, and signing out returns to sign-in.
- [ ] The API returns 401 for a missing, expired, or tampered token, tested with tokens signed by a local test key.
- [ ] No password or token is stored or logged.
