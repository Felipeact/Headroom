import "server-only"
import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"

/**
 * A Plaid Link token for the business (spec 12), or null when the API call fails. Link tokens
 * last four hours and cost nothing, so the step 3 page asks for one on every render.
 */
export async function createLinkToken(businessId: string): Promise<string | null> {
  try {
    const { data, response } = await api.POST("/v1/businesses/{business_id}/bank/link-token", {
      params: { path: { business_id: businessId } },
      headers: await authHeaders(),
    })
    if (data) return data.link_token
    Sentry.captureMessage(`POST /v1/businesses/{business_id}/bank/link-token returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
