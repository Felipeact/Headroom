import Link from "next/link"
import { ArrowLeft, TriangleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { DismissAlert } from "@/components/alert-page/dismiss-alert"
import { FixCard } from "@/components/alert-page/fix-card"
import { PaymentRow } from "@/components/alert-page/payment-row"
import { causesBySize, itemName, weekLabel } from "@/components/dashboard/copy"
import type { Alert } from "@/lib/api/alerts"
import { formatDate, formatMoney } from "@/lib/format"

/** The business-local calendar day of a timestamp, as "YYYY-MM-DD". */
function localDay(isoDateTime: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(isoDateTime),
  )
}

// The alert page (spec 27, `alert.dc.html`): one column, at most 640px wide on larger screens.
export function AlertView({ businessId, timeZone, alert }: { businessId: string; timeZone: string; alert: Alert }) {
  const t = useTranslations("AlertPage")
  const tAlert = useTranslations("Dashboard.alert")
  const money = (cents: number) => formatMoney(cents, alert.currency)
  const causes = causesBySize(alert)
  const arrives = alert.items.find((i) => i.kind === "arrives_after")
  const week = weekLabel(alert.lowest_week_starts_on)

  return (
    <div data-testid="alert-page" className="mx-auto flex w-full max-w-[640px] flex-col gap-5">
      <Link
        href="/"
        className="flex min-h-11 items-center gap-1.5 self-start text-[15px] font-medium text-accent no-underline hover:text-accent-hover"
      >
        <ArrowLeft aria-hidden="true" className="size-[18px]" strokeWidth={2} />
        {t("back")}
      </Link>

      <div className="flex flex-col gap-2.5">
        <p className="flex items-center gap-2 text-xs font-semibold tracking-[0.06em] text-warning-text uppercase">
          <TriangleAlert aria-hidden="true" className="size-[18px]" strokeWidth={1.8} />
          {tAlert("label")}
        </p>
        <h1 className="font-heading text-[26px] leading-[1.25] font-semibold tracking-[-0.02em]">
          {tAlert("title", { minimum: money(alert.minimum_cents), week })}
        </h1>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div
          data-testid="projected-low"
          className="flex flex-col gap-1 rounded-[14px] border border-warning-border bg-warning-bg px-4 py-3.5"
        >
          <p className="text-[13px] font-medium text-warning-text">{t("projectedLow")}</p>
          <p className="font-heading text-[26px] font-semibold text-warning-strong tabular-nums">
            {money(alert.lowest_balance_cents)}
          </p>
          <p className="text-xs text-warning-text">{t("weekOf", { week })}</p>
        </div>
        <div data-testid="short-by" className="flex flex-col gap-1 rounded-[14px] border border-border bg-surface px-4 py-3.5">
          <p className="text-[13px] font-medium text-ink-2">{t("shortBy")}</p>
          <p className="font-heading text-[26px] font-semibold tabular-nums">{money(alert.shortfall_cents)}</p>
          <p className="text-xs text-ink-3">{t("belowMinimum")}</p>
        </div>
      </div>

      <section
        aria-labelledby="causes-title"
        className="flex flex-col rounded-[14px] border border-border bg-surface p-4"
      >
        <h2 id="causes-title" className="mb-1 text-[17px] font-semibold">
          {t("causesTitle")}
        </h2>
        {causes.map((item, i) => (
          <PaymentRow
            key={i}
            testId="cause-row"
            name={itemName(item)}
            item={item}
            className={i < causes.length - 1 ? "border-b border-surface-muted" : undefined}
          />
        ))}
        {arrives && (
          <>
            <h3 className="mt-0 border-t border-border pt-2.5 pb-0.5 text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase">
              {t("arrivesAfter")}
            </h3>
            <PaymentRow
              testId="arrives-row"
              name={arrives.description ?? arrives.counterparty ?? ""}
              item={arrives}
              className="pt-2.5 pb-0"
            />
          </>
        )}
      </section>

      {alert.fixes.length > 0 && (
        <section aria-labelledby="fixes-title" className="flex flex-col gap-3">
          <h2 id="fixes-title" className="text-[17px] font-semibold">
            {t("fixesTitle")}
          </h2>
          {alert.fixes.map((fix) => (
            <FixCard key={fix.kind} fix={fix} minimumCents={alert.minimum_cents} arrives={arrives} />
          ))}
        </section>
      )}

      {alert.state === "open" && <DismissAlert businessId={businessId} alertId={alert.id} />}
      {alert.state === "dismissed" && alert.dismissed_at && (
        <p className="text-center text-[13px] leading-[1.45] text-ink-3">
          {t("dismissedNote", { date: formatDate(localDay(alert.dismissed_at, timeZone)) })}
        </p>
      )}
      {alert.state === "resolved" && (
        <p className="text-center text-[13px] leading-[1.45] text-ink-3">{t("resolvedNote")}</p>
      )}
    </div>
  )
}
