import { clerkMiddleware } from "@clerk/nextjs/server"

// Makes Clerk's auth() available server-side. Pages and layouts protect themselves with
// `await auth.protect()` (spec 10, AD-026); this file checks no paths.
export default clerkMiddleware()

export const config = {
  matcher: [
    // From Clerk's Next.js quickstart: skip Next internals and static files.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
  ],
}
