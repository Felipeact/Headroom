"use client"

import { useState, useTransition } from "react"
import { CircleAlert, Landmark, Lock, Plus } from "lucide-react"
import { useTranslations } from "next-intl"
import { updateBankAccount, type AccountChange } from "@/app/(app)/settings/banks/actions"
import { useConnectBank } from "@/components/onboarding/use-connect-bank"
import { BankCard } from "@/components/settings/bank-card"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Toaster } from "@/components/ui/sonner"
import type { components } from "@/lib/api/schema"

type Connection = components["schemas"]["Connection"]

// Settings > Bank connections (spec 17), from design/mockups/settings-banks.dc.html. Every change
// saves at once; the page then re-renders from the API, so the controls show what it returned.
export function BankConnections({
  businessId,
  timeZone,
  now,
  connections,
  linkToken,
  updateTokens,
}: {
  businessId: string
  timeZone: string
  now: string
  connections: Connection[]
  linkToken: string | null
  updateTokens: Record<string, string | null>
}) {
  const t = useTranslations("Settings.Banks")
  const [saveFailed, setSaveFailed] = useState(false)
  const [saving, startSaving] = useTransition()
  const connect = useConnectBank(businessId, linkToken ?? "", "/settings/banks")
  const busy = saving || connect.pending

  function save(accountId: string, change: AccountChange) {
    setSaveFailed(false)
    connect.clearError()
    startSaving(async () => {
      const result = await updateBankAccount(businessId, accountId, change)
      setSaveFailed(result.error !== null)
    })
  }

  function connectBank() {
    setSaveFailed(false)
    connect.open()
  }

  const alert = saveFailed ? t("errors.saveFailed") : connect.error ? t(`errors.${connect.error}`) : null
  const connectLabel = connect.pending ? t("connecting") : null

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
        <div className="flex flex-col gap-1.5">
          <h2 className="text-[22px] font-semibold">{t("title")}</h2>
          <p className="text-[15px] text-ink-2">{t("intro")}</p>
        </div>
        {connections.length > 0 && (
          <Button
            type="button"
            variant="secondary"
            disabled={busy || !linkToken || !connect.ready}
            aria-busy={connect.pending}
            onClick={connectBank}
            className="shrink-0"
          >
            <Plus aria-hidden="true" className="size-[18px]" strokeWidth={2} />
            {connectLabel ?? t("connectAnother")}
          </Button>
        )}
      </div>

      <div role="alert">
        {alert && (
          <p className="flex items-start gap-1.5 text-sm text-danger-text">
            <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
            <span>{alert}</span>
          </p>
        )}
      </div>

      {connections.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-start gap-3">
            <Landmark aria-hidden="true" className="size-7 text-ink-2" strokeWidth={1.6} />
            <h3 className="text-[17px] font-semibold sm:text-[19px]">{t("emptyTitle")}</h3>
            <p className="text-sm leading-normal text-ink-2">{t("emptyBody")}</p>
            <Button
              type="button"
              disabled={busy || !linkToken || !connect.ready}
              aria-busy={connect.pending}
              onClick={connectBank}
            >
              {connectLabel ?? t("connect")}
            </Button>
          </CardContent>
        </Card>
      ) : (
        connections.map((connection) => (
          <BankCard
            key={connection.id}
            businessId={businessId}
            connection={connection}
            timeZone={timeZone}
            now={now}
            updateToken={updateTokens[connection.id] ?? null}
            disabled={busy}
            onChange={save}
          />
        ))
      )}

      <p className="flex items-center gap-2 text-sm text-ink-2">
        <Lock aria-hidden="true" className="size-[18px] shrink-0" strokeWidth={1.8} />
        {t("readOnlyNote")}
      </p>
      {/* Sonner's own label is English with its hotkey ("Notifications alt+T"). */}
      <Toaster customAriaLabel={t("notifications")} />
    </>
  )
}
