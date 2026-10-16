"use client"

import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { disconnectBank } from "@/app/(app)/settings/banks/actions"
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

// "Disconnect" on a bank (spec 17): asks first, because the bank's data is deleted for good.
// On success the page re-renders without the bank.
export function DisconnectDialog({
  businessId,
  connectionId,
  bank,
}: {
  businessId: string
  connectionId: string
  bank: string
}) {
  const t = useTranslations("Settings.Banks")
  const [open, setOpen] = useState(false)
  const [failed, setFailed] = useState(false)
  const [pending, startDisconnect] = useTransition()

  function confirm() {
    setFailed(false)
    startDisconnect(async () => {
      const result = await disconnectBank(businessId, connectionId)
      if (result.error) {
        setFailed(true)
        return
      }
      setOpen(false)
      toast(t("disconnected", { bank }))
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
      <DialogTrigger asChild>
        <Button type="button" variant="destructive" className="shrink-0">
          {t("disconnect")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("disconnectTitle", { bank })}</DialogTitle>
          <DialogDescription>{t("disconnectBody")}</DialogDescription>
        </DialogHeader>
        <div role="alert">
          {failed && <p className="text-sm text-danger-text">{t("errors.disconnectFailed", { bank })}</p>}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="secondary" disabled={pending}>
              {t("cancel")}
            </Button>
          </DialogClose>
          <Button type="button" variant="destructive" disabled={pending} aria-busy={pending} onClick={confirm}>
            {pending ? t("disconnecting") : t("disconnect")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
