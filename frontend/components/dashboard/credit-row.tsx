import { CreditCard, Landmark } from "lucide-react"
import { useTranslations } from "next-intl"
import type { Dashboard } from "@/components/dashboard/types"
import { formatDate, formatMoney } from "@/lib/format"

type Account = Dashboard["accounts"][number]

// A credit card (amount owed, next payment) or a line of credit (available) in the accounts panel.
export function CreditRow({ account: a, where }: { account: Account; where: string }) {
  const t = useTranslations("Dashboard.accounts")
  const card = a.type === "credit_card"
  const Icon = card ? CreditCard : Landmark

  return (
    <li className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <Icon aria-hidden="true" className="size-[22px] shrink-0 text-ink-2" strokeWidth={1.8} />
        <div className="flex flex-col gap-0.5">
          <p data-user-content className="text-[15px] font-semibold">
            {a.name}
          </p>
          <p data-user-content className="text-[13px] text-ink-3">
            {where}
          </p>
        </div>
      </div>
      <div className="flex flex-col items-end gap-0.5">
        <p className="text-[15px] font-semibold tabular-nums">
          {formatMoney((card ? a.balance_cents : a.available_cents) ?? 0, a.currency)}
        </p>
        <p className="text-[13px] text-ink-3">
          {!card && t("available")}
          {card && a.next_payment_on && (
            <>
              <span className="max-lg:hidden">{t("paymentDue", { date: formatDate(a.next_payment_on) })}</span>
              <span className="lg:hidden">{t("paymentDueShort", { date: formatDate(a.next_payment_on) })}</span>
            </>
          )}
        </p>
      </div>
    </li>
  )
}
