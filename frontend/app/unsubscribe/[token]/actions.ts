"use server"

import * as Sentry from "@sentry/nextjs"
import { api } from "@/lib/api/client"

export type UnsubscribeResult = { status: "unsubscribed" | "invalid" | "error" }

/**
 * Turn off every Headroom email for the link's token (spec 28). Public by design (door 4):
 * no session is sent, because the person may not be signed in on this device.
 */
export async function unsubscribe(token: string): Promise<UnsubscribeResult> {
  try {
    const { response } = await api.POST("/v1/unsubscribe/{token}", {
      params: { path: { token } },
    })
    if (response.status === 200) return { status: "unsubscribed" }
    if (response.status === 404) return { status: "invalid" }
    Sentry.captureMessage(`POST /v1/unsubscribe/{token} returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { status: "error" }
}
