"use client"

import { Button } from "@/components/ui/button"
import { throwServerError } from "./actions"

export function SentryCheckButtons({ runId }: { runId: string }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <Button
        variant="secondary"
        onClick={() => {
          throw new Error(`Headroom web Sentry check (client) ${runId}`.trim())
        }}
      >
        Throw a client error
      </Button>
      <Button variant="secondary" onClick={() => void throwServerError(runId)}>
        Throw a server error
      </Button>
    </div>
  )
}
