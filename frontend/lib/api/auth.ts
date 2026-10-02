import "server-only"
import { auth } from "@clerk/nextjs/server"

/**
 * The header that carries the signed-in user's Clerk session token to the API (spec 10).
 * Pass it on each call: `api.GET("/v1/me", { headers: await authHeaders() })`. The token is
 * never cached, stored or logged here.
 */
export async function authHeaders(): Promise<{ Authorization: string }> {
  const token = await (await auth()).getToken()
  if (!token) throw new Error("No Clerk session token")
  return { Authorization: `Bearer ${token}` }
}
