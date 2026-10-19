"use client"

import { useCallback } from "react"
import { TriangleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { repairConnection } from "@/app/(app)/settings/banks/actions"
import { FASTLINK_CONTAINER_ID, useYodleeConnect } from "@/components/onboarding/use-yodlee-connect"
import { Button } from "@/components/ui/button"

// The warning on a Yodlee bank that needs attention (spec 17b). "Reconnect" opens FastLink in
// edit mode for that bank; the repair sync then proves the login works, as for Plaid (spec 17).
export function YodleeReconnectBanner({
  businessId,
  connectionId,
  bank,
  reason,
}: {
  businessId: string
  connectionId: string
  bank: string
  reason: "login" | "failing"
}) {
  const t = useTranslations("Settings.Banks")
  const onLinked = useCallback(async () => {
    const result = await repairConnection(businessId, connectionId)
    return result.error === null ? null : ("connectFailed" as const)
  }, [businessId, connectionId])
  const { open, attachContainer, pending, active, error } = useYodleeConnect(businessId, onLinked, connectionId)

  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-[10px] border border-warning-border bg-warning-bg px-4 py-3"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1.5">
          <p className="flex items-start gap-2.5 text-sm leading-[1.45] text-warning-text">
            <TriangleAlert aria-hidden="true" className="mt-px size-5 shrink-0" strokeWidth={1.8} />
            <span data-user-content>{t(reason === "login" ? "loginBanner" : "syncFailingBanner", { bank })}</span>
          </p>
          {error && (
            <p data-user-content className="text-sm text-danger-text">
              {t("errors.reconnectFailed", { bank })}
            </p>
          )}
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={pending}
          aria-busy={pending}
          onClick={() => void open()}
          className="shrink-0"
        >
          {pending ? t("reconnecting") : t("reconnect")}
        </Button>
      </div>
      {active && <div id={FASTLINK_CONTAINER_ID} ref={attachContainer} className="min-h-[640px] w-full" />}
    </div>
  )
}
