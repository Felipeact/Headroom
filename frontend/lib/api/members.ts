import "server-only"
import * as Sentry from "@sentry/nextjs"
import { authHeaders } from "@/lib/api/auth"
import { api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type MemberList = components["schemas"]["MemberList"]
export type BusinessMember = components["schemas"]["BusinessMember"]
export type InvitationPreview = components["schemas"]["InvitationPreview"]

/** A business's members and pending invitations (spec 31), or null when the API call fails. */
export async function loadMembers(businessId: string): Promise<MemberList | null> {
  try {
    const { data, response } = await api.GET("/v1/businesses/{business_id}/members", {
      params: { path: { business_id: businessId } },
      headers: await authHeaders(),
    })
    if (data) return data
    Sentry.captureMessage(`GET /v1/businesses/{business_id}/members returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}

/** What an invitation link points at: the invitation, `not_found` for an unknown token, or `error`. */
export async function loadInvitation(
  token: string,
): Promise<{ status: "found"; invitation: InvitationPreview } | { status: "not_found" | "error" }> {
  try {
    const { data, response } = await api.GET("/v1/invitations/{token}", {
      params: { path: { token } },
      headers: await authHeaders(),
    })
    if (data) return { status: "found", invitation: data }
    if (response.status === 404) return { status: "not_found" }
    Sentry.captureMessage(`GET /v1/invitations/{token} returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return { status: "error" }
}

/** The signed-in user's own ID, to find their row among a business's members, or null. */
export async function loadMyUserId(): Promise<string | null> {
  try {
    const { data, response } = await api.GET("/v1/me", { headers: await authHeaders() })
    if (data) return data.id
    Sentry.captureMessage(`GET /v1/me returned ${response.status}`)
  } catch (error) {
    Sentry.captureException(error)
  }
  return null
}
