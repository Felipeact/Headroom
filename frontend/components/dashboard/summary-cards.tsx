import { useTranslations } from "next-intl"
import { shortNames, weekLabel } from "@/components/dashboard/copy"
import { SummaryCard } from "@/components/dashboard/summary-card"
import type { Dashboard } from "@/components/dashboard/types"
import { formatDate, formatMoney } from "@/lib/format"

const CASH_TYPES = new Set(["checking", "savings"])

// Cash on hand, projected low, available credit and the next card payment (AC 12-14).
export function SummaryCards({ dashboard }: { dashboard: Dashboard }) {
  const t = useTranslations("Dashboard.cards")
  const { currency, minimum_balance_cents: minimum, projected_low: low } = dashboard
  const cash = dashboard.accounts.filter((a) => a.included && CASH_TYPES.has(a.type))
  const lines = dashboard.accounts.filter((a) => a.type === "line_of_credit")
  const card = dashboard.next_card_payment
  const cardName = card ? dashboard.accounts.find((a) => a.id === card.account_id)?.name : undefined
  const below = low !== null && minimum !== null && low.balance_cents < minimum

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:gap-5">
      <SummaryCard
        label={t("cashOnHand")}
        amount={formatMoney(dashboard.cash_on_hand_cents, currency)}
        note={t("cashAccounts", { names: shortNames(cash.map((a) => a.name)), count: cash.length })}
      />
      {low && (
        <SummaryCard
          label={t("projectedLow")}
          amount={formatMoney(low.balance_cents, currency)}
          warning={below}
          note={
            below ? (
              <>
                <span className="max-lg:hidden">
                  {t("lowBelow", {
                    week: weekLabel(low.week_starts_on),
                    short: formatMoney((minimum as number) - low.balance_cents, currency),
                  })}
                </span>
                <span className="lg:hidden">{t("lowBelowShort", { week: weekLabel(low.week_starts_on) })}</span>
              </>
            ) : (
              t("lowWeek", { week: weekLabel(low.week_starts_on) })
            )
          }
        />
      )}
      {dashboard.available_credit_cents !== null && (
        <SummaryCard
          label={t("availableCredit")}
          amount={formatMoney(dashboard.available_credit_cents, currency)}
          note={
            <>
              <span className="max-lg:hidden">{t("creditNote", { names: lines.map((a) => a.name).join(" + ") })}</span>
              <span className="lg:hidden">{t("creditNoteShort", { names: lines.map((a) => a.name).join(" + ") })}</span>
            </>
          }
        />
      )}
      {card && (
        <SummaryCard
          className="max-lg:hidden"
          label={t("nextCardPayment")}
          amount={formatMoney(Math.abs(card.amount_cents), currency)}
          note={t("cardDue", { card: cardName ?? "", date: formatDate(card.date, "weekday") })}
        />
      )}
    </div>
  )
}
