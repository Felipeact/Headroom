import { DashboardError } from "@/components/dashboard/dashboard-error"
import { DashboardView } from "@/components/dashboard/dashboard-view"
import { createUpdateLinkToken } from "@/lib/api/bank"
import { loadBusinesses } from "@/lib/api/businesses"
import { loadDashboard } from "@/lib/api/dashboard"

// The dashboard's data (spec 26): one API call, plus an update-mode Link token for each bank that
// asked the owner to log in again, so its banner can reconnect in place (AC 30).
export async function DashboardContent() {
  const businesses = await loadBusinesses()
  const business = businesses?.[0]
  const dashboard = business ? await loadDashboard(business.id) : null
  if (!business || !dashboard) return <DashboardError />

  const included = new Set(dashboard.accounts.filter((a) => a.included).map((a) => a.connection_id))
  const attention = dashboard.connections.filter((c) => c.status === "login_required" && included.has(c.id))
  const tokens = await Promise.all(attention.map((c) => createUpdateLinkToken(business.id, c.id)))

  return (
    <DashboardView
      businessId={business.id}
      timeZone={business.time_zone}
      now={new Date().toISOString()}
      dashboard={dashboard}
      attention={attention.map((c, i) => ({ connectionId: c.id, bank: c.institution_name, updateToken: tokens[i] }))}
    />
  )
}
