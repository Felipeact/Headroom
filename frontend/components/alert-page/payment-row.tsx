import { useTranslations } from "next-intl"
import { cn } from "cn"
import type { Alert } from "@/lib/api/alerts"
import { formatDate, formatSignedMoney } from "@/lib/format"

type Item = Alert["items"][number]

// The API types `schedule` as a string; these are the values detection writes (spec 19).
const SCHEDULES = ["weekly", "biweekly", "semimonthly", "monthly", "quarterly"] as const
type Schedule = (typeof SCHEDULES)[number]
const isSchedule = (value: string | null): value is Schedule => SCHEDULES.includes(value as Schedule)

// A payment on the alert page: name, "Thu, Nov 12 · Expected payment", and the signed amount (AC 3-5).
export function PaymentRow({
  testId,
  name,
  item,
  className,
}: {
  testId: string
  name: string
  item: Item
  className?: string
}) {
  const t = useTranslations("AlertPage")
  const type =
    item.source === "expected_payment"
      ? t("types.expected")
      : item.source === "card_payment"
        ? t("types.card")
        : isSchedule(item.schedule)
          ? t(`types.${item.schedule}`)
          : t("types.recurring")

  return (
    <div data-testid={testId} className={cn("flex items-start justify-between gap-3 py-3", className)}>
      <div className="flex flex-col gap-[3px]">
        <p className="text-[15px] font-semibold">{name}</p>
        <p className="text-[13px] text-ink-3">{t("rowMeta", { date: formatDate(item.date, "weekday"), type })}</p>
      </div>
      <p className={cn("text-[15px] font-semibold tabular-nums", item.amount_cents > 0 && "text-positive")}>
        {formatSignedMoney(item.amount_cents, item.currency)}
      </p>
    </div>
  )
}
