"use client"

import { useState, useTransition, type ReactNode } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { deleteExpectedPayment } from "@/app/(app)/expected-payments/actions"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

// "Delete" on an expected payment (spec 20): asks first, because it can't be undone. On success
// the page re-renders without the payment.
export function DeletePaymentDialog({
  businessId,
  paymentId,
  description,
  trigger,
}: {
  businessId: string
  paymentId: string
  description: string
  trigger: ReactNode
}) {
  const t = useTranslations("ExpectedPayments")
  const [open, setOpen] = useState(false)
  const [failed, setFailed] = useState(false)
  const [pending, startDelete] = useTransition()

  function confirm() {
    setFailed(false)
    startDelete(async () => {
      const result = await deleteExpectedPayment(businessId, paymentId)
      if (!result.ok) {
        setFailed(true)
        return
      }
      setOpen(false)
      toast(t("toasts.deleted"))
    })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setFailed(false)
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("deleteDialog.title", { description })}</DialogTitle>
          <DialogDescription>{t("deleteDialog.body")}</DialogDescription>
        </DialogHeader>
        <div role="alert">
          {failed && <p className="text-sm text-danger-text">{t("deleteDialog.failed")}</p>}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="secondary" disabled={pending}>
              {t("deleteDialog.cancel")}
            </Button>
          </DialogClose>
          <Button type="button" variant="destructive" disabled={pending} aria-busy={pending} onClick={confirm}>
            {pending ? t("deleteDialog.deleting") : t("deleteDialog.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
