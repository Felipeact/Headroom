"use client"

import { useId, useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { saveEmailPreferences, setClientAlertEmails } from "@/app/(app)/settings/email/actions"
import { Card, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Toaster } from "@/components/ui/sonner"
import { Switch } from "@/components/ui/switch"
import type { EmailPreferences } from "@/lib/api/email-preferences"

type Kind = keyof EmailPreferences

/** A business the signed-in user works for as a bookkeeper, and their alert choice for it. */
export type ClientAlerts = { id: string; name: string; enabled: boolean }

const ROWS = [
  { kind: "alerts", label: "alerts", hint: "alertsHint" },
  { kind: "weekly_digest", label: "digest", hint: "digestHint" },
] as const satisfies readonly { kind: Kind; label: string; hint: string }[]

// Each switch saves both choices at once, like "Counts as cash" in bank settings (spec 17).
export function EmailPreferencesForm({
  initial,
  clients = [],
}: {
  initial: EmailPreferences
  clients?: ClientAlerts[]
}) {
  const t = useTranslations("Settings.Email")
  const id = useId()
  const [preferences, setPreferences] = useState(initial)
  const [failed, setFailed] = useState(false)
  const [pending, startTransition] = useTransition()
  const [clientChoices, setClientChoices] = useState(() => Object.fromEntries(clients.map((c) => [c.id, c.enabled])))
  const [clientFailed, setClientFailed] = useState(false)

  function changeClient(businessId: string, on: boolean) {
    const previous = clientChoices
    setClientChoices({ ...previous, [businessId]: on })
    setClientFailed(false)
    startTransition(async () => {
      const { ok } = await setClientAlertEmails(businessId, on)
      if (ok) {
        toast(t("clientSaved"))
      } else {
        setClientChoices(previous)
        setClientFailed(true)
      }
    })
  }

  function change(kind: Kind, on: boolean) {
    const previous = preferences
    const next = { ...preferences, [kind]: on }
    setPreferences(next)
    setFailed(false)
    startTransition(async () => {
      const { ok } = await saveEmailPreferences(next)
      if (ok) {
        toast(t("saved"))
      } else {
        setPreferences(previous)
        setFailed(true)
      }
    })
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-[22px] font-semibold">{t("title")}</h2>
      <Card>
        <CardContent className="flex flex-col divide-y divide-line-soft">
          {ROWS.map(({ kind, label, hint }) => (
            <div
              key={kind}
              data-testid="email-preference-row"
              className="flex min-h-11 items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <Label htmlFor={`${id}-${kind}`} className="text-[15px] font-semibold">
                  {t(label)}
                </Label>
                <p id={`${id}-${kind}-hint`} className="text-sm text-ink-2">
                  {t(hint)}
                </p>
              </div>
              <Switch
                id={`${id}-${kind}`}
                checked={preferences[kind]}
                disabled={pending}
                aria-describedby={`${id}-${kind}-hint`}
                onCheckedChange={(on) => change(kind, on)}
              />
            </div>
          ))}
        </CardContent>
      </Card>
      {failed && (
        <p role="alert" className="text-sm text-danger-text">
          {t("saveFailed")}
        </p>
      )}
      {clients.length > 0 && (
        <section aria-labelledby={`${id}-clients`} className="flex flex-col gap-3">
          <div className="flex flex-col gap-0.5">
            <h3 id={`${id}-clients`} className="text-[17px] font-semibold">
              {t("clientsTitle")}
            </h3>
            <p className="text-sm text-ink-2">{t("clientsHint")}</p>
          </div>
          <Card>
            <CardContent className="flex flex-col divide-y divide-line-soft">
              {clients.map((client) => (
                <div
                  key={client.id}
                  data-testid="client-alert-row"
                  className="flex min-h-11 items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
                >
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <Label htmlFor={`${id}-client-${client.id}`} className="text-[15px] font-semibold">
                      {t("clientAlerts", { business: client.name })}
                    </Label>
                    <p id={`${id}-client-${client.id}-hint`} className="text-sm text-ink-2">
                      {t("clientAlertsHint", { business: client.name })}
                    </p>
                  </div>
                  <Switch
                    id={`${id}-client-${client.id}`}
                    checked={clientChoices[client.id] ?? false}
                    disabled={pending}
                    aria-describedby={`${id}-client-${client.id}-hint`}
                    onCheckedChange={(on) => changeClient(client.id, on)}
                  />
                </div>
              ))}
            </CardContent>
          </Card>
        </section>
      )}
      {clientFailed && (
        <p role="alert" className="text-sm text-danger-text">
          {t("clientSaveFailed")}
        </p>
      )}
      <Toaster customAriaLabel={t("notifications")} />
    </div>
  )
}
