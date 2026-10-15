import { auth } from "@clerk/nextjs/server"
import type { NextRequest } from "next/server"
import { capture } from "@/lib/analytics"
import { safePath } from "@/lib/safe-path"

// Where Clerk sends a user who has just signed up (spec 32): the sign-up page points here. It
// records `sign_up_completed`, then goes on to where the user was headed.
export async function GET(request: NextRequest) {
  await auth.protect()
  await capture("sign_up_completed", {})
  const next = safePath(request.nextUrl.searchParams.get("next"))
  return Response.redirect(new URL(next, request.url), 307)
}
