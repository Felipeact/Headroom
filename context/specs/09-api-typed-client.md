# Spec 09: Typed API client

- **Milestone:** 2, foundations
- **Status:** Done
- **Depends on:** 01, 02

## Goal

Let the web app call the API with types generated from the API itself, so nobody writes request types by hand.

## Build

- `uv run python -m app.export_openapi` writes `contracts/openapi.json` from the FastAPI app.
- `npm run api:types` generates `lib/api/schema.d.ts` from that file with openapi-typescript. `lib/api/client.ts` wraps openapi-fetch and sets the API's base URL.
- Commit both generated files. CI regenerates them and fails if they differ.
- The web app calls the API only from the server, in server components and server actions.

**Docs:** [openapi-typescript and openapi-fetch](https://openapi-ts.dev)

## Done when

- [x] A test page shows the result of `GET /healthz/live` through the typed client.
- [x] Changing an endpoint without regenerating the files makes CI fail.
