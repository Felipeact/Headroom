"use server"

import * as Sentry from "@sentry/nextjs"
import { revalidatePath } from "next/cache"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import { capture } from "@/lib/analytics"

export type DismissResult = { error: null } | { error: "dismissFailed" }

/** Dismiss an open alert from the dashboard (spec 26 AC 18); the API checks the caller owns it. */
export async function dismissAlert(businessId: string, alertId: string): Promise<DismissResult> {
  const path = "/v1/businesses/{business_id}/alerts/{alert_id}/dismiss"
  try {
    const { response } = await api.POST(path, {
      params: { path: { business_id: businessId, alert_id: alertId } },
      headers: await authHeaders(),
    })
    if (response.status !== 200) {
      Sentry.captureMessage(`POST ${path} returned ${response.status}`)
      return { error: "dismissFailed" }
    }
  } catch (error) {
    Sentry.captureException(error)
    return { error: "dismissFailed" }
  }
  await capture("alert_dismissed", { business_id: businessId, alert_id: alertId })
  revalidatePath("/")
  return { error: null }
}
