import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"
import { BusinessForm } from "@/components/onboarding/business-form"
import { StepIndicator } from "@/components/onboarding/step-indicator"
import { LayoutError } from "@/components/shell/layout-error"
import { loadBusinesses } from "@/lib/api/businesses"

export default async function BusinessStepPage() {
  await auth.protect()
  const businesses = await loadBusinesses()
  if (businesses && businesses.length > 0) redirect("/")
  const t = await getTranslations()

  return (
    <>
      <header>
        <StepIndicator step={2} total={5}>
          <span className="font-heading text-xl font-semibold tracking-[-0.01em]">
            {t("Shell.wordmark")}
          </span>
        </StepIndicator>
      </header>
      {businesses ? (
        <>
          <div className="flex flex-col gap-2">
            <h1 className="font-heading text-[28px] leading-tight font-semibold tracking-[-0.02em]">
              {t("Onboarding.Business.title")}
            </h1>
            <p className="text-[15px] leading-normal text-ink-2">{t("Onboarding.Business.intro")}</p>
          </div>
          <BusinessForm />
        </>
      ) : (
        <LayoutError />
      )}
    </>
  )
}
