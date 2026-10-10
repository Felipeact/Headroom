"use client"

import { useId, useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { saveEmailPreferences } from "@/app/(app)/settings/email/actions"
import { Card, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Toaster } from "@/components/ui/sonner"
import { Switch } from "@/components/ui/switch"
import type { EmailPreferences } from "@/lib/api/email-preferences"

type Kind = keyof EmailPreferences

const ROWS = [
  { kind: "alerts", label: "alerts", hint: "alertsHint" },
  { kind: "weekly_digest", label: "digest", hint: "digestHint" },
] as const satisfies readonly { kind: Kind; label: string; hint: string }[]

// Each switch saves both choices at once, like "Counts as cash" in bank settings (spec 17).
export function EmailPreferencesForm({ initial }: { initial: EmailPreferences }) {
  const t = useTranslations("Settings.Email")
  const id = useId()
  const [preferences, setPreferences] = useState(initial)
  const [failed, setFailed] = useState(false)
  const [pending, startTransition] = useTransition()

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
      <Toaster customAriaLabel={t("notifications")} />
    </div>
  )
}
