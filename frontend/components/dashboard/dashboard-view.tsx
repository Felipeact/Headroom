import { Hourglass, Landmark } from "lucide-react"
import { useTranslations } from "next-intl"
import { AccountsPanel } from "@/components/dashboard/accounts-panel"
import { AddPaymentButton } from "@/components/dashboard/add-payment-button"
import { AlertCard } from "@/components/dashboard/alert-card"
import { longDate } from "@/components/dashboard/copy"
import { ForecastSection } from "@/components/dashboard/forecast-section"
import { NoticeCard } from "@/components/dashboard/notice-card"
import { StaleBanner } from "@/components/dashboard/stale-banner"
import { StatusLine } from "@/components/dashboard/status-line"
import { SummaryCards } from "@/components/dashboard/summary-cards"
import type { Dashboard } from "@/components/dashboard/types"
import { UpcomingList } from "@/components/dashboard/upcoming-list"
import { ReconnectBanner } from "@/components/settings/reconnect-banner"
import { Toaster } from "@/components/ui/sonner"

export type Attention = { connectionId: string; bank: string; updateToken: string | null }

// The dashboard (spec 26), from design/mockups/dashboard-desktop.dc.html and dashboard-phone.dc.html.
export function DashboardView({
  businessId,
  timeZone,
  now,
  dashboard,
  attention,
}: {
  businessId: string
  timeZone: string
  now: string
  dashboard: Dashboard
  attention: Attention[]
}) {
  const t = useTranslations("Dashboard")

  // No bank yet: only the empty state (AC 27).
  if (dashboard.connections.length === 0) {
    return (
      <NoticeCard
        icon={Landmark}
        headingLevel={1}
        title={t("empty.title")}
        body={t("empty.body")}
        action={t("empty.action")}
        href="/onboarding/bank"
      />
    )
  }

  const forecast = dashboard.forecast
  const through = forecast ? longDate(forecast.weeks[forecast.weeks.length - 1].ends_on, false) : null
  const accounts = dashboard.accounts
    .filter((a) => a.included)
    .map(({ id, name, primary }) => ({ id, name, primary }))

  return (
    <>
      <StatusLine connections={dashboard.connections} timeZone={timeZone} now={now} />
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
        <div className="flex flex-col gap-1.5">
          <h1 className="font-heading text-[30px] leading-[1.1] font-semibold tracking-[-0.02em] sm:text-[40px]">
            {t("title")}
          </h1>
          {through && (
            <p className="text-[15px] text-ink-2">
              <span className="max-lg:hidden">{t("dateLine", { asOf: longDate(dashboard.as_of, true), through })}</span>
              <span className="lg:hidden">{t("throughLine", { through })}</span>
            </p>
          )}
        </div>
        <AddPaymentButton businessId={businessId} accounts={accounts} />
      </div>

      {attention.map((a) => (
        <ReconnectBanner
          key={a.connectionId}
          businessId={businessId}
          connectionId={a.connectionId}
          bank={a.bank}
          reason="login"
          updateToken={a.updateToken}
        />
      ))}
      {attention.length === 0 && forecast?.incomplete && <StaleBanner />}

      <SummaryCards dashboard={dashboard} />

      {forecast ? (
        <>
          {dashboard.alerts.length > 0 && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-5">
              {dashboard.alerts.map((alert) => (
                <AlertCard key={alert.id} businessId={businessId} alert={alert} />
              ))}
            </div>
          )}
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-6">
            <ForecastSection dashboard={dashboard} />
            <AccountsPanel dashboard={dashboard} />
          </div>
          <UpcomingList dashboard={dashboard} />
        </>
      ) : (
        <>
          <NoticeCard
            icon={Hourglass}
            title={t("building.title")}
            body={t("building.body")}
            action={t("building.action")}
            href="/onboarding/forecast"
          />
          <AccountsPanel dashboard={dashboard} />
        </>
      )}

      {/* Sonner's own label is English with its hotkey ("Notifications alt+T"). */}
      <Toaster customAriaLabel={t("notifications")} />
    </>
  )
}
