"use client"

import { useState, useTransition } from "react"
import { Bell, CircleAlert } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { saveMinimumBalance } from "@/app/onboarding/minimum-balance/actions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { MAX_MINIMUM_CENTS, formatMoney, formatWholeDollarsInput, parseWholeDollars } from "@/lib/format"

// Onboarding step 4, from design/mockups/onboarding-4-minimum-balance.dc.html (spec 23). The
// field starts at the stored amount, else the suggested one, else empty.
export function MinimumBalanceForm({
  businessId,
  initialCents,
  suggestedCents,
}: {
  businessId: string
  initialCents: number | null
  suggestedCents: number | null
}) {
  const t = useTranslations("Onboarding")
  const router = useRouter()
  const start = initialCents ?? suggestedCents
  const [text, setText] = useState(start === null ? "" : formatWholeDollarsInput(start))
  // The alerts card names the last valid amount typed.
  const [shownCents, setShownCents] = useState(start)
  const [invalid, setInvalid] = useState(false)
  const [saveFailed, setSaveFailed] = useState(false)
  const [pending, startTransition] = useTransition()
  const describedBy = [suggestedCents === null ? null : "minimum-hint", invalid ? "minimum-error" : null]
    .filter(Boolean)
    .join(" ")

  function change(value: string) {
    setText(value)
    const cents = parseWholeDollars(value)
    if (cents !== null) setShownCents(cents)
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    const cents = parseWholeDollars(text)
    setInvalid(cents === null)
    setSaveFailed(false)
    if (cents === null) return
    startTransition(async () => {
      const result = await saveMinimumBalance(businessId, cents)
      if (result.error) setSaveFailed(true)
      else router.push("/onboarding/forecast")
    })
  }

  return (
    <form noValidate onSubmit={submit} className="flex flex-1 flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="minimum">{t("Minimum.label")}</Label>
        <div className="relative">
          <span
            aria-hidden="true"
            className="absolute top-1/2 left-4 -translate-y-1/2 text-[22px] font-semibold text-ink-2"
          >
            $
          </span>
          <Input
            id="minimum"
            name="minimum"
            inputMode="numeric"
            autoComplete="off"
            value={text}
            onChange={(event) => change(event.target.value)}
            aria-invalid={invalid ? true : undefined}
            aria-describedby={describedBy || undefined}
            className="h-14 border-2 border-accent pr-4 pl-[34px] text-[22px] font-semibold tabular-nums"
          />
        </div>
        {suggestedCents !== null && (
          <p id="minimum-hint" className="text-[13px] leading-[1.45] text-ink-3">
            {t("Minimum.suggested", { amount: formatMoney(suggestedCents) })}
          </p>
        )}
        {invalid && (
          <p id="minimum-error" className="flex items-start gap-1.5 text-[13px] text-danger-text">
            <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
            <span>{t("Minimum.errors.invalid", { max: formatMoney(MAX_MINIMUM_CENTS) })}</span>
          </p>
        )}
      </div>

      <div className="flex items-start gap-3 rounded-[14px] border border-border bg-surface p-4">
        <Bell aria-hidden="true" className="size-[22px] shrink-0 text-accent" strokeWidth={1.8} />
        <div className="flex flex-col gap-1">
          <p className="text-[15px] font-semibold">{t("Minimum.alertsTitle")}</p>
          <p className="text-sm leading-normal text-ink-2">
            {shownCents === null ? t("Minimum.alertsBodyNoAmount") : t("Minimum.alertsBody", { amount: formatMoney(shownCents) })}
          </p>
        </div>
      </div>

      <p className="text-[13px] text-ink-3">{t("Minimum.settingsNote")}</p>

      <div className="mt-auto flex flex-col gap-3">
        <div role="alert">
          {saveFailed && (
            <p className="flex items-start gap-1.5 text-sm text-danger-text">
              <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
              <span>{t("Minimum.errors.saveFailed")}</span>
            </p>
          )}
        </div>
        <Button type="submit" disabled={pending} aria-busy={pending} className="min-h-[52px] rounded-xl text-base">
          {t("Minimum.continue")}
        </Button>
      </div>
    </form>
  )
}
