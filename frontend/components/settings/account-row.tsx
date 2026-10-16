"use client"

import { useId } from "react"
import { useTranslations } from "next-intl"
import type { AccountChange } from "@/app/(app)/settings/banks/actions"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Switch } from "@/components/ui/switch"
import { formatMoney } from "@/lib/format"
import type { components } from "@/lib/api/schema"

type Account = components["schemas"]["Account"]

const CASH_CURRENCY = "CAD"
// On a phone each row becomes a two-column block: the account and its balance, then the
// cash and primary controls underneath.
const CELL = "px-3 py-1.5 max-sm:px-0"

// The rules the API enforces (spec 13 door 1); here they only decide which control to show.
function kind(account: Account) {
  if (account.type === "credit_card" || account.type === "line_of_credit") return "credit"
  if (account.type === "other") return "other"
  if (account.currency !== CASH_CURRENCY) return "currency"
  return "cash"
}

// One account in a bank's table on Settings > Bank connections (spec 17). Its primary radio has
// a group of its own: a group around the table would hold the switches too, and Radix sends
// focus entering a group straight to its checked radio, so Tab would skip them.
export function AccountRow({
  account,
  disabled,
  onChange,
}: {
  account: Account
  disabled: boolean
  onChange: (change: AccountChange) => void
}) {
  const t = useTranslations("Settings.Banks")
  const nameId = useId()
  const radioId = useId()
  const accountKind = kind(account)
  const type = t(`types.${account.type}`)
  // A card shows what is owed; a line of credit what is still available.
  const amount = account.type === "line_of_credit" ? account.available_cents : account.balance_cents
  const note =
    account.type === "line_of_credit" ? t("available") : account.type === "credit_card" ? t("owed") : null

  return (
    <tr
      aria-labelledby={nameId}
      className="border-b border-surface-muted last:border-b-0 max-sm:grid max-sm:grid-cols-[1fr_auto] max-sm:gap-x-3 max-sm:py-2"
    >
      <td className={CELL} data-user-content>
        <div id={nameId} className="font-semibold">
          {account.name}
        </div>
        <div className="text-[13px] text-ink-3">
          {account.mask === null ? type : t("details", { mask: account.mask, type })}
        </div>
      </td>
      <td className={`${CELL} text-right align-top sm:align-middle`}>
        {amount !== null && (
          <>
            <div data-user-content className="font-semibold tabular-nums">{formatMoney(amount, account.currency)}</div>
            {note && <div className="text-[13px] text-ink-3">{note}</div>}
          </>
        )}
      </td>
      <td className={`${CELL} sm:pl-8`}>
        {accountKind === "cash" ? (
          <Switch
            checked={account.included}
            disabled={disabled}
            aria-label={t("countsAsCashLabel", { name: account.name })}
            onCheckedChange={(included) => onChange({ included })}
          />
        ) : (
          <span className="text-[13px] text-ink-3">{t(`${accountKind}Note`)}</span>
        )}
      </td>
      <td className={`${CELL} max-sm:text-right`}>
        {account.included ? (
          <RadioGroup
            value={account.primary ? account.id : ""}
            disabled={disabled}
            aria-label={t("primaryGroupLabel")}
            onValueChange={() => onChange({ primary: true })}
          >
            <Label
              htmlFor={radioId}
              className={`flex min-h-11 items-center gap-2 text-sm font-normal max-sm:justify-end ${
                account.primary ? "" : "text-ink-2"
              }`}
            >
              <RadioGroupItem id={radioId} value={account.id} disabled={disabled} />
              {account.primary ? t("primary") : t("makePrimary")}
            </Label>
          </RadioGroup>
        ) : (
          <span className="text-[13px] text-ink-3">{t("notAvailable")}</span>
        )}
      </td>
    </tr>
  )
}
