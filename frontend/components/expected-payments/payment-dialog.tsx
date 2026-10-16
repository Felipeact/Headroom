"use client"

import { useId, useState, useTransition, type FormEvent, type ReactNode } from "react"
import { CircleAlert } from "lucide-react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import {
  createExpectedPayment,
  updateExpectedPayment,
  type ExpectedPaymentBody,
} from "@/app/(app)/expected-payments/actions"
import { FieldError } from "@/components/expected-payments/field-error"
import { REPEATS, type AccountOption, type ExpectedPayment } from "@/components/expected-payments/types"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { MAX_AMOUNT_CENTS, formatAmountInput, parseAmountInput } from "@/lib/format"

type Direction = "out" | "in"
type Field = "amount" | "date" | "description"
type ErrorKey =
  | "amountRequired"
  | "amountInvalid"
  | "amountZero"
  | "amountTooLarge"
  | "dateRequired"
  | "descriptionRequired"

// "once" stands for a payment that doesn't repeat: Radix Select can't hold an empty value.
const ONCE = "once"

type Values = {
  direction: Direction
  amount: string
  date: string
  description: string
  accountId: string
  repeats: string
}

function initial(payment: ExpectedPayment | undefined, accounts: AccountOption[]): Values {
  const fallback = (accounts.find((a) => a.primary) ?? accounts[0])?.id ?? ""
  if (!payment) {
    return { direction: "out", amount: "", date: "", description: "", accountId: fallback, repeats: ONCE }
  }
  const known = accounts.some((a) => a.id === payment.account_id)
  return {
    direction: payment.amount_cents > 0 ? "in" : "out",
    amount: formatAmountInput(payment.amount_cents),
    date: payment.date,
    description: payment.description,
    // A payment whose account no longer counts as cash moves to the primary when saved.
    accountId: known ? payment.account_id : fallback,
    repeats: payment.repeats ?? ONCE,
  }
}

function validate(values: Values): { errors: Partial<Record<Field, ErrorKey>>; cents: number } {
  const errors: Partial<Record<Field, ErrorKey>> = {}
  const cents = parseAmountInput(values.amount)
  if (!values.amount.trim()) errors.amount = "amountRequired"
  else if (cents === null) errors.amount = "amountInvalid"
  else if (cents === 0) errors.amount = "amountZero"
  else if (cents > MAX_AMOUNT_CENTS) errors.amount = "amountTooLarge"
  if (!values.date) errors.date = "dateRequired"
  if (!values.description.trim()) errors.description = "descriptionRequired"
  return { errors, cents: cents ?? 0 }
}

// The add-and-edit dialog of the Expected payments page (spec 20), from
// design/mockups/expected-payments.dc.html. On a phone the dialog is a full-screen sheet.
export function PaymentDialog({
  businessId,
  accounts,
  payment,
  trigger,
}: {
  businessId: string
  accounts: AccountOption[]
  payment?: ExpectedPayment
  trigger: ReactNode
}) {
  const t = useTranslations("ExpectedPayments")
  const id = useId()
  const [open, setOpen] = useState(false)
  const [values, setValues] = useState<Values>(() => initial(payment, accounts))
  const [errors, setErrors] = useState<Partial<Record<Field, ErrorKey>>>({})
  const [failure, setFailure] = useState<string | null>(null)
  const [pending, startSaving] = useTransition()
  const editing = payment !== undefined

  function change<K extends keyof Values>(key: K, value: Values[K]) {
    setValues((current) => ({ ...current, [key]: value }))
  }

  function openChange(next: boolean) {
    if (next) {
      setValues(initial(payment, accounts))
      setErrors({})
      setFailure(null)
    }
    setOpen(next)
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const { errors: found, cents } = validate(values)
    setErrors(found)
    setFailure(null)
    if (Object.keys(found).length > 0) return
    const body: ExpectedPaymentBody = {
      account_id: values.accountId || null,
      description: values.description.trim(),
      amount_cents: values.direction === "in" ? cents : -cents,
      date: values.date,
      repeats: values.repeats === ONCE ? null : (values.repeats as ExpectedPaymentBody["repeats"]),
    }
    startSaving(async () => {
      const result = editing
        ? await updateExpectedPayment(businessId, payment.id, body)
        : await createExpectedPayment(businessId, body)
      if (!result.ok) {
        setFailure(result.status === 409 && result.detail ? result.detail : t("dialog.saveFailed"))
        return
      }
      setOpen(false)
      toast(editing ? t("toasts.updated") : t("toasts.added"))
    })
  }

  const describedBy = (field: Field) => (errors[field] ? `${id}-${field}-error` : undefined)

  return (
    <Dialog open={open} onOpenChange={openChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <form noValidate onSubmit={submit} className="flex flex-col gap-[18px]">
          <DialogHeader>
            <DialogTitle>{editing ? t("dialog.editTitle") : t("dialog.addTitle")}</DialogTitle>
            <DialogDescription className="sr-only">{t("dialog.description")}</DialogDescription>
          </DialogHeader>

          <ToggleGroup
            type="single"
            aria-label={t("dialog.direction")}
            spacing={1}
            value={values.direction}
            // A segmented control always has one choice, so ignore the click that would clear it.
            onValueChange={(value) => value && change("direction", value as Direction)}
            className="grid w-full grid-cols-2"
          >
            <ToggleGroupItem value="out">{t("dialog.moneyOut")}</ToggleGroupItem>
            <ToggleGroupItem value="in">{t("dialog.moneyIn")}</ToggleGroupItem>
          </ToggleGroup>

          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${id}-amount`}>{t("dialog.amount")}</Label>
              <div className="relative">
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-base font-semibold text-ink-2"
                >
                  $
                </span>
                <Input
                  id={`${id}-amount`}
                  type="text"
                  inputMode="decimal"
                  autoComplete="off"
                  value={values.amount}
                  onChange={(event) => change("amount", event.target.value)}
                  aria-invalid={errors.amount ? true : undefined}
                  aria-describedby={describedBy("amount")}
                  className="pl-7 tabular-nums"
                />
              </div>
              {errors.amount && <FieldError id={`${id}-amount-error`} message={t(`dialog.errors.${errors.amount}`)} />}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${id}-date`}>{t("dialog.date")}</Label>
              <Input
                id={`${id}-date`}
                type="date"
                value={values.date}
                onChange={(event) => change("date", event.target.value)}
                aria-invalid={errors.date ? true : undefined}
                aria-describedby={describedBy("date")}
              />
              {errors.date && <FieldError id={`${id}-date-error`} message={t(`dialog.errors.${errors.date}`)} />}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`${id}-description`}>{t("dialog.descriptionLabel")}</Label>
            <Input
              id={`${id}-description`}
              type="text"
              maxLength={100}
              value={values.description}
              onChange={(event) => change("description", event.target.value)}
              aria-invalid={errors.description ? true : undefined}
              aria-describedby={describedBy("description")}
            />
            {errors.description && (
              <FieldError id={`${id}-description-error`} message={t(`dialog.errors.${errors.description}`)} />
            )}
          </div>

          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${id}-account`}>{t("dialog.account")}</Label>
              <Select value={values.accountId} onValueChange={(value) => change("accountId", value)}>
                <SelectTrigger id={`${id}-account`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${id}-repeats`}>{t("dialog.repeats")}</Label>
              <Select value={values.repeats} onValueChange={(value) => change("repeats", value)}>
                <SelectTrigger id={`${id}-repeats`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[ONCE, ...REPEATS].map((repeats) => (
                    <SelectItem key={repeats} value={repeats}>
                      {t(`repeats.${repeats as "once"}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div role="alert">
            {failure && (
              <p className="flex items-start gap-1.5 text-sm text-danger-text">
                <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
                <span>{failure}</span>
              </p>
            )}
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="secondary" disabled={pending}>
                {t("dialog.cancel")}
              </Button>
            </DialogClose>
            <Button type="submit" disabled={pending} aria-busy={pending}>
              {editing
                ? pending
                  ? t("dialog.saving")
                  : t("dialog.save")
                : pending
                  ? t("dialog.adding")
                  : t("dialog.add")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
