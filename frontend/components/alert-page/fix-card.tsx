import { CircleCheck } from "lucide-react"
import { useTranslations } from "next-intl"
import { cn } from "cn"
import { itemName } from "@/components/dashboard/copy"
import type { Alert } from "@/lib/api/alerts"
import { formatDate, formatMoney } from "@/lib/format"

type Fix = Alert["fixes"][number]
type Item = Alert["items"][number]

// One way to fix the gap (AC 6-12): a title, a paragraph, and the new lowest balance.
export function FixCard({ fix, minimumCents, arrives }: { fix: Fix; minimumCents: number; arrives?: Item }) {
  const t = useTranslations("AlertPage")
  const money = (cents: number) => formatMoney(Math.abs(cents), fix.currency)
  const amount = money(fix.amount_cents)
  const name = itemName(fix)
  const date = formatDate(fix.date)
  const original = fix.original_date ? formatDate(fix.original_date) : ""
  const repay = fix.repay_on ? formatDate(fix.repay_on) : ""
  const available = money(fix.available_cents ?? 0)

  const [title, body] = {
    pay_early: () => [t("fix.payEarlyTitle", { name }), t("fix.payEarlyBody", { amount, due: original, date })],
    move_payment: () => [t("fix.moveTitle", { name }), t("fix.moveBody", { name, amount, date })],
    draw_credit: () => [
      t("fix.drawTitle", { amount }),
      arrives
        ? t("fix.drawBodyWhen", { available, name: itemName(arrives) })
        : t("fix.drawBodyOn", { available, date: repay }),
    ],
    financing: () => [t("fix.financingTitle", { amount }), t("fix.financingBody", { date, repay })],
  }[fix.kind]()
  const ok = fix.new_lowest_balance_cents >= minimumCents

  return (
    <div
      data-testid="fix-card"
      data-kind={fix.kind}
      className="flex flex-col gap-2.5 rounded-[14px] border border-border bg-surface p-4"
    >
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="text-sm leading-normal text-ink-2">{body}</p>
      <div
        data-testid="fix-result"
        className={cn(
          "flex items-center justify-between gap-2 rounded-[10px] px-3 py-2.5",
          ok ? "bg-positive-bg text-positive" : "bg-warning-bg text-warning-strong",
        )}
      >
        <p className="flex items-center gap-1.5 text-[13px] font-medium">
          {ok && <CircleCheck data-testid="fix-ok" aria-hidden="true" className="size-4" strokeWidth={2} />}
          {t("newLowest")}
        </p>
        <p className="text-[15px] font-semibold tabular-nums">{formatMoney(fix.new_lowest_balance_cents, fix.currency)}</p>
      </div>
    </div>
  )
}
