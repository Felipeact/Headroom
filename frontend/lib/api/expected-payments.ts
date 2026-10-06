import "server-only"
import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type ExpectedPayment = components["schemas"]["ExpectedPayment"]

/** The business's upcoming expected payments (spec 20), or null when the API call fails. */
export async function loadExpectedPayments(businessId: string): Promise<ExpectedPayment[] | null> {
  try {
    const { data, response } = await api.GET("/v1/businesses/{business_id}/expected-payments", {
      params: { path: { business_id: businessId } },
      headers: await authHeaders(),
    })
    if (data) return data.items
    Sentry.captureMessage(`GET /v1/businesses/{business_id}/expected-payments returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
