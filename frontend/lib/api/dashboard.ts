import "server-only"
import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Dashboard = components["schemas"]["Dashboard"]

/** Everything the dashboard shows, in one call (spec 26), or null when the API call fails. */
export async function loadDashboard(businessId: string): Promise<Dashboard | null> {
  try {
    const { data, response } = await api.GET("/v1/businesses/{business_id}/dashboard", {
      params: { path: { business_id: businessId } },
      headers: await authHeaders(),
    })
    if (data) return data
    Sentry.captureMessage(`GET /v1/businesses/{business_id}/dashboard returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
