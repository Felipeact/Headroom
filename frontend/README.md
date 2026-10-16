# frontend

The Headroom web app. It's built with Next.js (App Router), React, TypeScript in strict mode, Tailwind CSS, and shadcn/ui. Clerk handles sign-in.

The commands and rules in the root [AGENTS.md](../AGENTS.md) are the source of truth, and [AGENTS.md](AGENTS.md) in this folder adds guidance specific to Next.js. This file is a guide to this folder.

## Setup

You need Node.js and a running API (see [services/core/README.md](../services/core/README.md)).

```bash
cp .env.example .env.local   # use a Clerk development instance only
npm install
npm run dev                  # http://localhost:3000
```

### Environment variables

`.env.example` lists every variable with a comment:

| Variables | Used for |
|---|---|
| `API_URL` | The API. It's called only from server code. |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_CLERK_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | Sign-in |
| `NEXT_PUBLIC_SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | Error monitoring. Leave the DSN empty to turn Sentry off. |
| `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` | Uploading source maps at build time (optional) |
| `E2E_CLERK_USER_USERNAME` | The Clerk test user that Playwright signs in as |

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Starts the development server |
| `npm run build` | Builds for production |
| `npm run lint` | Runs ESLint |
| `npm run typecheck` | Generates route types and runs `tsc` |
| `npm test` | Runs the Vitest unit and component tests |
| `npm run test:e2e` | Runs the Playwright tests (it starts the dev server itself) |
| `npm run api:types` | Regenerates `lib/api/schema.d.ts` from `contracts/openapi.json` |

## Layout

```text
app/
├── (app)/                  # Signed-in screens, inside the app shell
│   ├── page.tsx            # Dashboard
│   ├── alerts/             # Alert list and alert page
│   ├── expected-payments/
│   └── settings/           # Business, banks, members, email, data
├── onboarding/             # business → bank → accounts → minimum balance → forecast
├── sign-in/, sign-up/      # Clerk
├── unsubscribe/[token]/    # Email unsubscribe link
├── dev/                    # Developer-only check pages
└── healthz/                # Health check route
components/
├── ui/                     # shadcn/ui components (added with the shadcn CLI)
└── <feature>/              # Screen components: dashboard, alert-page, onboarding, settings, shell, ...
lib/
├── api/                    # The typed API client, one file per area
├── format.ts               # Money and date formatting
└── ...
messages/en.json            # All interface text
i18n/                       # next-intl setup
tests/                      # Vitest tests
e2e/                        # Playwright tests
```

## How the app is built

- **Data:** pages load data in server components and make changes through server actions. The browser never calls the API.
- **API client:** every call goes through the typed client in `lib/api/`. Its types are generated from the API's OpenAPI contract, so never write request or response types by hand. After the API changes, run `npm run api:types`.
- **Money:** amounts arrive as integer cents. Format them only with `lib/format.ts`.
- **Text:** all interface text lives in `messages/en.json`. Don't hard-code text in components. v1 is English only.
- **Design:** follow [context/DESIGN.md](../context/DESIGN.md) and the mockups in [design/mockups/](../design/mockups/). Use only the design tokens and the components in `components/ui/`. Add new shadcn components with `npx shadcn@latest add <name>`. Ask before adding colors, fonts, or new components.
- **Code style:** components are named in PascalCase, hooks start with `use`, and each file holds one component. Avoid `any`.

### Every screen

- has loading, empty, and error states
- works at 375 pixels wide
- can be used with the keyboard alone
- has touch targets of at least 44 pixels
- has a Playwright test that includes an axe accessibility check

## Tests and checks

```bash
npm run lint && npm run typecheck && npm test && npm run build
npm run test:e2e
```

- **Unit and component tests** (`tests/`): Vitest and Testing Library.
- **End-to-end tests** (`e2e/`): Playwright, with an axe check on every screen. They sign in as the Clerk test user set in `E2E_CLERK_USER_USERNAME`.

## Deploy

This app runs on Railway as the `web` service. A push to `development` that changes this folder deploys it to staging once CI passes. The service settings live in [`.railway/railway.ts`](../.railway/railway.ts).
