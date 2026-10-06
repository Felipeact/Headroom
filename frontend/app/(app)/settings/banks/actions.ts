"use server"

import * as Sentry from "@sentry/nextjs"
import { revalidatePath } from "next/cache"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type AccountChange = components["schemas"]["AccountUpdate"]

const PAGE = "/settings/banks"

// Bank settings (spec 17). Each action forwards the IDs; the API checks that the caller owns
// the business and that the account or connection is its own. On success the page re-renders
// from the API.

/** Include or exclude an account as cash, or make it primary. */
export async function updateBankAccount(
  businessId: string,
  accountId: string,
  change: AccountChange,
): Promise<{ error: "saveFailed" | null }> {
  try {
    const { response } = await api.PATCH("/v1/businesses/{business_id}/bank/accounts/{account_id}", {
      params: { path: { business_id: businessId, account_id: accountId } },
      body: change,
      headers: await authHeaders(),
    })
    if (response.status === 200) {
      revalidatePath(PAGE)
      return { error: null }
    }
    Sentry.captureMessage(`PATCH /v1/businesses/{business_id}/bank/accounts/{account_id} returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { error: "saveFailed" }
}

/** After Plaid Link's update mode: sync the connection, which proves the login works again. */
export async function repairConnection(
  businessId: string,
  connectionId: string,
): Promise<{ error: "reconnectFailed" | null }> {
  try {
    const { response } = await api.POST("/v1/businesses/{business_id}/bank/connections/{connection_id}/repair", {
      params: { path: { business_id: businessId, connection_id: connectionId } },
      headers: await authHeaders(),
    })
    if (response.status === 200) {
      revalidatePath(PAGE)
      return { error: null }
    }
    Sentry.captureMessage(
      `POST /v1/businesses/{business_id}/bank/connections/{connection_id}/repair returned ${response.status}`,
    )
  } catch (error) {
    Sentry.captureException(error)
  }
  return { error: "reconnectFailed" }
}

/** Remove the bank at Plaid, and its token and data from Headroom. */
export async function disconnectBank(
  businessId: string,
  connectionId: string,
): Promise<{ error: "disconnectFailed" | null }> {
  try {
    const { response } = await api.DELETE("/v1/businesses/{business_id}/bank/connections/{connection_id}", {
      params: { path: { business_id: businessId, connection_id: connectionId } },
      headers: await authHeaders(),
    })
    if (response.status === 204) {
      revalidatePath(PAGE)
      return { error: null }
    }
    Sentry.captureMessage(
      `DELETE /v1/businesses/{business_id}/bank/connections/{connection_id} returned ${response.status}`,
    )
  } catch (error) {
    Sentry.captureException(error)
  }
  return { error: "disconnectFailed" }
}
