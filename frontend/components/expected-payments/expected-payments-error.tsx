"use client"

import { CircleAlert } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

// The expected payments could not be loaded (spec 20); the API helper already told Sentry.
export function ExpectedPaymentsError() {
  const t = useTranslations()
  const router = useRouter()

  return (
    <>
      <h1 className="font-heading text-[30px] font-semibold tracking-[-0.02em] sm:text-[40px]">
        {t("ExpectedPayments.title")}
      </h1>
      <Card>
        <CardContent className="flex flex-col items-start gap-3">
          <CircleAlert aria-hidden="true" className="size-7 text-danger-text" strokeWidth={1.6} />
          <p className="text-[15px] leading-normal text-ink-2">{t("ExpectedPayments.loadFailed")}</p>
          <Button variant="secondary" onClick={() => router.refresh()}>
            {t("States.tryAgain")}
          </Button>
        </CardContent>
      </Card>
    </>
  )
}
