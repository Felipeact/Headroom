"use server"

import * as Sentry from "@sentry/nextjs"
import { revalidatePath } from "next/cache"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"

export type AcceptResult = {
  status: "accepted" | "expired" | "wrongAddress" | "alreadyOwner" | "notFound" | "failed"
}

/** Accept an invitation as the signed-in user (spec 31). The API matches their email address. */
export async function acceptInvitation(token: string): Promise<AcceptResult> {
  try {
    const { response } = await api.POST("/v1/invitations/{token}/accept", {
      params: { path: { token } },
      headers: await authHeaders(),
    })
    if (response.status === 200) {
      // The shell names the business and the settings sections from the user's businesses.
      revalidatePath("/", "layout")
      return { status: "accepted" }
    }
    if (response.status === 410) return { status: "expired" }
    if (response.status === 403) return { status: "wrongAddress" }
    if (response.status === 409) return { status: "alreadyOwner" }
    if (response.status === 404) return { status: "notFound" }
    Sentry.captureMessage(`POST /v1/invitations/{token}/accept returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { status: "failed" }
}
