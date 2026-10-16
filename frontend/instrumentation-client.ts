// Sentry in the browser. Starts only when NEXT_PUBLIC_SENTRY_DSN is set.
import * as Sentry from "@sentry/nextjs"
import { sentryOptions } from "@/lib/sentry-options"

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  ...sentryOptions,
})

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart
