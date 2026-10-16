// Spec 34 C9, C10: evaluate .railway/railway.ts per environment, offline.
// Usage: node iac-check.mjs <repo root> c9|c10. Prints PASS or the first mismatch; exit 0/1.
import { isDeepStrictEqual } from "node:util";
import { pathToFileURL } from "node:url";

const [root, which] = process.argv.slice(2);
const sdk = await import(pathToFileURL(`${root}/.railway/node_modules/railway/dist/index.js`).href);
const program = (await import(pathToFileURL(`${root}/.railway/railway.ts`).href)).default;

const compile = (environment) =>
  program(sdk.createRailwayContext({ environment }), sdk.project);

function fail(message) {
  console.error(`FAIL ${which}: ${message}`);
  process.exit(1);
}

async function c9() {
  try {
    await compile("preview");
    fail("preview did not throw");
  } catch (error) {
    if (!String(error?.message).includes("preview")) fail(`error does not name preview: ${error?.message}`);
  }
  for (const environment of ["staging", "production"]) {
    try {
      await compile(environment);
    } catch (error) {
      fail(`${environment} threw: ${error?.message}`);
    }
  }
}

const byName = (definition) => Object.fromEntries(definition.resources.map((r) => [r.name, r]));
const literal = (resource, name) => {
  const variable = resource.variables?.[name];
  return variable?.type === "literal" ? variable.value : undefined;
};

async function c10() {
  const expected = {
    staging: { branch: "development", sentry: "staging" },
    production: { branch: "main", sentry: "production" },
  };
  const compiled = {};
  for (const [environment, want] of Object.entries(expected)) {
    const resources = byName(await compile(environment));
    compiled[environment] = resources;
    for (const name of ["api", "web", "jobs"]) {
      const branch = resources[name]?.source?.branch;
      if (branch !== want.branch) fail(`${environment} ${name} branch is ${branch}`);
    }
    if (literal(resources.api, "SENTRY_ENVIRONMENT") !== want.sentry) fail(`${environment} api SENTRY_ENVIRONMENT`);
    if (literal(resources.web, "NEXT_PUBLIC_SENTRY_ENVIRONMENT") !== want.sentry) {
      fail(`${environment} web NEXT_PUBLIC_SENTRY_ENVIRONMENT`);
    }
    if (literal(resources.jobs, "SENTRY_ENVIRONMENT") !== "${{api.SENTRY_ENVIRONMENT}}") {
      fail(`${environment} jobs SENTRY_ENVIRONMENT is not api's`);
    }
    const custom = (r) => Object.keys(r?.networking?.customDomains ?? {}).sort();
    const wantWeb = environment === "production" ? ["headroom.felipeviana.com"] : [];
    const wantApi = environment === "production" ? ["api.headroom.felipeviana.com"] : [];
    if (!isDeepStrictEqual(custom(resources.web), wantWeb)) fail(`${environment} web domains ${custom(resources.web)}`);
    if (!isDeepStrictEqual(custom(resources.api), wantApi)) fail(`${environment} api domains ${custom(resources.api)}`);
    if (custom(resources.jobs).length || custom(resources.Postgres).length) fail(`${environment} jobs or Postgres has a domain`);
    for (const r of [resources.web, resources.api]) {
      for (const [host, target] of Object.entries(r?.networking?.customDomains ?? {})) {
        if (target?.port !== 8080) fail(`${host} targets port ${target?.port}, not 8080`);
      }
    }
    const usage = Object.keys(resources["postgres-volume"]?.config?.alerts?.usage ?? {}).sort();
    if (!isDeepStrictEqual(usage, ["100", "80", "95"])) fail(`${environment} volume alerts ${usage}`);
  }
  const { staging, production } = compiled;
  if (!isDeepStrictEqual(Object.keys(staging).sort(), Object.keys(production).sort())) {
    fail("the two environments name different resources");
  }
  for (const name of ["api", "web", "jobs"]) {
    for (const part of ["build", "deploy"]) {
      if (!isDeepStrictEqual(staging[name][part], production[name][part])) fail(`${name} ${part} differs`);
    }
    const names = (r) => Object.keys(r.variables ?? {}).sort();
    if (!isDeepStrictEqual(names(staging[name]), names(production[name]))) fail(`${name} variable names differ`);
  }
}

await ({ c9, c10 }[which] ?? (() => fail("unknown check")))();
console.log(`PASS ${which}`);
