"use client"

import { CircleAlert } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

// The bank connections could not be loaded (spec 17); the API helper already told Sentry.
export function BankSettingsError() {
  const t = useTranslations()
  const router = useRouter()

  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3">
        <CircleAlert aria-hidden="true" className="size-7 text-danger-text" strokeWidth={1.6} />
        <h2 className="text-[17px] font-semibold sm:text-[19px]">{t("Settings.Banks.title")}</h2>
        <p className="text-sm leading-normal text-ink-2">{t("Settings.Banks.errors.load")}</p>
        <Button variant="secondary" onClick={() => router.refresh()}>
          {t("States.tryAgain")}
        </Button>
      </CardContent>
    </Card>
  )
}
