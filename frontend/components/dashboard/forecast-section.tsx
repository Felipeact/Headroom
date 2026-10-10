import { useTranslations } from "next-intl"
import { chartSummary } from "@/components/dashboard/chart-summary"
import { ForecastChart } from "@/components/dashboard/forecast-chart"
import type { Dashboard } from "@/components/dashboard/types"

// The "13-week forecast" panel (AC 19-21): the chart, and its text summary for screen readers.
export function ForecastSection({ dashboard }: { dashboard: Dashboard }) {
  const t = useTranslations("Dashboard.chart")
  const forecast = dashboard.forecast
  if (!forecast) return null

  return (
    <section
      aria-labelledby="forecast-title"
      className="flex min-w-0 flex-col gap-4 rounded-[14px] border border-border bg-surface px-4 py-5 sm:px-6 lg:flex-[2]"
    >
      <div className="flex flex-col gap-1">
        <h2 id="forecast-title" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-ink-3">{t("subtitle")}</p>
      </div>
      <p data-testid="chart-summary" className="sr-only">
        {chartSummary(t, forecast, dashboard.minimum_balance_cents, dashboard.currency)}
      </p>
      <ForecastChart forecast={forecast} minimumCents={dashboard.minimum_balance_cents} currency={dashboard.currency} />
    </section>
  )
}
