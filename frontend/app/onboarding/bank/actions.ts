"use server"

import * as Sentry from "@sentry/nextjs"
import { redirect } from "next/navigation"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import { capture } from "@/lib/analytics"
import type { components } from "@/lib/api/schema"

export type ConnectBankError = "alreadyConnected" | "connectFailed"
export type ConnectBankResult = { error: ConnectBankError }
// Where a connected bank leads: onboarding's choose-accounts step, or back to bank settings
// (spec 17). A closed list, because a server action's arguments come from the browser.
export type ConnectBankReturn = "/onboarding/accounts" | "/settings/banks"
const RETURNS: readonly ConnectBankReturn[] = ["/onboarding/accounts", "/settings/banks"]

// Onboarding step 3 (spec 12): store the bank Plaid Link just connected, then choose which
// accounts count as cash (spec 13). The choose-accounts step calls this too, to connect another
// bank, and the redirect re-renders it. The API checks that the caller owns `businessId`; this
// action only forwards it.
export async function connectBank(
  businessId: string,
  publicToken: string,
  returnTo: ConnectBankReturn = "/onboarding/accounts",
): Promise<ConnectBankResult> {
  let status: number
  try {
    const { response } = await api.POST("/v1/businesses/{business_id}/bank/connections", {
      params: { path: { business_id: businessId } },
      body: { provider: "plaid", public_token: publicToken },
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
  Sentry.captureMessage(`POST /v1/businesses/{business_id}/bank/connections returned ${status}`)
  return { error: "connectFailed" }
}

export type FastLinkLaunch = components["schemas"]["FastLink"]
export type FastLinkResult = { launch: FastLinkLaunch } | { error: "launchFailed" }

// Spec 17b: what Yodlee's FastLink needs to open for this business (or, with `connectionId`, to
// reconnect that Yodlee bank). FastLink runs in the browser and calls Yodlee itself, so a short-
// lived Yodlee token for the business's own user has to reach it; the API never returns a secret.
export async function launchFastLink(businessId: string, connectionId?: string): Promise<FastLinkResult> {
  try {
    const { data, response } = await api.POST("/v1/businesses/{business_id}/bank/yodlee/fastlink", {
      params: { path: { business_id: businessId } },
      body: connectionId ? { connection_id: connectionId } : {},
      headers: await authHeaders(),
    })
    if (data) return { launch: data }
    Sentry.captureMessage(`POST /v1/businesses/{business_id}/bank/yodlee/fastlink returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { error: "launchFailed" }
}

// Spec 17b: store the bank FastLink just linked, like `connectBank` does for Plaid Link.
export async function connectYodleeBank(
  businessId: string,
  providerAccountId: string,
  returnTo: ConnectBankReturn = "/onboarding/accounts",
): Promise<ConnectBankResult> {
  let status: number
  try {
    const { response } = await api.POST("/v1/businesses/{business_id}/bank/connections", {
      params: { path: { business_id: businessId } },
      body: { provider: "yodlee", provider_account_id: providerAccountId },
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
  Sentry.captureMessage(`POST /v1/businesses/{business_id}/bank/connections returned ${status}`)
  return { error: "connectFailed" }
}
