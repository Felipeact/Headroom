"use client"

import { useEffect } from "react"
import * as Sentry from "@sentry/nextjs"
import { CircleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

export default function ErrorState({
  error,
  retry,
}: {
  error: Error & { digest?: string }
  retry: () => void
}) {
  const t = useTranslations("States")

  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3">
        <CircleAlert aria-hidden="true" className="size-7 text-danger-text" strokeWidth={1.6} />
        <h1 className="text-[17px] font-semibold sm:text-[19px]">{t("errorTitle")}</h1>
        <p className="text-sm leading-normal text-ink-2">{t("errorBody")}</p>
        <Button variant="secondary" onClick={() => retry()}>
          {t("tryAgain")}
        </Button>
      </CardContent>
    </Card>
  )
}
