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
    },
  });

  const web = service("web", {
    source: github(REPO, { branch: "development", rootDirectory: "/frontend", checkSuites: true }),
    build: { builder: "RAILPACK", watchPatterns: ["/frontend/**"] },
    healthcheck: "/",
    replicas: { [US_EAST]: 1 },
  });

  return project("headroom", {
    resources: [api, Postgres, web, postgresVolume],
  });
});
