"use client"

import { Plus } from "lucide-react"
import { useTranslations } from "next-intl"
import { PaymentDialog } from "@/components/expected-payments/payment-dialog"
import type { AccountOption } from "@/components/expected-payments/types"
import { Button } from "@/components/ui/button"

// "Add expected payment" on the dashboard opens spec 20's dialog in place (AC 25).
export function AddPaymentButton({ businessId, accounts }: { businessId: string; accounts: AccountOption[] }) {
  const t = useTranslations("Dashboard")

  return (
    <PaymentDialog
      businessId={businessId}
      accounts={accounts}
      trigger={
        <Button type="button" className="shrink-0 self-start sm:self-auto">
          <Plus aria-hidden="true" className="size-[18px]" strokeWidth={2} />
          {t("addPayment")}
        </Button>
      }
    />
  )
}
