import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs/config";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {
  /* config options here */
};

const withNextIntl = createNextIntlPlugin();

// Source maps upload only when SENTRY_AUTH_TOKEN, SENTRY_ORG and SENTRY_PROJECT are set.
export default withSentryConfig(withNextIntl(nextConfig), {
  silent: !process.env.CI,
  widenClientFileUpload: true,
  telemetry: false,
});
