"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { dismissAlert } from "@/app/(app)/actions"
import { Button } from "@/components/ui/button"

// "Dismiss alert" (AC 15-18): on success, back to the dashboard, which no longer lists it.
export function DismissAlert({ businessId, alertId }: { businessId: string; alertId: string }) {
  const t = useTranslations("AlertPage")
  const tAlert = useTranslations("Dashboard.alert")
  const router = useRouter()
  const [failed, setFailed] = useState(false)
  const [pending, startDismiss] = useTransition()

  function dismiss() {
    setFailed(false)
    startDismiss(async () => {
      const result = await dismissAlert(businessId, alertId)
      if (result.error) {
        setFailed(true)
        return
      }
      toast(tAlert("dismissed"))
      router.push("/")
    })
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        variant="secondary"
        className="min-h-12 w-full"
        disabled={pending}
        aria-busy={pending}
        onClick={dismiss}
      >
        {pending ? tAlert("dismissing") : t("dismiss")}
      </Button>
      <p className="text-center text-[13px] leading-[1.45] text-ink-3">{t("dismissNote")}</p>
      {failed && (
        <p role="alert" className="text-center text-sm text-danger-text">
          {tAlert("dismissFailed")}
        </p>
      )}
    </div>
  )
}
