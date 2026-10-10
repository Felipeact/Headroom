"use client"

import { useSyncExternalStore } from "react"
import { useTranslations } from "next-intl"
import { Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ReferenceLine, XAxis, YAxis } from "recharts"
import type { Dashboard } from "@/components/dashboard/types"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import { formatCompactMoney, formatDate, formatMoney } from "@/lib/format"

type Forecast = NonNullable<Dashboard["forecast"]>

export type ChartPoint = {
  label: string
  // Dollars, for plotting only; every label is formatted from cents.
  balance: number
  range: [number, number]
  cents: number
}

const DESKTOP = "(min-width: 1024px)"
const REDUCED_MOTION = "(prefers-reduced-motion: reduce)"

function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query)
      list.addEventListener("change", onChange)
      return () => list.removeEventListener("change", onChange)
    },
    () => window.matchMedia(query).matches,
    // Phones first on the server; the desktop labels follow on hydration.
    () => false,
  )
}

/** Today at the opening balance, then each week's end balance at its Monday (AC 19). */
export function chartPoints(forecast: Forecast, today: string): ChartPoint[] {
  const opening = forecast.opening_balance_cents / 100
  return [
    { label: today, balance: opening, range: [opening, opening], cents: forecast.opening_balance_cents },
    ...forecast.weeks.map((week) => ({
      label: formatDate(week.starts_on),
      balance: week.end_balance_cents / 100,
      range: [week.low_cents / 100, week.high_cents / 100] as [number, number],
      cents: week.end_balance_cents,
    })),
  ]
}

/** "Today" and every 2nd week from week 1 on desktop; "Today" and weeks 3, 7 and 11 on phones. */
export function xTicks(points: ChartPoint[], desktop: boolean): string[] {
  const weeks = desktop ? [1, 3, 5, 7, 9, 11, 13] : [3, 7, 11]
  return [points[0].label, ...weeks.map((n) => points[n].label)]
}

// The 13-week forecast chart (AC 19, AC 20, AC 36), styled as DESIGN.md "Forecast chart". Its
// text summary is rendered beside it by the dashboard, so screen readers skip the drawing.
export function ForecastChart({
  forecast,
  minimumCents,
  currency,
}: {
  forecast: Forecast
  minimumCents: number | null
  currency: string
}) {
  const t = useTranslations("Dashboard.chart")
  const desktop = useMedia(DESKTOP)
  const animate = !useMedia(REDUCED_MOTION)
  const points = chartPoints(forecast, t("today"))
  const lowest = points.slice(1).reduce((a, b) => (b.cents < a.cents ? b : a))
  const minimum = minimumCents === null ? null : formatMoney(minimumCents, currency)
  const config = { balance: { label: t("legendBalance"), color: "var(--accent)" } } satisfies ChartConfig

  return (
    <div className="flex flex-col gap-3">
      <ChartContainer
        config={config}
        aria-hidden="true"
        data-points={points.length}
        className="aspect-auto h-[240px] w-full lg:h-[280px]">
        {/* The text summary beside the chart is what screen readers get, so the drawing takes no focus. */}
        <ComposedChart data={points} accessibilityLayer={false} margin={{ top: 24, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--line-soft)" />
          <XAxis
            dataKey="label"
            ticks={xTicks(points, desktop)}
            interval={0}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--ink-3)", fontSize: 12 }}
          />
          <YAxis
            width={48}
            tickLine={false}
            axisLine={false}
            tickCount={desktop ? 5 : 3}
            tickFormatter={(dollars: number) => formatCompactMoney(Math.round(dollars * 100), currency)}
            tick={{ fill: "var(--ink-3)", fontSize: 12 }}
          />
          <ReferenceLine y={0} stroke="var(--line-strong)" />
          <Area
            dataKey="range"
            stroke="none"
            fill="var(--accent)"
            fillOpacity={0.13}
            isAnimationActive={animate}
          />
          <Line
            dataKey="balance"
            stroke="var(--accent)"
            strokeWidth={2.5}
            dot={false}
            isAnimationActive={animate}
          />
          {minimum !== null && minimumCents !== null && (
            <ReferenceLine
              y={minimumCents / 100}
              stroke="var(--warning-line)"
              strokeDasharray="6 4"
              strokeWidth={2}
              label={{
                value: desktop ? t("minimumLabel", { minimum }) : t("minimumLabelShort", { minimum }),
                position: "insideTopRight",
                fill: "var(--warning-text)",
                fontSize: 12,
              }}
            />
          )}
          <ReferenceDot
            x={lowest.label}
            y={lowest.balance}
            r={5}
            fill="var(--accent)"
            stroke="var(--surface)"
            label={{
              value: t("lowLabel", { low: formatMoney(lowest.cents, currency) }),
              position: "top",
              fill: "var(--ink)",
              fontSize: 12,
              fontWeight: 600,
            }}
          />
        </ComposedChart>
      </ChartContainer>
      <ul className="flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-ink-2">
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="inline-block h-[3px] w-[22px] rounded-sm bg-accent" />
          {t("legendBalance")}
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="inline-block h-3 w-[22px] rounded-[3px] bg-accent opacity-20" />
          {t("legendRange")}
        </li>
        {minimum !== null && (
          <li className="flex items-center gap-2">
            <span aria-hidden="true" className="inline-block w-[22px] border-t-2 border-dashed border-warning-line" />
            <span className="max-lg:hidden">{t("legendMinimum", { minimum })}</span>
            <span className="lg:hidden">{t("legendMinimumShort")}</span>
          </li>
        )}
      </ul>
    </div>
  )
}
