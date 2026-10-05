import { defineRailway, github, postgres, preserve, project, service, volume } from "railway/iac";

const REPO = "Felipeact/Headroom";
const US_EAST = "us-east4-eqdc4a";

export default defineRailway((ctx) => {
  // Only staging exists until spec 34 adds production.
  if (!ctx.isEnvironment("staging")) {
    throw new Error(`.railway/railway.ts only describes staging, not ${ctx.environment}`);
  }

  const Postgres = postgres("Postgres", { region: US_EAST });
  Postgres.networking = { privateNetworkEndpoint: "postgres" };
  const postgresVolume = volume("postgres-volume", {
    alerts: { usage: { "100": {}, "80": {}, "95": {} } },
    allowOnlineResize: true,
    region: US_EAST,
    sizeMB: 5000,
  });

  const api = service("api", {
    source: github(REPO, { branch: "development", rootDirectory: "/services/core", checkSuites: true }),
    build: { builder: "RAILPACK", watchPatterns: ["/services/core/**"] },
    preDeploy: "alembic upgrade head",
    start: "fastapi run app/main.py",
    healthcheck: "/healthz/ready",
    replicas: { [US_EAST]: 1 },
    env: {
      // Railway resolves the references; the psycopg scheme is required by app/settings.py.
      DATABASE_URL:
        "postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}",
      // The DSN is set with `railway variable set`; preserve() keeps it out of this file.
      SENTRY_DSN: preserve(),
      SENTRY_ENVIRONMENT: "staging",
      // Clerk (spec 10), set with `railway variable set`: the PEM public key, and the web
      // origin allowed in a token's azp claim.
      CLERK_JWT_KEY: preserve(),
      CLERK_AUTHORIZED_PARTIES: preserve(),
      // Plaid (specs 12, 14) and the access-token keys, set with `railway variable set`.
      PLAID_CLIENT_ID: preserve(),
      PLAID_SECRET: preserve(),
      PLAID_ENV: preserve(),
      PLAID_WEBHOOK_URL: preserve(),
      TOKEN_ENCRYPTION_KEYS: preserve(),
    },
  });

  const web = service("web", {
    source: github(REPO, { branch: "development", rootDirectory: "/frontend", checkSuites: true }),
    build: { builder: "RAILPACK", watchPatterns: ["/frontend/**"] },
    // Public and dependency-free: every page requires login, so "/" answers 307 (spec 10).
    healthcheck: "/healthz",
    replicas: { [US_EAST]: 1 },
    env: {
      // Set with `railway variable set` (spec 10): the Clerk keys and the API's address.
      API_URL: preserve(),
      CLERK_SECRET_KEY: preserve(),
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: preserve(),
      NEXT_PUBLIC_CLERK_SIGN_IN_URL: "/sign-in",
      NEXT_PUBLIC_CLERK_SIGN_UP_URL: "/sign-up",
    },
  });

  // The hourly job runner (spec 15): runs `python -m app.jobs.run_due`, which exits when done.
  // No healthcheck (it serves nothing), no pre-deploy (`api` migrates), and no restart:
  // a failed run is retried by the next hourly run, never at once.
  const jobs = service("jobs", {
    source: github(REPO, { branch: "development", rootDirectory: "/services/core", checkSuites: true }),
    build: { builder: "RAILPACK", watchPatterns: ["/services/core/**"] },
    start: "python -m app.jobs.run_due",
    deploy: { cronSchedule: "0 * * * *", restartPolicyType: "NEVER" },
    replicas: { [US_EAST]: 1 },
    env: {
      // The template `api` uses (AD-006), not a reference to a reference (spec 15 door 7).
      DATABASE_URL:
        "postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}",
      // One source for each secret: references to `api`'s variables of the same name.
      CLERK_JWT_KEY: "${{api.CLERK_JWT_KEY}}",
      PLAID_CLIENT_ID: "${{api.PLAID_CLIENT_ID}}",
      PLAID_SECRET: "${{api.PLAID_SECRET}}",
      PLAID_ENV: "${{api.PLAID_ENV}}",
      TOKEN_ENCRYPTION_KEYS: "${{api.TOKEN_ENCRYPTION_KEYS}}",
      SENTRY_DSN: "${{api.SENTRY_DSN}}",
      SENTRY_ENVIRONMENT: "${{api.SENTRY_ENVIRONMENT}}",
    },
  });

  return project("headroom", {
    resources: [api, jobs, Postgres, web, postgresVolume],
  });
});
