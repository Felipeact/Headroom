"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { CircleAlert } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { cn } from "cn"
import type { components } from "@/lib/api/schema"
import { formatList } from "@/lib/format"

export type ForecastStatus = components["schemas"]["ForecastStatus"]
type StepState = "done" | "active" | "pending"

// How often step 5 asks again, and when it offers a way out (spec 23, AC 26 and AC 29).
const POLL_MS = 3000
const SLOW_MS = 180_000

function StepIcon({ state }: { state: StepState }) {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="shrink-0 fill-none stroke-2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {state === "done" && (
        <g className="stroke-positive">
          <circle cx="12" cy="12" r="9" />
          <path d="M8.5 12.5l2.5 2.5 4.5-5" />
        </g>
      )}
      {state === "active" && (
        <>
          <circle cx="12" cy="12" r="9" className="stroke-border" />
          <path d="M12 3a9 9 0 0 1 9 9" className="origin-center stroke-accent motion-safe:animate-spin" />
        </>
      )}
      {state === "pending" && <circle cx="12" cy="12" r="9" className="stroke-line-strong" />}
    </svg>
  )
}

function Step({ state, title, detail }: { state: StepState; title: string; detail?: string }) {
  return (
    <li
      data-state={state}
      className={cn(
        "flex items-center gap-3 border-b border-line-soft last:border-b-0",
        detail ? "min-h-[60px]" : "min-h-[52px]",
      )}
    >
      <StepIcon state={state} />
      <div className="flex flex-col gap-0.5">
        <div
          className={cn(
            "text-[15px]",
            state === "active" && "font-semibold",
            state === "pending" && "text-ink-3",
          )}
        >
          {title}
        </div>
        {detail && <div className="text-[13px] text-ink-3">{detail}</div>}
      </div>
    </li>
  )
}

// Onboarding step 5, from design/mockups/onboarding-5-building-forecast.dc.html (spec 23). The
// page reloads the status from the API every 3 seconds while the forecast is building; the
// server component sends the owner to the dashboard once it is ready.
export function ForecastProgress({ status }: { status: ForecastStatus }) {
  const t = useTranslations("Onboarding")
  const { refresh } = useRouter()
  const [slow, setSlow] = useState(false)
  const building = status.state === "building"

  useEffect(() => {
    if (!building) return
    const timer = setInterval(refresh, POLL_MS)
    return () => clearInterval(timer)
  }, [building, refresh])

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_MS)
    return () => clearTimeout(timer)
  }, [])

  const read = status.transactions_read
  const others = status.recurring_count - status.recurring_names.length
  const found =
    status.recurring_count > 0
      ? t("Forecast.soFar", {
          names: formatList([...status.recurring_names, ...(others > 0 ? [t("Forecast.others", { count: others })] : [])]),
        })
      : undefined

  return (
    <div className="flex flex-1 flex-col justify-center gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-[28px] leading-tight font-semibold tracking-[-0.02em]">{t("Forecast.title")}</h1>
        <p className="text-[15px] leading-normal text-ink-2">{t("Forecast.intro")}</p>
      </div>
      <div role="status" aria-live="polite" className="rounded-[14px] border border-border bg-surface px-4 py-1">
        <ul className="flex flex-col">
          <Step state="done" title={t("Forecast.connected", { banks: formatList(status.institution_names) })} />
          <Step
            state={read ? "done" : "active"}
            title={
              !read
                ? t("Forecast.reading")
                : status.history_months === null || status.history_months === undefined
                  ? t("Forecast.readNoHistory")
                  : t("Forecast.read", { months: status.history_months })
            }
          />
          <Step state={read ? "active" : "pending"} title={t("Forecast.finding")} detail={found} />
          <Step state="pending" title={t("Forecast.building")} />
        </ul>
      </div>
      {status.state === "needs_attention" ? (
        <p className="flex items-start gap-1.5 text-sm text-danger-text">
          <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
          <span>
            {t("Forecast.needsAttention")}{" "}
            <Link href="/settings/banks" className="font-semibold underline">
              {t("Forecast.fixBank")}
            </Link>
          </span>
        </p>
      ) : (
        <p className="text-sm leading-normal text-ink-2">{t("Forecast.footer")}</p>
      )}
      {building && slow && (
        <p className="text-sm leading-normal text-ink-2">
          {t.rich("Forecast.slow", {
            link: (chunks) => (
              <Link href="/" className="font-semibold underline">
                {chunks}
              </Link>
            ),
          })}
        </p>
      )}
    </div>
  )
}
