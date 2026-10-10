import type { Dashboard } from "@/components/dashboard/types"
import { formatDate, formatMoney } from "@/lib/format"

type Forecast = NonNullable<Dashboard["forecast"]>
type SummaryKey = "summary" | "summaryLowBelow" | "summaryLowAbove" | "summaryLow"
type Translate = (key: SummaryKey, values: Record<string, string>) => string

/** The chart's text summary for screen readers (AC 21). */
export function chartSummary(t: Translate, forecast: Forecast, minimumCents: number | null, currency: string): string {
  const weeks = forecast.weeks
  const last = weeks[weeks.length - 1]
  const low = weeks.reduce((a, b) => (b.end_balance_cents < a.end_balance_cents ? b : a))
  const money = (cents: number) => formatMoney(cents, currency)
  const first = t("summary", {
    opening: money(forecast.opening_balance_cents),
    last: money(last.end_balance_cents),
    lastWeek: formatDate(last.starts_on),
  })
  const values = { low: money(low.end_balance_cents), week: formatDate(low.starts_on) }
  const second =
    minimumCents === null
      ? t("summaryLow", values)
      : low.end_balance_cents < minimumCents
        ? t("summaryLowBelow", {
            ...values,
            short: money(minimumCents - low.end_balance_cents),
            minimum: money(minimumCents),
          })
        : t("summaryLowAbove", { ...values, minimum: money(minimumCents) })
  return `${first} ${second}`
}
