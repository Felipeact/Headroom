import Link from "next/link"
import { useTranslations } from "next-intl"
import { CreditRow } from "@/components/dashboard/credit-row"
import type { Dashboard } from "@/components/dashboard/types"
import { formatMoney } from "@/lib/format"

type Account = Dashboard["accounts"][number]

const GROUP = "text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase"

// The accounts panel (AC 22): included cash accounts and their total, then cards and lines of
// credit, which never count as cash.
export function AccountsPanel({ dashboard }: { dashboard: Dashboard }) {
  const t = useTranslations("Dashboard.accounts")
  const cash = dashboard.accounts.filter((a) => a.included && (a.type === "checking" || a.type === "savings"))
  // Cards first, then lines of credit, as the mockups list them (AC 22).
  const credit = [
    ...dashboard.accounts.filter((a) => a.type === "credit_card"),
    ...dashboard.accounts.filter((a) => a.type === "line_of_credit"),
  ]
  const where = (a: Account) =>
    a.mask ? t("institution", { institution: a.institution_name, mask: a.mask }) : a.institution_name

  return (
    <section
      aria-labelledby="accounts-title"
      className="flex min-w-0 flex-col gap-[18px] rounded-[14px] border border-border bg-surface px-4 py-5 sm:px-6 lg:flex-1"
    >
      <div className="flex items-center justify-between">
        <h2 id="accounts-title" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <Link
          href="/settings/banks"
          className="flex min-h-11 min-w-11 items-center justify-end text-sm font-medium text-accent hover:text-accent-hover"
        >
          {t("manage")}
        </Link>
      </div>
      {cash.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <h3 className={GROUP}>{t("cash")}</h3>
          <ul className="flex flex-col gap-2">
            {cash.map((a) => (
              <li
                key={a.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-3.5"
              >
                <div className="flex flex-col gap-0.5">
                  <p className="flex flex-wrap items-center gap-2 text-[15px] font-semibold">
                    <span data-user-content>{a.name}</span>
                    {a.primary && (
                      <span className="rounded-md border border-border px-1.5 py-0.5 text-[11px] font-semibold tracking-[0.04em] text-ink-2 uppercase">
                        {t("primary")}
                      </span>
                    )}
                  </p>
                  <p data-user-content className="text-[13px] text-ink-3">
                    {where(a)}
                  </p>
                </div>
                <p className="text-base font-semibold tabular-nums">{formatMoney(a.balance_cents ?? 0, a.currency)}</p>
              </li>
            ))}
          </ul>
          <p className="flex items-center justify-between px-1 pt-1 text-[15px] font-semibold">
            <span>{t("cashOnHand")}</span>
            <span className="tabular-nums">{formatMoney(dashboard.cash_on_hand_cents, dashboard.currency)}</span>
          </p>
        </div>
      )}
      {cash.length > 0 && credit.length > 0 && <div aria-hidden="true" className="h-px bg-border" />}
      {credit.length > 0 && (
        <div className="flex flex-col gap-3.5">
          <h3 className={GROUP}>{t("credit")}</h3>
          <ul className="flex flex-col gap-3.5">
            {credit.map((a) => (
              <CreditRow key={a.id} account={a} where={where(a)} />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
