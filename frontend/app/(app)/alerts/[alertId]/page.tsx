import { auth } from "@clerk/nextjs/server"
import { notFound } from "next/navigation"
import { AlertView } from "@/components/alert-page/alert-view"
import { loadAlert } from "@/lib/api/alerts"
import { loadBusinesses } from "@/lib/api/businesses"
import { capture } from "@/lib/analytics"

// One cash gap alert in full (spec 27). A failed load throws to `(app)/error.tsx`; an unknown,
// foreign or malformed id is the not-found state.
export default async function AlertPage({ params }: PageProps<"/alerts/[alertId]">) {
  await auth.protect()
  const { alertId } = await params
  const business = (await loadBusinesses())?.[0]
  if (!business) throw new Error("Could not load the business")
  const alert = await loadAlert(business.id, alertId)
  if (alert === "not_found") notFound()
  if (!alert) throw new Error("Could not load the alert")
  await capture("alert_opened", { business_id: business.id, alert_id: alertId, role: business.role })
  return <AlertView businessId={business.id} timeZone={business.time_zone} alert={alert} />
}
