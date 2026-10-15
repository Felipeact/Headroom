"use server"

import * as Sentry from "@sentry/nextjs"
import { revalidatePath } from "next/cache"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { EmailPreferences } from "@/lib/api/email-preferences"

/** Save both email choices (spec 28). Never throws: a failure is `{ ok: false }`. */
export async function saveEmailPreferences(preferences: EmailPreferences): Promise<{ ok: boolean }> {
  try {
    const { response } = await api.PUT("/v1/me/email-preferences", {
      body: preferences,
      headers: await authHeaders(),
    })
    if (response.ok) {
      revalidatePath("/settings/email")
      return { ok: true }
    }
    Sentry.captureMessage(`PUT /v1/me/email-preferences returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { ok: false }
}

/** A bookkeeper's choice to get one client's alert emails (spec 31). Never throws. */
export async function setClientAlertEmails(businessId: string, enabled: boolean): Promise<{ ok: boolean }> {
  try {
    const { response } = await api.PUT("/v1/businesses/{business_id}/me/alert-emails", {
      params: { path: { business_id: businessId } },
      body: { enabled },
      headers: await authHeaders(),
    })
    if (response.ok) {
      revalidatePath("/settings/email")
      return { ok: true }
    }
    Sentry.captureMessage(`PUT /v1/businesses/{business_id}/me/alert-emails returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { ok: false }
}
