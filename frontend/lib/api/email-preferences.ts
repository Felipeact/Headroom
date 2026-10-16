import "server-only"
import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type EmailPreferences = components["schemas"]["EmailPreferences"]

/** The signed-in person's email choices (spec 28), or null when the API call fails. */
export async function loadEmailPreferences(): Promise<EmailPreferences | null> {
  try {
    const { data, response } = await api.GET("/v1/me/email-preferences", {
      headers: await authHeaders(),
    })
    if (data) return data
    Sentry.captureMessage(`GET /v1/me/email-preferences returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
