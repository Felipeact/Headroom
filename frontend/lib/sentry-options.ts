// Options shared by every Sentry.init (browser, Node.js and edge). Error monitoring only: no
// tracing, Session Replay or logs (plan door 4). The screens show bank data, so nothing about
// the user or the request is collected; Sentry 11 collects all of it unless told not to.
import type { init } from "@sentry/nextjs"

type SharedOptions = Pick<NonNullable<Parameters<typeof init>[0]>, "environment" | "dataCollection">

export const sentryOptions: SharedOptions = {
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
  dataCollection: {
    userInfo: false,
    cookies: false,
    httpHeaders: false,
    httpBodies: [],
    urlQueryParams: false,
    stackFrameVariables: false,
  },
}
