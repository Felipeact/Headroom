import { Suspense } from "react"
import { auth } from "@clerk/nextjs/server"
import { DashboardContent } from "@/components/dashboard/dashboard-content"
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton"

// The dashboard (spec 26): skeletons first, then everything from one API call.
export default async function DashboardPage() {
  await auth.protect()
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <DashboardContent />
    </Suspense>
  )
}
