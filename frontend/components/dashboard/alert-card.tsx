"use client"

import { useState, useTransition } from "react"
import Link from "next/link"
import { ArrowRight, TriangleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { dismissAlert } from "@/app/(app)/actions"
import { causesBySize, itemName, weekLabel } from "@/components/dashboard/copy"
import type { Dashboard } from "@/components/dashboard/types"
import { Button } from "@/components/ui/button"
import { formatMoney } from "@/lib/format"

type Alert = Dashboard["alerts"][number]
type Fix = Alert["fixes"][number]

// A cash gap alert on the dashboard (AC 15-18): what happens, the top fix, and two actions.
export function AlertCard({ businessId, alert }: { businessId: string; alert: Alert }) {
  const t = useTranslations("Dashboard.alert")
  const [failed, setFailed] = useState(false)
  const [pending, startDismiss] = useTransition()
  const money = (cents: number) => formatMoney(Math.abs(cents), alert.currency)
  const titleId = `alert-${alert.id}`

  const causes = causesBySize(alert).map((c) => t("cause", { name: itemName(c), amount: money(c.amount_cents) }))
  const low = money(alert.lowest_balance_cents)
  const body =
    causes.length <= 1
      ? t("bodyOne", { first: causes[0] ?? "", low })
      : causes.length === 2
        ? t("bodyTwo", { first: causes[0], second: causes[1], low })
        : t("bodyMore", { first: causes[0], second: causes[1], more: causes.length - 2, low })

  function fixText(fix: Fix): string {
    const amount = money(fix.amount_cents)
    const name = itemName(fix)
    switch (fix.kind) {
      case "pay_early":
        return t("fixPayEarly", { name, amount })
      case "move_payment":
        return t("fixMovePayment", { name, amount })
      case "draw_credit":
        return t("fixDrawCredit", { name: fix.description ?? "", amount })
      case "financing":
        return t("fixFinancing", { amount })
    }
  }
  const top = alert.fixes[0]

  function dismiss() {
    setFailed(false)
    startDismiss(async () => {
      const result = await dismissAlert(businessId, alert.id)
      if (result.error) setFailed(true)
      else toast(t("dismissed"))
    })
  }

  return (
    <section
      aria-labelledby={titleId}
      data-testid="alert-card"
      className="flex flex-col gap-3.5 rounded-[14px] border border-warning-border bg-warning-bg px-4 py-5 sm:px-6"
    >
      <div className="flex items-start gap-3">
        <TriangleAlert aria-hidden="true" className="size-6 shrink-0 text-warning-text" strokeWidth={1.8} />
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-semibold tracking-[0.06em] text-warning-text uppercase">{t("label")}</p>
          <h2 id={titleId} className="text-[17px] leading-[1.3] font-semibold text-warning-strong sm:text-[19px]">
            {t("title", { minimum: money(alert.minimum_cents), week: weekLabel(alert.lowest_week_starts_on) })}
          </h2>
          <p className="text-[15px] leading-normal">{body}</p>
        </div>
      </div>
      {top && (
        <div className="flex items-center gap-3 rounded-[10px] border border-warning-border bg-surface px-4 py-3.5">
          <ArrowRight aria-hidden="true" className="size-[22px] shrink-0" strokeWidth={1.8} />
          <p data-testid="top-fix" className="text-[15px] leading-[1.45]">
            <strong className="font-semibold">{t("topFix")}</strong> {fixText(top)}
            {top.new_lowest_balance_cents >= alert.minimum_cents && (
              <span className="max-lg:hidden"> {t("keepsAbove")}</span>
            )}
          </p>
        </div>
      )}
      <div className="flex flex-wrap gap-2.5">
        <Button asChild variant="outline">
          <Link href={`/alerts/${alert.id}`}>{t("seeFixes", { count: alert.fixes.length })}</Link>
        </Button>
        <Button type="button" variant="secondary" disabled={pending} aria-busy={pending} onClick={dismiss}>
          {pending ? t("dismissing") : t("dismiss")}
        </Button>
      </div>
      {failed && (
        <p role="alert" className="text-sm text-danger-text">
          {t("dismissFailed")}
        </p>
      )}
    </section>
  )
}
