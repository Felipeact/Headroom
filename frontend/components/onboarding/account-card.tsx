"use client"

import { useId } from "react"
import { useTranslations } from "next-intl"
import type { AccountChange } from "@/app/onboarding/accounts/actions"
import { Label } from "@/components/ui/label"
import { RadioGroupItem } from "@/components/ui/radio-group"
import { Switch } from "@/components/ui/switch"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { components } from "@/lib/api/schema"
import { formatMoney } from "@/lib/format"

type Account = components["schemas"]["Account"]

const CASH_CURRENCY = "CAD"
const ROW = "flex min-h-11 items-center border-t border-surface-muted"

// The rules the API enforces (spec 13 door 1); here they only decide which control to show.
function kind(account: Account) {
  if (account.type === "credit_card" || account.type === "line_of_credit") return "credit"
  if (account.type === "other") return "other"
  if (account.currency !== CASH_CURRENCY) return "currency"
  return account.type
}

// One account on the choose-accounts step (design/mockups/onboarding-3-choose-accounts.dc.html).
// Must sit inside the primary-account RadioGroup of `ChooseAccounts`.
export function AccountCard({
  account,
  disabled,
  onChange,
}: {
  account: Account
  disabled: boolean
  onChange: (change: AccountChange) => void
}) {
  const t = useTranslations("Onboarding")
  const accountKind = kind(account)
  const amount = accountKind === "credit" ? account.available_cents : account.balance_cents
  const type = t(`Accounts.types.${account.type}`)
  const nameId = useId()
  const radioId = useId()

  return (
    <li
      aria-labelledby={nameId}
      className="flex flex-col gap-2 rounded-[14px] border border-border bg-surface p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <p id={nameId} className="text-[15px] font-semibold">
            {account.name}
          </p>
          <p className="text-[13px] text-ink-3">
            {account.mask === null ? type : t("Accounts.details", { mask: account.mask, type })}
          </p>
        </div>
        {amount !== null && (
          <div className="flex flex-col items-end gap-0.5">
            <p className="text-base font-semibold tabular-nums">{formatMoney(amount, account.currency)}</p>
            {accountKind === "credit" && <p className="text-xs text-ink-3">{t("Accounts.available")}</p>}
          </div>
        )}
      </div>

      {accountKind === "checking" && (
        <div className={`${ROW} justify-between`}>
          <span className="text-sm">{t("Accounts.countsAsCash")}</span>
          <Switch
            checked={account.included}
            disabled={disabled}
            aria-label={t("Accounts.countsAsCashLabel", { name: account.name })}
            onCheckedChange={(included) => onChange({ included })}
          />
        </div>
      )}
      {accountKind === "savings" && (
        <>
          <p className="border-t border-surface-muted pt-3 text-sm font-semibold">{t("Accounts.spendQuestion")}</p>
          <ToggleGroup
            type="single"
            spacing={1}
            value={account.included ? "yes" : "no"}
            disabled={disabled}
            aria-label={t("Accounts.spendGroupLabel", { name: account.name })}
            // A segmented control always has one choice, so ignore the click that would clear it.
            onValueChange={(value) => value && onChange({ included: value === "yes" })}
            className="grid w-full grid-cols-2"
          >
            <ToggleGroupItem value="yes">{t("Accounts.spendYes")}</ToggleGroupItem>
            <ToggleGroupItem value="no">{t("Accounts.spendNo")}</ToggleGroupItem>
          </ToggleGroup>
        </>
      )}
      {accountKind === "credit" && <p className="text-[13px] leading-[1.45] text-ink-2">{t("Accounts.creditNote")}</p>}
      {accountKind === "other" && <p className="text-[13px] leading-[1.45] text-ink-2">{t("Accounts.otherNote")}</p>}
      {accountKind === "currency" && (
        <p className="text-[13px] leading-[1.45] text-ink-2">{t("Accounts.currencyNote")}</p>
      )}

      {account.included && (
        <Label className={`${ROW} gap-2.5 text-sm font-normal`} htmlFor={radioId}>
          <RadioGroupItem id={radioId} value={account.id} disabled={disabled} />
          {t("Accounts.primary")}
        </Label>
      )}
    </li>
  )
}
