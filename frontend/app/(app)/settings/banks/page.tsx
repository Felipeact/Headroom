import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { BankConnections } from "@/components/settings/bank-connections"
import { BankSettingsError } from "@/components/settings/bank-settings-error"
import {
  createFlinksConnectUrl,
  createLinkToken,
  createUpdateLinkToken,
  loadConnections,
} from "@/lib/api/bank"
import { loadBusinesses } from "@/lib/api/businesses"

const NEEDS_ATTENTION = new Set(["login_required", "sync_failing"])

// Settings > Bank connections (spec 17), from design/mockups/settings-banks.dc.html.
export default async function BankSettingsPage() {
  await auth.protect()
  const businesses = await loadBusinesses()
  const business = businesses?.[0]
  const connections = business?.role === "owner" ? await loadConnections(business.id) : null
  if (!business) return <BankSettingsError />
  // Banks are the owner's (spec 31): the API refuses a bookkeeper, so don't ask it.
  if (business.role !== "owner") redirect("/settings/email")
  if (!connections) return <BankSettingsError />

  // Link tokens last four hours and cost nothing: one to connect another bank, and one in
  // update mode for each Plaid bank that needs the owner to log in again. A Flinks bank has no
  // update mode (spec 17a): the owner disconnects it and connects it again.
  const attention = connections.filter(
    (connection) => connection.provider === "plaid" && NEEDS_ATTENTION.has(connection.status),
  )
  const [linkToken, flinks, ...updates] = await Promise.all([
    createLinkToken(business.id),
    createFlinksConnectUrl(business.id),
    ...attention.map((connection) => createUpdateLinkToken(business.id, connection.id)),
  ])
  const updateTokens = Object.fromEntries(attention.map((connection, i) => [connection.id, updates[i]]))

  return (
    <BankConnections
      businessId={business.id}
      timeZone={business.time_zone}
      now={new Date().toISOString()}
      connections={connections}
      linkToken={linkToken}
      flinks={flinks}
      updateTokens={updateTokens}
    />
  )
}
