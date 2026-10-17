import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"
import { ConnectBank } from "@/components/onboarding/connect-bank"
import { StepIndicator } from "@/components/onboarding/step-indicator"
import { LayoutError } from "@/components/shell/layout-error"
import { createFlinksConnectUrl, createLinkToken } from "@/lib/api/bank"
import { loadBusinesses } from "@/lib/api/businesses"

export default async function BankStepPage() {
  await auth.protect()
  const businesses = await loadBusinesses()
  if (businesses && businesses.length === 0) redirect("/onboarding/business")
  const business = businesses?.[0]
  // Flinks (spec 17a) is offered only when the API has it; null keeps Plaid alone.
  const [linkToken, flinks] = business
    ? await Promise.all([createLinkToken(business.id), createFlinksConnectUrl(business.id)])
    : [null, null]
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
      {business && linkToken ? (
        <ConnectBank businessId={business.id} linkToken={linkToken} flinks={flinks} />
      ) : (
        <LayoutError />
      )}
    </>
  )
}
