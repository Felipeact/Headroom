"use client"

import { useCallback, useState, useTransition } from "react"
import { TriangleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { usePlaidLink, type PlaidLinkError } from "react-plaid-link"
import { repairConnection } from "@/app/(app)/settings/banks/actions"
import { Button } from "@/components/ui/button"

// The warning on a bank that needs attention (spec 17, DESIGN.md "Partial"). "Reconnect" opens
// Plaid Link in update mode; the owner logs in on the bank's own screen, and the repair sync
// then proves the login works. Link's public token is not needed in update mode.
export function ReconnectBanner({
  businessId,
  connectionId,
  bank,
  reason,
  updateToken,
}: {
  businessId: string
  connectionId: string
  bank: string
  reason: "login" | "failing"
  updateToken: string | null
}) {
  const t = useTranslations("Settings.Banks")
  const [failed, setFailed] = useState(false)
  const [pending, startRepair] = useTransition()

  const onSuccess = useCallback(() => {
    setFailed(false)
    startRepair(async () => {
      const result = await repairConnection(businessId, connectionId)
      setFailed(result.error !== null)
    })
  }, [businessId, connectionId])
  // Closing Link is not an error; Link reporting one is.
  const onExit = useCallback((linkError: PlaidLinkError | null) => {
    setFailed(linkError !== null)
  }, [])
  const { open, ready } = usePlaidLink({ token: updateToken, onSuccess, onExit })

  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-[10px] border border-warning-border bg-warning-bg px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex flex-col gap-1.5">
        <p className="flex items-start gap-2.5 text-sm leading-[1.45] text-warning-text">
          <TriangleAlert aria-hidden="true" className="mt-px size-5 shrink-0" strokeWidth={1.8} />
          <span data-user-content>{t(reason === "login" ? "loginBanner" : "syncFailingBanner", { bank })}</span>
        </p>
        {failed && <p data-user-content className="text-sm text-danger-text">{t("errors.reconnectFailed", { bank })}</p>}
      </div>
      <Button
        type="button"
        variant="outline"
        disabled={!updateToken || !ready || pending}
        aria-busy={pending}
        onClick={() => {
          setFailed(false)
          open()
        }}
        className="shrink-0"
      >
        {pending ? t("reconnecting") : t("reconnect")}
      </Button>
    </div>
  )
}
