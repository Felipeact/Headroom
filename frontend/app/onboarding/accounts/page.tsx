import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"
import { ChooseAccounts } from "@/components/onboarding/choose-accounts"
import { StepIndicator } from "@/components/onboarding/step-indicator"
import { LayoutError } from "@/components/shell/layout-error"
import { createLinkToken, loadConnections } from "@/lib/api/bank"
import { loadBusinesses } from "@/lib/api/businesses"

export default async function AccountsStepPage() {
  await auth.protect()
  const businesses = await loadBusinesses()
  if (businesses && businesses.length === 0) redirect("/onboarding/business")
  const business = businesses?.[0]
  const connections = business ? await loadConnections(business.id) : null
  if (connections && connections.length === 0) redirect("/onboarding/bank")
  // For "Connect another bank"; link tokens last four hours and cost nothing.
  const linkToken = business && connections ? await createLinkToken(business.id) : null
  const t = await getTranslations()

  return (
    <>
      <header>
        <StepIndicator step={3} total={5}>
          <span className="font-heading text-xl font-semibold tracking-[-0.01em]">
            {t("Shell.wordmark")}
          </span>
        </StepIndicator>
      </header>
      {business && connections && linkToken ? (
        <ChooseAccounts businessId={business.id} linkToken={linkToken} connections={connections} />
      ) : (
        <LayoutError />
      )}
    </>
  )
}
