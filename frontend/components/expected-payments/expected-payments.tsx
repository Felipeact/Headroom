"use client"

import { CalendarClock, Plus } from "lucide-react"
import { useTranslations } from "next-intl"
import { PaymentDialog } from "@/components/expected-payments/payment-dialog"
import { PaymentRow } from "@/components/expected-payments/payment-row"
import type { AccountOption, ExpectedPayment } from "@/components/expected-payments/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Toaster } from "@/components/ui/sonner"

const HEAD = "px-3 py-3 text-xs font-semibold tracking-[0.06em] text-ink-3 uppercase"

// Expected payments (spec 20), from design/mockups/expected-payments.dc.html. Every change saves
// at once; the page then re-renders from the API.
export function ExpectedPayments({
  businessId,
  payments,
  accounts,
}: {
  businessId: string
  payments: ExpectedPayment[]
  accounts: AccountOption[]
}) {
  const t = useTranslations("ExpectedPayments")

  // One primary button per screen (DESIGN.md): the empty state's replaces the header's.
  const add = (
    <PaymentDialog
      businessId={businessId}
      accounts={accounts}
      trigger={
        <Button type="button" className="shrink-0 self-start sm:self-auto">
          <Plus aria-hidden="true" className="size-[18px]" strokeWidth={2} />
          {t("add")}
        </Button>
      }
    />
  )

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
        <div className="flex flex-col gap-1.5">
          <h1 className="font-heading text-[30px] leading-[1.1] font-semibold tracking-[-0.02em] sm:text-[40px]">
            {t("title")}
          </h1>
          <p className="text-[15px] text-ink-2">{t("intro")}</p>
        </div>
        {payments.length > 0 && add}
      </div>

      {payments.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-start gap-3">
            <CalendarClock aria-hidden="true" className="size-7 text-ink-2" strokeWidth={1.6} />
            <h2 className="text-[17px] font-semibold sm:text-[19px]">{t("emptyTitle")}</h2>
            <p className="text-sm leading-normal text-ink-2">{t("emptyBody")}</p>
            {add}
          </CardContent>
        </Card>
      ) : (
        <section
          aria-label={t("tableLabel")}
          className="rounded-[14px] border border-border bg-surface px-4 py-1 sm:px-6 sm:py-2.5"
        >
          <table className="w-full border-collapse text-[15px]">
            <thead className="max-sm:sr-only">
              <tr className="border-b border-border">
                <th scope="col" className={`${HEAD} text-left`}>
                  {t("columns.date")}
                </th>
                <th scope="col" className={`${HEAD} text-left`}>
                  {t("columns.description")}
                </th>
                <th scope="col" className={`${HEAD} text-left`}>
                  {t("columns.account")}
                </th>
                <th scope="col" className={`${HEAD} text-left`}>
                  {t("columns.repeats")}
                </th>
                <th scope="col" className={`${HEAD} text-right`}>
                  {t("columns.amount")}
                </th>
                <th scope="col" className={`${HEAD} w-[104px]`}>
                  <span className="sr-only">{t("columns.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {payments.map((payment) => (
                <PaymentRow key={payment.id} businessId={businessId} payment={payment} accounts={accounts} />
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Sonner's own label is English with its hotkey ("Notifications alt+T"). */}
      <Toaster customAriaLabel={t("notifications")} />
    </>
  )
}
