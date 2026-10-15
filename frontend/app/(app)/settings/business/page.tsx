import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { SettingsPlaceholder } from "@/components/settings/settings-placeholder"
import { loadBusinesses } from "@/lib/api/businesses"

export default async function BusinessSettingsPage() {
  await auth.protect()
  // Business settings are the owner's (spec 31).
  const business = (await loadBusinesses())?.[0]
  if (business && business.role !== "owner") redirect("/settings/email")
  return <SettingsPlaceholder section="business" />
}
