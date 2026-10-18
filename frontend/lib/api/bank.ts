import "server-only"
import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

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

export type Connection = components["schemas"]["Connection"]

/** The business's bank connections with their accounts (spec 13), or null when the API call fails. */
export async function loadConnections(businessId: string): Promise<Connection[] | null> {
  try {
    const { data, response } = await api.GET("/v1/businesses/{business_id}/bank/connections", {
      params: { path: { business_id: businessId } },
      headers: await authHeaders(),
    })
    if (data) return data.items
    Sentry.captureMessage(`GET /v1/businesses/{business_id}/bank/connections returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}

/**
 * A Plaid Link token in update mode for one connection (spec 17), to repair its bank login, or
 * null when the API call fails.
 */
export async function createUpdateLinkToken(businessId: string, connectionId: string): Promise<string | null> {
  try {
    const { data, response } = await api.POST(
      "/v1/businesses/{business_id}/bank/connections/{connection_id}/link-token",
      {
        params: { path: { business_id: businessId, connection_id: connectionId } },
        headers: await authHeaders(),
      },
    )
    if (data) return data.link_token
    Sentry.captureMessage(
      `POST /v1/businesses/{business_id}/bank/connections/{connection_id}/link-token returned ${response.status}`,
    )
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}

export type FlinksConnect = components["schemas"]["FlinksConnectUrl"]

/**
 * The Flinks Connect iframe for the business (spec 17a), or null when Flinks is off (`404`) or
 * the call fails. Its authorize token is single-use, so every render asks for a new one.
 */
export async function createFlinksConnectUrl(businessId: string): Promise<FlinksConnect | null> {
  try {
    const { data, response } = await api.POST("/v1/businesses/{business_id}/bank/flinks/connect-url", {
      params: { path: { business_id: businessId } },
      headers: await authHeaders(),
    })
    if (data) return data
    // 404: Flinks isn't configured here, which is not a failure.
    if (response.status !== 404) {
      Sentry.captureException(
        new Error(`POST /v1/businesses/{business_id}/bank/flinks/connect-url returned ${response.status}`),
      )
    }
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
