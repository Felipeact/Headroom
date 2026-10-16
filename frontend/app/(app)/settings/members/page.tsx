import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { MembersSection } from "@/components/settings/members-section"
import { loadBusinesses } from "@/lib/api/businesses"
import { loadMembers } from "@/lib/api/members"

// Settings > Members (spec 31). Owners only: the API refuses a bookkeeper, and this sends them
// to the one settings section they have.
export default async function MembersSettingsPage() {
  await auth.protect()
  const businesses = await loadBusinesses()
  const business = businesses?.[0]
  // The (app) error state: "We couldn't load this page" with "Try again".
  if (!business) throw new Error("Business could not be loaded")
  if (business.role !== "owner") redirect("/settings/email")
  const members = await loadMembers(business.id)
  if (!members) throw new Error("Members could not be loaded")

  return <MembersSection businessId={business.id} members={members} />
}
