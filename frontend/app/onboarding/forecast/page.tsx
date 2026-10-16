import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"
import { ForecastProgress } from "@/components/onboarding/forecast-progress"
import { StepIndicator } from "@/components/onboarding/step-indicator"
import { LayoutError } from "@/components/shell/layout-error"
import { loadConnections } from "@/lib/api/bank"
import { loadBusinesses } from "@/lib/api/businesses"
import { loadForecastStatus, loadMinimumBalance } from "@/lib/api/forecast"

export default async function ForecastStepPage() {
  await auth.protect()
  const businesses = await loadBusinesses()
  if (businesses && businesses.length === 0) redirect("/onboarding/business")
  const business = businesses?.[0]
  const connections = business ? await loadConnections(business.id) : null
  if (connections && connections.length === 0) redirect("/onboarding/bank")
  const minimum = business && connections ? await loadMinimumBalance(business.id) : null
  if (minimum && minimum.amount_cents == null) redirect("/onboarding/minimum-balance")
  const status = business && minimum ? await loadForecastStatus(business.id) : null
  const t = await getTranslations()

  return (
    <>
      <header>
        <StepIndicator step={5} total={5}>
          <span className="font-heading text-xl font-semibold tracking-[-0.01em]">
            {t("Shell.wordmark")}
          </span>
        </StepIndicator>
      </header>
      {status ? <ForecastProgress status={status} /> : <LayoutError />}
    </>
  )
}
