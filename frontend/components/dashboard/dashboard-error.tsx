"use client"

import { CircleAlert } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

// The dashboard call failed (AC 29). "Try again" renders the page again from the API.
export function DashboardError() {
  const t = useTranslations("Dashboard.error")
  const router = useRouter()

  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3">
        <CircleAlert aria-hidden="true" className="size-7 text-danger-text" strokeWidth={1.6} />
        <h1 className="text-[17px] font-semibold sm:text-[19px]">{t("title")}</h1>
        <p className="text-sm leading-normal text-ink-2">{t("body")}</p>
        <Button variant="secondary" onClick={() => router.refresh()}>
          {t("retry")}
        </Button>
      </CardContent>
    </Card>
  )
}
