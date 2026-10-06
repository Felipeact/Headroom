"use client"

import { Pencil, Trash2 } from "lucide-react"
import { useTranslations } from "next-intl"
import { DeletePaymentDialog } from "@/components/expected-payments/delete-payment-dialog"
import { PaymentDialog } from "@/components/expected-payments/payment-dialog"
import type { AccountOption, ExpectedPayment } from "@/components/expected-payments/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { formatDate, formatSignedMoney } from "@/lib/format"

// On a phone each row becomes a block: the description and the amount, then the date, how it
// repeats and the account underneath, then the actions.
const CELL = "px-3 py-2 max-sm:px-0 max-sm:py-0.5"
const DETAIL = "max-sm:col-span-2 max-sm:text-sm max-sm:text-ink-2"

// One expected payment in the table on the Expected payments page (spec 20).
export function PaymentRow({
  businessId,
  payment,
  accounts,
}: {
  businessId: string
  payment: ExpectedPayment
  accounts: AccountOption[]
}) {
  const t = useTranslations("ExpectedPayments")
  const account = accounts.find((a) => a.id === payment.account_id)
  // The list holds only payments with a next date (AC 9).
  const nextDate = payment.next_date ?? payment.date
  const moneyIn = payment.amount_cents > 0

  return (
    <tr className="border-b border-surface-muted last:border-b-0 max-sm:grid max-sm:grid-cols-[1fr_auto] max-sm:gap-x-3 max-sm:py-3">
      <td className={`${CELL} ${DETAIL} whitespace-nowrap max-sm:order-3`}>
        <span className="inline-flex flex-wrap items-center gap-2">
          {formatDate(nextDate, "weekday")}
          {payment.overdue && <Badge variant="warning">{t("overdue")}</Badge>}
        </span>
      </td>
      <td data-user-content className={`${CELL} max-sm:order-1 max-sm:font-semibold`}>
        {payment.description}
      </td>
      <td data-user-content className={`${CELL} ${DETAIL} max-sm:order-5`}>
        {account ? account.name : t("accountRemoved")}
      </td>
      <td className={`${CELL} ${DETAIL} text-ink-2 max-sm:order-4`}>
        {t(`repeats.${payment.repeats ?? "once"}`)}
      </td>
      <td
        className={`${CELL} text-right font-semibold whitespace-nowrap tabular-nums max-sm:order-2 ${
          moneyIn ? "text-positive" : ""
        }`}
      >
        {formatSignedMoney(payment.amount_cents, payment.currency)}
      </td>
      <td className={`${CELL} max-sm:order-6 max-sm:col-span-2`}>
        <div className="flex justify-end gap-1 max-sm:-ml-2.5 max-sm:justify-start">
          <PaymentDialog
            businessId={businessId}
            accounts={accounts}
            payment={payment}
            trigger={
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("edit", { description: payment.description })}
              >
                <Pencil aria-hidden="true" className="size-[18px] text-ink-2" strokeWidth={1.8} />
              </Button>
            }
          />
          <DeletePaymentDialog
            businessId={businessId}
            paymentId={payment.id}
            description={payment.description}
            trigger={
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("delete", { description: payment.description })}
              >
                <Trash2 aria-hidden="true" className="size-[18px] text-ink-2" strokeWidth={1.8} />
              </Button>
            }
          />
        </div>
      </td>
    </tr>
  )
}
