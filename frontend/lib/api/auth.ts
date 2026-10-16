import "server-only"
import { auth } from "@clerk/nextjs/server"

// Clerk session tokens live 60 seconds. One with less left than this can expire while a slow
// render is still on its way to the API, so a fresh one is minted instead.
const MIN_SECONDS_LEFT = 10
const FRESH_TOKEN_SECONDS = 60

// Infinity when the expiry cannot be read: such a token is sent as is, and the API decides.
function secondsLeft(token: string): number {
  try {
    const payload = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString())
    return typeof payload.exp === "number" ? payload.exp - Date.now() / 1000 : Infinity
  } catch {
    return Infinity
  }
}

/**
 * The header that carries the signed-in user's Clerk session token to the API (spec 10).
 * Pass it on each call: `api.GET("/v1/me", { headers: await authHeaders() })`. The token is
 * never cached, stored or logged here.
 */
export async function authHeaders(): Promise<{ Authorization: string }> {
  const session = await auth()
  let token = await session.getToken()
  if (token && secondsLeft(token) < MIN_SECONDS_LEFT) {
    token = await session.getToken({ expiresInSeconds: FRESH_TOKEN_SECONDS })
  }
  if (!token) throw new Error("No Clerk session token")
  return { Authorization: `Bearer ${token}` }
}
