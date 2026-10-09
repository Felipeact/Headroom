"use server"

import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"

export type SaveMinimumBalanceResult = { error: "saveFailed" | null }

// Onboarding step 4 (spec 23): store the minimum balance. The API checks the caller owns
// `businessId` and the amount's bounds; this action only forwards them.
export async function saveMinimumBalance(
  businessId: string,
  amountCents: number,
): Promise<SaveMinimumBalanceResult> {
  try {
    const { response } = await api.PUT("/v1/businesses/{business_id}/minimum-balance", {
      params: { path: { business_id: businessId } },
      body: { amount_cents: amountCents },
      headers: await authHeaders(),
    })
    if (response.status === 200) return { error: null }
    Sentry.captureMessage(`PUT /v1/businesses/{business_id}/minimum-balance returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { error: "saveFailed" }
}
