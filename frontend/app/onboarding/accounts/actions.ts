"use server"

import * as Sentry from "@sentry/nextjs"
import { revalidatePath } from "next/cache"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type AccountChange = components["schemas"]["AccountUpdate"]
export type UpdateAccountResult = { error: "saveFailed" | null }

// Onboarding step 3, choose accounts (spec 13): include or exclude an account as cash, or make
// it primary. On success the page re-renders from the API. The API checks the caller owns
// `businessId` and that the account is theirs; this action only forwards them.
export async function updateAccount(
  businessId: string,
  accountId: string,
  change: AccountChange,
): Promise<UpdateAccountResult> {
  try {
    const { response } = await api.PATCH("/v1/businesses/{business_id}/bank/accounts/{account_id}", {
      params: { path: { business_id: businessId, account_id: accountId } },
      body: change,
      headers: await authHeaders(),
    })
    if (response.status === 200) {
      revalidatePath("/onboarding/accounts")
      return { error: null }
    }
    Sentry.captureMessage(`PATCH /v1/businesses/{business_id}/bank/accounts/{account_id} returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { error: "saveFailed" }
}
