import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"
import { MinimumBalanceForm } from "@/components/onboarding/minimum-balance-form"
import { StepIndicator } from "@/components/onboarding/step-indicator"
import { LayoutError } from "@/components/shell/layout-error"
import { loadConnections } from "@/lib/api/bank"
import { loadBusinesses } from "@/lib/api/businesses"
import { loadMinimumBalance } from "@/lib/api/forecast"

export default async function MinimumBalanceStepPage() {
  await auth.protect()
  const businesses = await loadBusinesses()
  if (businesses && businesses.length === 0) redirect("/onboarding/business")
  const business = businesses?.[0]
  const connections = business ? await loadConnections(business.id) : null
  if (connections && connections.length === 0) redirect("/onboarding/bank")
  const minimum = business && connections ? await loadMinimumBalance(business.id) : null
  const t = await getTranslations()

  return (
    <>
      <header>
        <StepIndicator step={4} total={5}>
          <span className="font-heading text-xl font-semibold tracking-[-0.01em]">
            {t("Shell.wordmark")}
          </span>
        </StepIndicator>
      </header>
      {business && minimum ? (
        <>
          <div className="flex flex-col gap-2">
            <h1 className="font-heading text-[28px] leading-tight font-semibold tracking-[-0.02em]">
              {t("Onboarding.Minimum.title")}
            </h1>
            <p className="text-[15px] leading-normal text-ink-2">{t("Onboarding.Minimum.intro")}</p>
          </div>
          <MinimumBalanceForm
            businessId={business.id}
            initialCents={minimum.amount_cents ?? null}
            suggestedCents={minimum.suggested_cents ?? null}
          />
        </>
      ) : (
        <LayoutError />
      )}
    </>
  )
}
