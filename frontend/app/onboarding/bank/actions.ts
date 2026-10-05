"use server"

import * as Sentry from "@sentry/nextjs"
import { redirect } from "next/navigation"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"

export type ConnectBankError = "alreadyConnected" | "connectFailed"
export type ConnectBankResult = { error: ConnectBankError }

// Onboarding step 3 (spec 12): store the bank Plaid Link just connected, then choose which
// accounts count as cash (spec 13). The choose-accounts step calls this too, to connect another
// bank, and the redirect re-renders it. The API checks that the caller owns `businessId`; this
// action only forwards it.
export async function connectBank(businessId: string, publicToken: string): Promise<ConnectBankResult> {
  let status: number
  try {
    const { response } = await api.POST("/v1/businesses/{business_id}/bank/connections", {
      params: { path: { business_id: businessId } },
      body: { public_token: publicToken },
      headers: await authHeaders(),
    })
    status = response.status
  } catch (error) {
    Sentry.captureException(error)
    return { error: "connectFailed" }
  }

  if (status === 201) redirect("/onboarding/accounts")
  if (status === 409) return { error: "alreadyConnected" }
  Sentry.captureMessage(`POST /v1/businesses/{business_id}/bank/connections returned ${status}`)
  return { error: "connectFailed" }
}
