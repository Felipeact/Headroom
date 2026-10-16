"use client"

import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { removeMember } from "@/app/(app)/settings/members/actions"
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

// "Remove" on a bookkeeper (spec 31): asks first, because their access ends at once.
export function RemoveMemberDialog({
  businessId,
  userId,
  name,
}: {
  businessId: string
  userId: string
  name: string
}) {
  const t = useTranslations("Settings.Members")
  const [open, setOpen] = useState(false)
  const [failed, setFailed] = useState(false)
  const [pending, startRemove] = useTransition()

  function confirm() {
    setFailed(false)
    startRemove(async () => {
      const result = await removeMember(businessId, userId)
      if (result.error) {
        setFailed(true)
        return
      }
      setOpen(false)
      toast(t("removed", { name }))
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
        <Button type="button" variant="destructive" className="shrink-0" aria-label={`${t("remove")} ${name}`}>
          {t("remove")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("removeTitle", { name })}</DialogTitle>
          <DialogDescription>{t("removeBody")}</DialogDescription>
        </DialogHeader>
        <div role="alert">{failed && <p className="text-sm text-danger-text">{t("errors.removeFailed", { name })}</p>}</div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="secondary" disabled={pending}>
              {t("cancel")}
            </Button>
          </DialogClose>
          <Button type="button" variant="destructive" disabled={pending} aria-busy={pending} onClick={confirm}>
            {pending ? t("removing") : t("remove")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
