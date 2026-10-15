// Spec 33 S2: the web app sends its security headers (C12, C13).
import { describe, expect, it } from "vitest";

import nextConfig from "../next.config";

async function sent(): Promise<Record<string, string>> {
  const rules = await nextConfig.headers?.();
  expect(rules).toBeDefined();
  const rule = rules?.find((entry) => entry.source === "/:path*");
  expect(rule).toBeDefined();
  return Object.fromEntries((rule?.headers ?? []).map(({ key, value }) => [key, value]));
}

describe("security headers", () => {
  it("config sends the enforced headers", async () => {
    const headers = await sent();

    expect(headers["Strict-Transport-Security"]).toBe("max-age=31536000; includeSubDomains");
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["Permissions-Policy"]).toBe("camera=(), microphone=(), geolocation=()");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Content-Security-Policy-Report-Only"]).toBeTruthy();
  });

  it("csp is report only", async () => {
    const headers = await sent();

    expect(headers["Content-Security-Policy-Report-Only"]).toContain("frame-ancestors 'none'");
    expect(headers["Content-Security-Policy-Report-Only"]).toContain("default-src 'self'");
    expect(Object.keys(headers)).not.toContain("Content-Security-Policy");
  });
});
