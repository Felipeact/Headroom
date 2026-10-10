import "server-only"
import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Alert = components["schemas"]["Alert"]

/**
 * One alert with its items and fixes (spec 27). "not_found" when the API answers 404 (unknown or
 * another business's alert) or 422 (a malformed id); null when the call fails.
 */
export async function loadAlert(businessId: string, alertId: string): Promise<Alert | "not_found" | null> {
  const path = "/v1/businesses/{business_id}/alerts/{alert_id}"
  try {
    const { data, response } = await api.GET(path, {
      params: { path: { business_id: businessId, alert_id: alertId } },
      headers: await authHeaders(),
    })
    if (data) return data
    if (response.status === 404 || response.status === 422) return "not_found"
    Sentry.captureMessage(`GET ${path} returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
