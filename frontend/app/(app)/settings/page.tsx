import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"

// Bank connections is the only settings section with a screen so far (spec 17). next.config.ts
// redirects /settings before this renders; this is the fallback.
export default async function SettingsPage() {
  await auth.protect()
  redirect("/settings/banks")
}
