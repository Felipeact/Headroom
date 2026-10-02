"use client"

import { useEffect } from "react"
import * as Sentry from "@sentry/nextjs"
import NextError from "next/error"

// Replaces the root layout when it fails, so it renders its own document and cannot use
// next-intl. Shows Next's generic error page and reports the error.
export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <html lang="en">
      <body>
        {/* statusCode 0 is Sentry's documented value: App Router errors carry no status code. */}
        <NextError statusCode={0} />
      </body>
    </html>
  )
}
