import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs/config";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {
  // Settings opens on its only built section (spec 17). Here rather than only in the page: a
  // redirect() in a page under the streaming (app) layout becomes a client-side redirect after
  // load, which interrupts whatever navigation comes next.
  async redirects() {
    return [{ source: "/settings", destination: "/settings/banks", permanent: false }];
  },
};

const withNextIntl = createNextIntlPlugin();

// Source maps upload only when SENTRY_AUTH_TOKEN, SENTRY_ORG and SENTRY_PROJECT are set.
export default withSentryConfig(withNextIntl(nextConfig), {
  silent: !process.env.CI,
  widenClientFileUpload: true,
  telemetry: false,
});
