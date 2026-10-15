"use server"

import * as Sentry from "@sentry/nextjs"
import { revalidatePath } from "next/cache"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"

const PAGE = "/settings/members"

export type InviteError = "alreadyMember" | "alreadyInvited" | "invalid" | "notSent" | "failed"

// Members (spec 31). Each action forwards the IDs; the API checks that the caller owns the
// business. On success the page re-renders from the API.

/** Invite a bookkeeper by email. */
export async function inviteBookkeeper(businessId: string, email: string): Promise<{ error: InviteError | null }> {
  try {
    const { error, response } = await api.POST("/v1/businesses/{business_id}/invitations", {
      params: { path: { business_id: businessId } },
      body: { email },
      headers: await authHeaders(),
    })
    if (response.status === 201) {
      revalidatePath(PAGE)
      return { error: null }
    }
    if (response.status === 422) return { error: "invalid" }
    if (response.status === 503) return { error: "notSent" }
    if (response.status === 409) {
      // The two conflicts differ only in the problem's detail text.
      const detail = (error as { detail?: string } | undefined)?.detail ?? ""
      return { error: detail.includes("pending") ? "alreadyInvited" : "alreadyMember" }
    }
    Sentry.captureMessage(`POST /v1/businesses/{business_id}/invitations returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { error: "failed" }
}

/** Remove a bookkeeper from the business. */
export async function removeMember(businessId: string, userId: string): Promise<{ error: "removeFailed" | null }> {
  try {
    const { response } = await api.DELETE("/v1/businesses/{business_id}/members/{user_id}", {
      params: { path: { business_id: businessId, user_id: userId } },
      headers: await authHeaders(),
    })
    if (response.status === 204) {
      revalidatePath(PAGE)
      return { error: null }
    }
    Sentry.captureMessage(`DELETE /v1/businesses/{business_id}/members/{user_id} returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { error: "removeFailed" }
}
