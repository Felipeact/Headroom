"use client"

import { useRouter } from "next/navigation"
import { CircleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

// The (app)/error.tsx state, for errors in the (app) layout itself, which that boundary
// sits inside and cannot catch.
export function LayoutError() {
  const t = useTranslations("States")
  const router = useRouter()

  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3">
        <CircleAlert aria-hidden="true" className="size-7 text-danger-text" strokeWidth={1.6} />
        <h1 className="text-[17px] font-semibold sm:text-[19px]">{t("errorTitle")}</h1>
        <p className="text-sm leading-normal text-ink-2">{t("errorBody")}</p>
        <Button variant="secondary" onClick={() => router.refresh()}>
          {t("tryAgain")}
        </Button>
      </CardContent>
    </Card>
  )
}
