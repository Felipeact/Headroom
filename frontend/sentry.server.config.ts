// Sentry in the Node.js runtime, loaded by instrumentation.ts.
import * as Sentry from "@sentry/nextjs"
import { sentryOptions } from "@/lib/sentry-options"

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  ...sentryOptions,
})
