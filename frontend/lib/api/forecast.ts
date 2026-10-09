import "server-only"
import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type MinimumBalance = components["schemas"]["MinimumBalance"]
export type ForecastStatus = components["schemas"]["ForecastStatus"]

/** The business's minimum balance and the suggested one (spec 23), or null when the API call fails. */
export async function loadMinimumBalance(businessId: string): Promise<MinimumBalance | null> {
  try {
    const { data, response } = await api.GET("/v1/businesses/{business_id}/minimum-balance", {
      params: { path: { business_id: businessId } },
      headers: await authHeaders(),
    })
    if (data) return data
    Sentry.captureMessage(`GET /v1/businesses/{business_id}/minimum-balance returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}

/** How far the first forecast has got (spec 23), or null when the API call fails. */
export async function loadForecastStatus(businessId: string): Promise<ForecastStatus | null> {
  try {
    const { data, response } = await api.GET("/v1/businesses/{business_id}/forecast/status", {
      params: { path: { business_id: businessId } },
      headers: await authHeaders(),
    })
    if (data) return data
    Sentry.captureMessage(`GET /v1/businesses/{business_id}/forecast/status returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
