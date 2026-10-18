"use client"

import { useState, useTransition } from "react"
import { CircleAlert, Plus } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { updateAccount, type AccountChange } from "@/app/onboarding/accounts/actions"
import { AccountCard } from "@/components/onboarding/account-card"
import { FlinksConnect } from "@/components/onboarding/flinks-connect"
import { useConnectBank } from "@/components/onboarding/use-connect-bank"
import { Button } from "@/components/ui/button"
import { RadioGroup } from "@/components/ui/radio-group"
import type { FlinksConnect as FlinksConnectInfo } from "@/lib/api/bank"
import type { components } from "@/lib/api/schema"

type Connection = components["schemas"]["Connection"]
type Message = "saveFailed" | "noneIncluded"

// Onboarding step 3, choose accounts, from design/mockups/onboarding-3-choose-accounts.dc.html
// (spec 13). Each change saves at once; the page then re-renders from the API, so the controls
// always show what the API last returned.
export function ChooseAccounts({
  businessId,
  linkToken,
  flinks = null,
  connections,
}: {
  businessId: string
  linkToken: string
  // Offered next to Plaid when the API has Flinks (spec 17a).
  flinks?: FlinksConnectInfo | null
  connections: Connection[]
}) {
  const t = useTranslations("Onboarding")
  const providers = useTranslations("BankProviders")
  const router = useRouter()
  const [message, setMessage] = useState<Message | null>(null)
  const [saving, startSaving] = useTransition()
  const connect = useConnectBank(businessId, linkToken)
  const busy = saving || connect.pending
  const accounts = connections.flatMap((connection) => connection.accounts)
  const primary = accounts.find((account) => account.primary)

  function save(accountId: string, change: AccountChange) {
    setMessage(null)
    connect.clearError()
    startSaving(async () => {
      const result = await updateAccount(businessId, accountId, change)
      setMessage(result.error)
    })
  }

  function connectAnother() {
    setMessage(null)
    connect.open()
  }

  function continueOn() {
    if (!accounts.some((account) => account.included)) {
      connect.clearError()
      setMessage("noneIncluded")
      return
    }
    router.push("/onboarding/minimum-balance")
  }

  const alert = message
    ? t(`Accounts.errors.${message}`)
    : connect.error
      ? t(`Bank.errors.${connect.error}`)
      : null
  const cards = (connection: Connection) => (
    <ul className="flex flex-col gap-3">
      {connection.accounts.map((account) => (
        <AccountCard
          key={account.id}
          account={account}
          disabled={busy}
          onChange={(change) => save(account.id, change)}
        />
      ))}
    </ul>
  )

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-[28px] leading-tight font-semibold tracking-[-0.02em]">
          {t("Accounts.title")}
        </h1>
        <p className="text-[15px] leading-normal text-ink-2">
          {connections.length === 1
            ? t("Accounts.introOne", { bank: connections[0].institution_name })
            : t("Accounts.introMany")}
        </p>
      </div>
      <RadioGroup
        value={primary?.id ?? ""}
        disabled={busy}
        aria-label={t("Accounts.primaryGroupLabel")}
        // The group wraps the cards, so it must not be a tab stop: Radix moves focus from it
        // to the checked radio, which skips every switch in the cards before that one.
        tabIndex={-1}
        onValueChange={(accountId) => save(accountId, { primary: true })}
        className="gap-5"
      >
        {connections.length === 1
          ? cards(connections[0])
          : connections.map((connection) => (
              <section key={connection.id} className="flex flex-col gap-3">
                <h2 className="text-base font-semibold">{connection.institution_name}</h2>
                {cards(connection)}
              </section>
            ))}
      </RadioGroup>
      <p className="text-[13px] leading-[1.45] text-ink-3">{t("Accounts.primaryNote")}</p>
      <div className="mt-auto flex flex-col gap-2.5">
        <div role="alert">
          {alert && (
            <p className="flex items-start gap-1.5 text-sm text-danger-text">
              <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0" strokeWidth={1.8} />
              <span>{alert}</span>
            </p>
          )}
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={busy || !connect.ready}
          aria-busy={connect.pending}
          onClick={connectAnother}
          className="min-h-[52px] rounded-xl text-base"
        >
          <Plus aria-hidden="true" className="size-[18px]" strokeWidth={2} />
          {connect.pending
            ? t("Bank.connecting")
            : flinks
              ? providers("plaid")
              : t("Accounts.connectAnother")}
        </Button>
        {flinks && (
          <FlinksConnect
            businessId={businessId}
            flinks={flinks}
            disabled={busy}
            className="min-h-[52px] rounded-xl text-base"
          />
        )}
        <Button
          type="button"
          disabled={busy}
          onClick={continueOn}
          className="min-h-[52px] rounded-xl text-base"
        >
          {t("Accounts.continue")}
        </Button>
      </div>
    </div>
  )
}
