import "server-only"
import * as Sentry from "@sentry/nextjs"
import type { components } from "@/lib/api/schema"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"

export type Business = components["schemas"]["Business"]

/**
 * The signed-in user's businesses, oldest membership first (AD-033), or null when the API
 * call fails. The first verified call also creates the user's row (spec 10).
 */
export async function loadBusinesses(): Promise<Business[] | null> {
  try {
    const { data, response } = await api.GET("/v1/businesses", { headers: await authHeaders() })
    if (data) return data.items
    Sentry.captureMessage(`GET /v1/businesses returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
