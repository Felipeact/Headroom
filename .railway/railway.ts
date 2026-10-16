import { defineRailway, github, postgres, preserve, project, service, volume } from "railway/iac";

const REPO = "Felipeact/Headroom";
const US_EAST = "us-east4-eqdc4a";

// What differs between the two environments (spec 34 door 1); everything else is shared.
// Custom domains exist only in production (spec 34 door 8); staging keeps Railway's own.
const ENVIRONMENTS = {
  staging: { branch: "development", sentryEnvironment: "staging", webDomains: [], apiDomains: [] },
  production: {
    branch: "main",
    sentryEnvironment: "production",
    webDomains: ["headroom.felipeviana.com"],
    apiDomains: ["api.headroom.felipeviana.com"],
  },
} as const;

// Omits `domains` when there are none, so staging's generated domains are never touched.
const domains = (list: readonly string[]) => (list.length > 0 ? { domains: [...list] } : {});

export default defineRailway((ctx) => {
  const env = ctx.isEnvironment("production")
    ? ENVIRONMENTS.production
    : ctx.isEnvironment("staging")
      ? ENVIRONMENTS.staging
      : undefined;
  if (env === undefined) {
    throw new Error(`.railway/railway.ts describes staging and production, not ${ctx.environment}`);
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
    source: github(REPO, { branch: env.branch, rootDirectory: "/services/core", checkSuites: true }),
    build: { builder: "RAILPACK", watchPatterns: ["/services/core/**"] },
    preDeploy: "alembic upgrade head",
    start: "fastapi run app/main.py",
    healthcheck: "/healthz/ready",
    replicas: { [US_EAST]: 1 },
    ...domains(env.apiDomains),
    env: {
      // Railway resolves the references; the psycopg scheme is required by app/settings.py.
      DATABASE_URL:
        "postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}",
      // The DSN is set with `railway variable set`; preserve() keeps it out of this file.
      SENTRY_DSN: preserve(),
      SENTRY_ENVIRONMENT: env.sentryEnvironment,
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
      // Email (spec 28), set with `railway variable set`: the sender (`console` or `resend`)
      // and its key, the From address, the footer's mailing address, the public web and API
      // URLs for the footer and List-Unsubscribe links, and the Clerk Backend API key.
      EMAIL_SENDER: preserve(),
      RESEND_API_KEY: preserve(),
      EMAIL_FROM: preserve(),
      EMAIL_MAILING_ADDRESS: preserve(),
      WEB_URL: preserve(),
      API_PUBLIC_URL: preserve(),
      CLERK_SECRET_KEY: preserve(),
      // The weekly metrics report (spec 32), set with `railway variable set`: the region's PostHog
      // app host, the project and a personal API key with Query Read, and the report recipients.
      POSTHOG_APP_HOST: preserve(),
      POSTHOG_PROJECT_ID: preserve(),
      POSTHOG_PERSONAL_API_KEY: preserve(),
      METRICS_REPORT_RECIPIENTS: preserve(),
    },
  });

  const web = service("web", {
    source: github(REPO, { branch: env.branch, rootDirectory: "/frontend", checkSuites: true }),
    build: { builder: "RAILPACK", watchPatterns: ["/frontend/**"] },
    // Public and dependency-free: every page requires login, so "/" answers 307 (spec 10).
    healthcheck: "/healthz",
    replicas: { [US_EAST]: 1 },
    ...domains(env.webDomains),
    env: {
      // Set with `railway variable set` (spec 10): the Clerk keys and the API's address.
      API_URL: preserve(),
      CLERK_SECRET_KEY: preserve(),
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: preserve(),
      NEXT_PUBLIC_CLERK_SIGN_IN_URL: "/sign-in",
      NEXT_PUBLIC_CLERK_SIGN_UP_URL: "/sign-up",
      // Sentry for the web app (spec 07), with its own client key per environment (spec 34).
      NEXT_PUBLIC_SENTRY_DSN: preserve(),
      NEXT_PUBLIC_SENTRY_ENVIRONMENT: env.sentryEnvironment,
      // PostHog (spec 32), set with `railway variable set`: the project token and the region's
      // ingestion host. Only the web server sends events, so neither is a NEXT_PUBLIC_ variable.
      POSTHOG_KEY: preserve(),
      POSTHOG_HOST: preserve(),
    },
  });

  // The hourly job runner (spec 15): runs `python -m app.jobs.run_due`, which exits when done.
  // No healthcheck (it serves nothing), no pre-deploy (`api` migrates), and no restart:
  // a failed run is retried by the next hourly run, never at once.
  const jobs = service("jobs", {
    source: github(REPO, { branch: env.branch, rootDirectory: "/services/core", checkSuites: true }),
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
      // Spec 28: the email retries job sends through the same settings as `api`.
      EMAIL_SENDER: "${{api.EMAIL_SENDER}}",
      RESEND_API_KEY: "${{api.RESEND_API_KEY}}",
      EMAIL_FROM: "${{api.EMAIL_FROM}}",
      EMAIL_MAILING_ADDRESS: "${{api.EMAIL_MAILING_ADDRESS}}",
      WEB_URL: "${{api.WEB_URL}}",
      API_PUBLIC_URL: "${{api.API_PUBLIC_URL}}",
      CLERK_SECRET_KEY: "${{api.CLERK_SECRET_KEY}}",
      // Spec 32: the Tuesday metrics report reads PostHog and emails the recipients.
      POSTHOG_APP_HOST: "${{api.POSTHOG_APP_HOST}}",
      POSTHOG_PROJECT_ID: "${{api.POSTHOG_PROJECT_ID}}",
      POSTHOG_PERSONAL_API_KEY: "${{api.POSTHOG_PERSONAL_API_KEY}}",
      METRICS_REPORT_RECIPIENTS: "${{api.METRICS_REPORT_RECIPIENTS}}",
    },
  });

  return project("headroom", {
    resources: [api, jobs, Postgres, web, postgresVolume],
  });
});
