"use server"

import * as Sentry from "@sentry/nextjs"
import { redirect } from "next/navigation"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import { capture } from "@/lib/analytics"

export type ConnectBankError = "alreadyConnected" | "connectFailed"
export type ConnectBankResult = { error: ConnectBankError }
// Flinks can also be still preparing the accounts (spec 17a).
export type ConnectFlinksError = ConnectBankError | "stillPreparing"
export type ConnectFlinksResult = { error: ConnectFlinksError }
// Where a connected bank leads: onboarding's choose-accounts step, or back to bank settings
// (spec 17). A closed list, because a server action's arguments come from the browser.
export type ConnectBankReturn = "/onboarding/accounts" | "/settings/banks"
const RETURNS: readonly ConnectBankReturn[] = ["/onboarding/accounts", "/settings/banks"]
// A Flinks loginId is a UUID (spec 17a); anything else from the browser is not sent on.
const LOGIN_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

type ConnectBody = { provider: "plaid"; public_token: string } | { provider: "flinks"; login_id: string }

async function connect(
  businessId: string,
  body: ConnectBody,
  returnTo: ConnectBankReturn,
): Promise<ConnectFlinksResult> {
  let status: number
  try {
    const { response } = await api.POST("/v1/businesses/{business_id}/bank/connections", {
      params: { path: { business_id: businessId } },
      body,
      headers: await authHeaders(),
    })
    status = response.status
  } catch (error) {
    Sentry.captureException(error)
    return { error: "connectFailed" }
  }

  if (status === 201) {
    await capture("bank_connected", { business_id: businessId })
    redirect(RETURNS.includes(returnTo) ? returnTo : "/onboarding/accounts")
  }
  if (status === 409) return { error: "alreadyConnected" }
  // Flinks still preparing the accounts, or briefly unavailable: the same login can retry.
  if (status === 503) return { error: "stillPreparing" }
  Sentry.captureMessage(`POST /v1/businesses/{business_id}/bank/connections returned ${status}`)
  return { error: "connectFailed" }
}

// Onboarding step 3 (spec 12): store the bank Plaid Link just connected, then choose which
// accounts count as cash (spec 13). The choose-accounts step calls this too, to connect another
// bank, and the redirect re-renders it. The API checks that the caller owns `businessId`; this
// action only forwards it.
export async function connectBank(
  businessId: string,
  publicToken: string,
  returnTo: ConnectBankReturn = "/onboarding/accounts",
): Promise<ConnectBankResult> {
  const result = await connect(businessId, { provider: "plaid", public_token: publicToken }, returnTo)
  // Only Flinks answers 503 (spec 17a); for Plaid it is just a failed connect.
  return { error: result.error === "stillPreparing" ? "connectFailed" : result.error }
}

// The same, for the loginId Flinks Connect returned (spec 17a).
export async function connectFlinksBank(
  businessId: string,
  loginId: string,
  returnTo: ConnectBankReturn = "/onboarding/accounts",
): Promise<ConnectFlinksResult> {
  if (!LOGIN_ID.test(loginId)) return { error: "connectFailed" }
  return connect(businessId, { provider: "flinks", login_id: loginId }, returnTo)
}
